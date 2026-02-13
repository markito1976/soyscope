"""USPTO PatentsView API adapter for SoyScope.

Free API key required. Rate limit: 45 requests/minute.
Docs: https://patentsview.org/apis/api-endpoints
Endpoint: https://search.patentsview.org/api/v1/patent/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class PatentsViewSource(BaseSource):
    """Search adapter for the USPTO PatentsView API."""

    BASE_URL = "https://search.patentsview.org/api/v1/patent/"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    @property
    def name(self) -> str:
        return "patentsview"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        # Build the query filter for PatentsView v1 API
        # The API uses Elasticsearch-style queries
        filters: list[dict[str, Any]] = [
            {"_or": [
                {"_text_any": {"patent_abstract": query}},
                {"_text_any": {"patent_title": query}},
            ]}
        ]

        if year_start is not None:
            filters.append({"_gte": {"patent_date": f"{year_start}-01-01"}})
        if year_end is not None:
            filters.append({"_lte": {"patent_date": f"{year_end}-12-31"}})

        q_filter = {"_and": filters} if len(filters) > 1 else filters[0]

        params: dict[str, Any] = {
            "q": q_filter,
            "f": ["patent_number", "patent_title", "patent_abstract",
                   "patent_date", "patent_type",
                   "assignees.assignee_organization",
                   "inventors.inventor_first_name",
                   "inventors.inventor_last_name"],
            "o": {"per_page": min(max_results, 100)},
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers=headers,
                    json=params,
                )
                response.raise_for_status()
                data = response.json()

                total_results = data.get("total_patent_count", 0)
                patents = data.get("patents", [])

                for pat in patents:
                    paper = self._parse_patent(pat)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "PatentsView HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("PatentsView request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching PatentsView for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    def _parse_patent(self, pat: dict[str, Any]) -> Paper | None:
        try:
            title = pat.get("patent_title", "")
            if not title:
                return None

            abstract = pat.get("patent_abstract", "") or None

            # Patent date → year
            patent_date = pat.get("patent_date", "")
            year = None
            if patent_date:
                try:
                    year = int(str(patent_date)[:4])
                except (ValueError, IndexError):
                    pass

            patent_number = pat.get("patent_number", "")
            url = f"https://patents.google.com/patent/US{patent_number}" if patent_number else None

            # Inventors
            authors: list[str] = []
            for inv in pat.get("inventors", []) or []:
                first = inv.get("inventor_first_name", "")
                last = inv.get("inventor_last_name", "")
                full = f"{first} {last}".strip()
                if full:
                    authors.append(full)

            # Assignee as venue
            venue = None
            assignees = pat.get("assignees", []) or []
            if assignees:
                venue = assignees[0].get("assignee_organization")

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                url=url,
                authors=authors,
                venue=venue,
                source_type=SourceType.PATENT,
                raw_metadata=pat,
            )
        except Exception:
            self.logger.exception("Failed to parse PatentsView patent: %s", pat.get("patent_number"))
            return None
