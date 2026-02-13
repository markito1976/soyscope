"""OSTI.gov (Office of Scientific and Technical Information) adapter for SoyScope.

Free REST API — no authentication required.
Covers DOE PAGES (journal articles), DOE Patents, DOE Data Explorer, ETDEWEB.
Docs: https://www.osti.gov/api/v1/docs
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import OAStatus, Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class OSTISource(BaseSource):
    """Search adapter for the OSTI.gov REST API."""

    BASE_URL = "https://www.osti.gov/api/v1/records"

    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "osti"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        params: dict[str, Any] = {
            "q": query,
            "rows": min(max_results, 100),
            "page": 0,
        }

        if year_start is not None:
            params["publication_date_start"] = f"{year_start}-01-01"
        if year_end is not None:
            params["publication_date_end"] = f"{year_end}-12-31"

        headers = {"Accept": "application/json"}
        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                records = response.json()

                # OSTI returns a list of records directly
                if isinstance(records, list):
                    total_results = len(records)
                    for rec in records:
                        paper = self._parse_record(rec)
                        if paper is not None:
                            papers.append(paper)
                elif isinstance(records, dict):
                    # Some endpoints wrap in a dict
                    items = records.get("records", records.get("results", []))
                    total_results = records.get("total", len(items))
                    for rec in items:
                        paper = self._parse_record(rec)
                        if paper is not None:
                            papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "OSTI HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("OSTI request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching OSTI for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        headers = {"Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.BASE_URL,
                    params={"q": f'doi:"{doi}"', "rows": 1},
                    headers=headers,
                )
                response.raise_for_status()
                records = response.json()
                items = records if isinstance(records, list) else records.get("records", [])
                if items:
                    return self._parse_record(items[0])
        except httpx.HTTPStatusError as exc:
            self.logger.error("OSTI HTTP error %s for DOI %r: %s", exc.response.status_code, doi, exc)
        except httpx.RequestError as exc:
            self.logger.error("OSTI request error for DOI %r: %s", doi, exc)
        except Exception:
            self.logger.exception("Unexpected error fetching DOI %r from OSTI", doi)
        return None

    def _parse_record(self, rec: dict[str, Any]) -> Paper | None:
        try:
            title = rec.get("title", "")
            if not title:
                return None

            abstract = rec.get("description", "") or None

            # Authors: OSTI returns semicolon-separated or list
            raw_authors = rec.get("authors", "")
            if isinstance(raw_authors, str):
                authors = [a.strip() for a in raw_authors.split(";") if a.strip()]
            elif isinstance(raw_authors, list):
                authors = raw_authors
            else:
                authors = []

            # Year from publication_date (YYYY-MM-DD or YYYY)
            pub_date = rec.get("publication_date", "")
            year = None
            if pub_date:
                try:
                    year = int(str(pub_date)[:4])
                except (ValueError, IndexError):
                    pass

            doi = rec.get("doi") or None
            url = rec.get("link") or rec.get("links", {}).get("fulltext") or None
            pdf_url = rec.get("links", {}).get("fulltext") if isinstance(rec.get("links"), dict) else None

            # Determine source type
            product_type = rec.get("product_type", "").lower()
            if "patent" in product_type:
                source_type = SourceType.PATENT
            elif "report" in product_type or "technical" in product_type:
                source_type = SourceType.GOVT_REPORT
            elif "conference" in product_type:
                source_type = SourceType.CONFERENCE
            else:
                source_type = SourceType.PAPER

            # OA: OSTI content is generally open access
            oa_status = OAStatus.GOLD if rec.get("access_type") == "Open" else None

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                doi=doi,
                url=url,
                pdf_url=pdf_url,
                authors=authors,
                venue=rec.get("journal_name") or rec.get("publisher"),
                source_type=source_type,
                open_access_status=oa_status,
                raw_metadata=rec,
            )
        except Exception:
            self.logger.exception("Failed to parse OSTI record: %s", rec.get("osti_id"))
            return None
