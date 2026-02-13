"""AGRIS (FAO) bibliographic database adapter for SoyScope.

7+ million multilingual records. Strong Global South coverage.
Uses the AGRIS search API (JSON).
Docs: https://agris.fao.org/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class AGRISSource(BaseSource):
    """Search adapter for the AGRIS (FAO) database."""

    BASE_URL = "https://agris.fao.org/search"

    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "agris"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        params: dict[str, Any] = {
            "query": query,
            "sortField": "Relevance",
            "numberOfResult": min(max_results, 100),
            "startRecord": 0,
            "output": "json",
        }

        if year_start is not None:
            params["yearFrom"] = year_start
        if year_end is not None:
            params["yearTo"] = year_end

        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                total_results = data.get("totalCount", data.get("total", 0))
                records = data.get("results", data.get("records", []))

                for rec in records:
                    paper = self._parse_record(rec)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "AGRIS HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("AGRIS request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching AGRIS for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    def _parse_record(self, rec: dict[str, Any]) -> Paper | None:
        try:
            title = rec.get("title", "") or rec.get("dcTitle", "")
            if isinstance(title, list):
                title = title[0] if title else ""
            if not title:
                return None

            abstract = rec.get("abstract", "") or rec.get("dcDescription", "") or None
            if isinstance(abstract, list):
                abstract = abstract[0] if abstract else None

            # Authors
            raw_authors = rec.get("authors", rec.get("dcCreator", []))
            if isinstance(raw_authors, str):
                authors = [a.strip() for a in raw_authors.split(";") if a.strip()]
            elif isinstance(raw_authors, list):
                authors = [a if isinstance(a, str) else a.get("name", "") for a in raw_authors]
                authors = [a for a in authors if a]
            else:
                authors = []

            # Year
            year = None
            date_str = rec.get("date", "") or rec.get("dcDate", "")
            if isinstance(date_str, list):
                date_str = date_str[0] if date_str else ""
            if date_str:
                try:
                    year = int(str(date_str)[:4])
                except (ValueError, IndexError):
                    pass

            # URL
            url = rec.get("url", "") or rec.get("dcIdentifier", "") or None
            if isinstance(url, list):
                url = url[0] if url else None

            # Venue / journal
            venue = rec.get("source", "") or rec.get("dcSource", "") or None
            if isinstance(venue, list):
                venue = venue[0] if venue else None

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                url=url,
                authors=authors,
                venue=venue,
                source_type=SourceType.PAPER,
                raw_metadata=rec,
            )
        except Exception:
            self.logger.exception("Failed to parse AGRIS record: %s", rec.get("title"))
            return None
