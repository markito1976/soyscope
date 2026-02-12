"""Unpaywall OA PDF location API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ..models import OAStatus, Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)

_OA_STATUS_MAP: dict[str, OAStatus] = {
    "gold": OAStatus.GOLD,
    "green": OAStatus.GREEN,
    "hybrid": OAStatus.HYBRID,
    "bronze": OAStatus.BRONZE,
    "closed": OAStatus.CLOSED,
}


class UnpaywallSource(BaseSource):
    """Search adapter for the Unpaywall REST API.

    Unpaywall is DOI-based only -- it does not support free-text search.
    The primary entry point is :meth:`get_by_doi`; the :meth:`search`
    method is a limited convenience that only works when *query* looks
    like a DOI string.
    """

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str | None = None) -> None:
        super().__init__(email=email)

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "unpaywall"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Limited search implementation.

        Unpaywall only works with DOIs.  If *query* looks like a DOI
        (contains ``"10."``), we attempt to fetch that DOI directly.
        Otherwise an empty :class:`SearchResult` is returned.
        """
        if "10." in query:
            paper = await self.get_by_doi(query.strip())
            if paper is not None:
                return SearchResult(
                    papers=[paper],
                    total_results=1,
                    query=query,
                    api_source=self.name,
                )
        return SearchResult(
            papers=[],
            total_results=0,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Retrieve open-access metadata for a single DOI.

        This is the primary method -- Unpaywall is a DOI-based service.
        """
        url = f"{self.BASE_URL}/{doi}"
        params: dict[str, str] = {}
        if self.email:
            params["email"] = self.email

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    self.logger.info("DOI not found in Unpaywall: %s", doi)
                    return None
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except httpx.HTTPStatusError:
            self.logger.exception("Unpaywall HTTP error for doi=%r", doi)
            return None
        except Exception:
            self.logger.exception("Unpaywall request failed for doi=%r", doi)
            return None

        return self._parse_response(data)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def get_pdf_url(self, doi: str) -> str | None:
        """Return the best OA PDF URL for *doi*, or ``None``."""
        url = f"{self.BASE_URL}/{doi}"
        params: dict[str, str] = {}
        if self.email:
            params["email"] = self.email

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    self.logger.info("DOI not found in Unpaywall: %s", doi)
                    return None
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except httpx.HTTPStatusError:
            self.logger.exception("Unpaywall HTTP error for doi=%r", doi)
            return None
        except Exception:
            self.logger.exception("Unpaywall request failed for doi=%r", doi)
            return None

        best_oa = data.get("best_oa_location")
        if best_oa:
            return best_oa.get("url_for_pdf")
        return None

    async def get_many_by_doi(self, dois: list[str]) -> list[Paper]:
        """Fetch multiple DOIs sequentially with a small delay between each."""
        papers: list[Paper] = []
        for i, doi in enumerate(dois):
            paper = await self.get_by_doi(doi)
            if paper is not None:
                papers.append(paper)
            # Small delay between requests to be polite to the API
            if i < len(dois) - 1:
                await asyncio.sleep(0.5)
        return papers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(self, data: dict[str, Any]) -> Paper:
        """Convert an Unpaywall API response dict into a :class:`Paper`."""
        title = data.get("title") or "Untitled"
        doi = data.get("doi")
        year = data.get("year")
        doi_url = data.get("doi_url")

        # Best OA PDF URL
        best_oa = data.get("best_oa_location")
        pdf_url: str | None = None
        if best_oa:
            pdf_url = best_oa.get("url_for_pdf")

        # Authors
        authors: list[str] = []
        for author in data.get("z_authors", []) or []:
            given = author.get("given", "")
            family = author.get("family", "")
            full = f"{given} {family}".strip()
            if full:
                authors.append(full)

        # Venue
        venue = data.get("journal_name")

        # Open-access status
        oa_status_str = data.get("oa_status", "")
        open_access_status = _OA_STATUS_MAP.get(oa_status_str)

        # Raw metadata: include the oa_locations list
        raw_metadata: dict[str, Any] = {
            "oa_locations": data.get("oa_locations", []),
        }

        return self._make_paper(
            title=title,
            doi=doi,
            year=year,
            url=doi_url,
            pdf_url=pdf_url,
            authors=authors,
            venue=venue,
            open_access_status=open_access_status,
            source_type=SourceType.PAPER,
            raw_metadata=raw_metadata,
        )
