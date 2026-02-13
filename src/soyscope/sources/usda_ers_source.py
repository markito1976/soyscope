"""USDA ERS (Economic Research Service) adapter for SoyScope.

REST API at https://api.ers.usda.gov/data/arms/
Free API key from https://api.data.gov
Covers Agricultural Resource Management Survey, Oil Crops data.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class USDAERSSource(BaseSource):
    """Search adapter for USDA ERS data APIs."""

    BASE_URL = "https://api.ers.usda.gov/data/arms"
    SEARCH_URL = "https://api.nal.usda.gov/pubag/rest/search"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    @property
    def name(self) -> str:
        return "usda_ers"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        # Use PubAg (USDA publication aggregator) for text search
        # which covers ERS publications and more USDA literature
        params: dict[str, Any] = {
            "query": query,
            "numRecords": min(max_results, 100),
            "startRecord": 0,
        }

        if self.api_key:
            params["api_key"] = self.api_key

        # Build date filter
        fq_parts: list[str] = []
        if year_start is not None and year_end is not None:
            fq_parts.append(f"publicationYear:[{year_start} TO {year_end}]")
        elif year_start is not None:
            fq_parts.append(f"publicationYear:[{year_start} TO *]")
        elif year_end is not None:
            fq_parts.append(f"publicationYear:[* TO {year_end}]")

        if fq_parts:
            params["fq"] = " AND ".join(fq_parts)

        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.SEARCH_URL,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                total_results = data.get("numFound", data.get("totalResults", 0))
                records = data.get("result", data.get("results", []))

                for rec in records:
                    paper = self._parse_record(rec)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "USDA ERS HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("USDA ERS request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching USDA ERS for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    def _parse_record(self, rec: dict[str, Any]) -> Paper | None:
        try:
            title = rec.get("title", "")
            if not title:
                return None

            abstract = rec.get("abstract", "") or rec.get("description", "") or None

            # Authors
            raw_authors = rec.get("authors", [])
            if isinstance(raw_authors, str):
                authors = [a.strip() for a in raw_authors.split(";") if a.strip()]
            elif isinstance(raw_authors, list):
                authors = []
                for a in raw_authors:
                    if isinstance(a, str):
                        authors.append(a)
                    elif isinstance(a, dict):
                        authors.append(a.get("name", ""))
                authors = [a for a in authors if a]
            else:
                authors = []

            # Year
            year = None
            year_val = rec.get("publicationYear") or rec.get("year")
            if year_val:
                try:
                    year = int(year_val)
                except (ValueError, TypeError):
                    pass

            doi = rec.get("doi") or None
            url = rec.get("url") or rec.get("link") or None
            pdf_url = rec.get("pdfUrl") or rec.get("fullTextUrl") or None

            # Venue
            venue = rec.get("journal", "") or rec.get("source", "") or None

            # Determine type
            doc_type = (rec.get("documentType", "") or rec.get("type", "")).lower()
            if "report" in doc_type:
                source_type = SourceType.GOVT_REPORT
            else:
                source_type = SourceType.PAPER

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                doi=doi,
                url=url,
                pdf_url=pdf_url,
                authors=authors,
                venue=venue,
                source_type=source_type,
                raw_metadata=rec,
            )
        except Exception:
            self.logger.exception("Failed to parse USDA ERS record: %s", rec.get("title"))
            return None
