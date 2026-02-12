"""CORE (core.ac.uk) full-text open access search adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ..models import OAStatus, Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class CoreSource(BaseSource):
    """Search adapter for the CORE open access API (v3)."""

    BASE_URL = "https://api.core.ac.uk/v3"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "core"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search CORE ``POST /search/works`` for open access papers.

        Parameters
        ----------
        query:
            Free-text search query.
        max_results:
            Maximum number of results to return (capped at 100 by the API).
        year_start / year_end:
            Optional publication-year filter range.
        """
        effective_query = query
        if year_start is not None:
            effective_query = f"({effective_query}) AND yearPublished>={year_start}"
        if year_end is not None:
            effective_query = f"({effective_query}) AND yearPublished<={year_end}"

        body: dict[str, Any] = {
            "q": effective_query,
            "limit": min(max_results, 100),
            "offset": 0,
        }

        headers = self._auth_headers()
        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/search/works",
                    headers=headers,
                    json=body,
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    self.logger.warning(
                        "CORE rate-limited (429). Retrying after %d seconds.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    response = await client.post(
                        f"{self.BASE_URL}/search/works",
                        headers=headers,
                        json=body,
                    )

                response.raise_for_status()
                data = response.json()

                total_results = data.get("totalHits", 0)
                results = data.get("results", [])

                for work in results:
                    paper = self._parse_work(work)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "CORE HTTP error %s for query %r: %s",
                exc.response.status_code,
                query,
                exc,
            )
        except httpx.RequestError as exc:
            self.logger.error(
                "CORE request error for query %r: %s", query, exc
            )
        except Exception:
            self.logger.exception(
                "Unexpected error while searching CORE for query %r", query
            )

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Look up a single work in CORE by DOI."""
        headers = self._auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/search/works",
                    headers=headers,
                    params={"q": f'doi:"{doi}"'},
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    self.logger.warning(
                        "CORE rate-limited (429). Retrying after %d seconds.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    response = await client.get(
                        f"{self.BASE_URL}/search/works",
                        headers=headers,
                        params={"q": f'doi:"{doi}"'},
                    )

                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if results:
                    return self._parse_work(results[0])

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                self.logger.info("DOI %r not found in CORE", doi)
            else:
                self.logger.error(
                    "CORE HTTP error %s fetching DOI %r: %s",
                    exc.response.status_code,
                    doi,
                    exc,
                )
        except httpx.RequestError as exc:
            self.logger.error(
                "CORE request error fetching DOI %r: %s", doi, exc
            )
        except Exception:
            self.logger.exception(
                "Unexpected error fetching DOI %r from CORE", doi
            )

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build authorization headers for the CORE API."""
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _parse_work(self, work: dict[str, Any]) -> Paper | None:
        """Convert a raw CORE work dict into a :class:`Paper`."""
        try:
            title = work.get("title", "")
            if not title:
                return None

            abstract = work.get("abstract", "") or None

            # Authors: CORE returns a list of dicts with a "name" key.
            authors: list[str] = []
            for author_entry in work.get("authors", []):
                author_name = author_entry.get("name") if isinstance(author_entry, dict) else None
                if author_name:
                    authors.append(author_name)

            # URL: prefer downloadUrl, then first sourceFulltextUrl, then
            # fall back to the CORE landing page.
            core_id = work.get("id")
            url = (
                work.get("downloadUrl")
                or (work.get("sourceFulltextUrls") or [None])[0]
                or (f"https://core.ac.uk/works/{core_id}" if core_id else None)
            )

            pdf_url = work.get("downloadUrl")

            # Venue: prefer publisher, fall back to first journal title.
            venue = work.get("publisher") or None
            if venue is None:
                journals = work.get("journals", [])
                if journals and isinstance(journals[0], dict):
                    venue = journals[0].get("title")

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=work.get("yearPublished"),
                doi=work.get("doi"),
                url=url,
                pdf_url=pdf_url,
                authors=authors,
                venue=venue,
                citation_count=work.get("citationCount"),
                open_access_status=OAStatus.GREEN,
                source_type=SourceType.PAPER,
                raw_metadata=work,
            )

        except Exception:
            self.logger.exception(
                "Failed to parse CORE work: %s", work.get("id")
            )
            return None
