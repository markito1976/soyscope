"""SBIR/STTR Awards Database adapter for SoyScope.

Free, no authentication required.
API: https://api.www.sbir.gov/public/api/awards
Tracks federally funded small business innovation awards.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class SBIRSource(BaseSource):
    """Search adapter for the SBIR/STTR Awards API."""

    BASE_URL = "https://api.www.sbir.gov/public/api/awards"

    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "sbir"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        params: dict[str, Any] = {
            "keyword": query,
            "rows": min(max_results, 100),
            "start": 0,
        }

        if year_start is not None:
            params["year.gte"] = year_start
        if year_end is not None:
            params["year.lte"] = year_end

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

                # SBIR API returns results in various structures
                if isinstance(data, dict):
                    total_results = data.get("totalCount", data.get("numFound", 0))
                    awards = data.get("results", data.get("awards", []))
                elif isinstance(data, list):
                    awards = data
                    total_results = len(data)
                else:
                    awards = []

                for award in awards:
                    paper = self._parse_award(award)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "SBIR HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("SBIR request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching SBIR for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    def _parse_award(self, award: dict[str, Any]) -> Paper | None:
        try:
            title = award.get("award_title", "") or award.get("title", "")
            if not title:
                return None

            abstract = award.get("abstract", "") or None

            # Year from award_year or year field
            year = None
            for field in ("award_year", "year", "award_date"):
                val = award.get(field)
                if val:
                    try:
                        year = int(str(val)[:4])
                        break
                    except (ValueError, IndexError):
                        continue

            # PI as author
            authors: list[str] = []
            pi = award.get("pi_name", "") or award.get("pi", "")
            if pi:
                authors.append(pi)

            # Company/firm as venue
            venue = award.get("firm", "") or award.get("company", "")

            # Agency info
            agency = award.get("agency", "")
            url = award.get("award_link") or award.get("url") or None

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                url=url,
                authors=authors,
                venue=f"{venue} ({agency})" if venue and agency else venue or agency or None,
                source_type=SourceType.GOVT_REPORT,
                raw_metadata=award,
            )
        except Exception:
            self.logger.exception("Failed to parse SBIR award: %s", award.get("award_title"))
            return None
