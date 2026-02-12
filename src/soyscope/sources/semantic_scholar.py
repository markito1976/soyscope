"""Semantic Scholar API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)

# Fields requested from the Semantic Scholar Graph API.
_S2_FIELDS = (
    "paperId,externalIds,title,abstract,year,citationCount,"
    "venue,authors,openAccessPdf,publicationTypes,tldr"
)


class SemanticScholarSource(BaseSource):
    """Search adapter for the Semantic Scholar Graph API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "semantic_scholar"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search Semantic Scholar for papers matching *query*.

        Parameters
        ----------
        query:
            Free-text search string.
        max_results:
            Maximum number of papers to return (capped at 100 by the API).
        year_start:
            Optional lower bound on publication year (inclusive).
        year_end:
            Optional upper bound on publication year (inclusive).
        """
        limit = min(max_results, 100)

        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "fields": _S2_FIELDS,
        }

        # Build the year range filter (e.g. "2000-2005").
        if year_start is not None and year_end is not None:
            params["year"] = f"{year_start}-{year_end}"
        elif year_start is not None:
            params["year"] = f"{year_start}-"
        elif year_end is not None:
            params["year"] = f"-{year_end}"

        headers = self._build_headers()
        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/paper/search",
                    params=params,
                    headers=headers,
                )

                # Handle rate limiting with a single retry after waiting.
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    self.logger.warning(
                        "Semantic Scholar rate-limited (429). "
                        "Retrying after %d seconds.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    response = await client.get(
                        f"{self.BASE_URL}/paper/search",
                        params=params,
                        headers=headers,
                    )

                response.raise_for_status()
                data = response.json()

                total_results = data.get("total", 0)
                results = data.get("data", [])

                for item in results:
                    paper = self._parse_paper(item)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "Semantic Scholar HTTP error %s for query %r: %s",
                exc.response.status_code,
                query,
                exc,
            )
        except httpx.RequestError as exc:
            self.logger.error(
                "Semantic Scholar request error for query %r: %s",
                query,
                exc,
            )
        except Exception:
            self.logger.exception(
                "Unexpected error while searching Semantic Scholar for query %r",
                query,
            )

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Fetch a single paper from Semantic Scholar by DOI."""
        headers = self._build_headers()
        params: dict[str, str] = {"fields": _S2_FIELDS}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/paper/DOI:{doi}",
                    params=params,
                    headers=headers,
                )

                # Handle rate limiting with a single retry after waiting.
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    self.logger.warning(
                        "Semantic Scholar rate-limited (429) fetching DOI %r. "
                        "Retrying after %d seconds.",
                        doi,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    response = await client.get(
                        f"{self.BASE_URL}/paper/DOI:{doi}",
                        params=params,
                        headers=headers,
                    )

                if response.status_code == 404:
                    self.logger.info(
                        "DOI %r not found in Semantic Scholar", doi
                    )
                    return None

                response.raise_for_status()
                data = response.json()
                return self._parse_paper(data)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                self.logger.info(
                    "DOI %r not found in Semantic Scholar", doi
                )
            else:
                self.logger.error(
                    "Semantic Scholar HTTP error %s fetching DOI %r: %s",
                    exc.response.status_code,
                    doi,
                    exc,
                )
        except httpx.RequestError as exc:
            self.logger.error(
                "Semantic Scholar request error fetching DOI %r: %s",
                doi,
                exc,
            )
        except Exception:
            self.logger.exception(
                "Unexpected error fetching DOI %r from Semantic Scholar", doi
            )

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers, including the API key when available."""
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _parse_paper(self, paper: dict[str, Any]) -> Paper | None:
        """Convert a raw Semantic Scholar paper dict into a :class:`Paper`."""
        try:
            title = paper.get("title") or ""
            if not title:
                return None

            abstract = paper.get("abstract") or None

            year = paper.get("year")

            # DOI from externalIds.
            external_ids = paper.get("externalIds") or {}
            doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None

            # Canonical URL on Semantic Scholar.
            paper_id = paper.get("paperId", "")
            url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

            # Open-access PDF URL.
            oa_pdf = paper.get("openAccessPdf")
            pdf_url: str | None = None
            if isinstance(oa_pdf, dict) and oa_pdf:
                pdf_url = oa_pdf.get("url")

            # Authors list.
            authors: list[str] = []
            for author in paper.get("authors") or []:
                if isinstance(author, dict):
                    author_name = author.get("name")
                    if author_name:
                        authors.append(author_name)

            venue = paper.get("venue") or None
            citation_count = paper.get("citationCount")

            # Build raw_metadata, including the TLDR if present.
            raw_metadata: dict[str, Any] = {}
            tldr = paper.get("tldr")
            if tldr is not None:
                raw_metadata["tldr"] = tldr

            publication_types = paper.get("publicationTypes")
            if publication_types is not None:
                raw_metadata["publicationTypes"] = publication_types

            if external_ids:
                raw_metadata["externalIds"] = external_ids

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                doi=doi,
                url=url,
                pdf_url=pdf_url,
                authors=authors,
                venue=venue,
                citation_count=citation_count,
                raw_metadata=raw_metadata,
            )

        except Exception:
            self.logger.exception(
                "Failed to parse Semantic Scholar paper: %s",
                paper.get("paperId"),
            )
            return None
