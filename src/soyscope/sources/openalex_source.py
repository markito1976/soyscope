"""OpenAlex API adapter for SoyScope."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import OAStatus, Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)

# Mapping from OpenAlex OA status strings to our OAStatus enum.
_OA_STATUS_MAP: dict[str, OAStatus] = {
    "gold": OAStatus.GOLD,
    "green": OAStatus.GREEN,
    "hybrid": OAStatus.HYBRID,
    "bronze": OAStatus.BRONZE,
    "closed": OAStatus.CLOSED,
}


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild plain-text abstract from an OpenAlex inverted index.

    OpenAlex stores abstracts as ``{word: [position, ...], ...}``.  We
    reconstruct the original text by placing every word at its recorded
    positions and joining with spaces.
    """
    if not inverted_index:
        return ""

    # Determine the total length so we can pre-allocate the list.
    max_pos = -1
    for positions in inverted_index.values():
        for pos in positions:
            if pos > max_pos:
                max_pos = pos

    if max_pos < 0:
        return ""

    words: list[str] = [""] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word

    return " ".join(words)


class OpenAlexSource(BaseSource):
    """Search adapter for the OpenAlex REST API."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str | None = None) -> None:
        super().__init__(email=email)
        self.email = email

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "openalex"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search OpenAlex ``/works`` for papers matching *query*.

        Uses cursor-based pagination when *max_results* exceeds a single
        page (capped at 200 per page by the API).
        """
        per_page = min(max_results, 200)

        params: dict[str, Any] = {
            "search": query,
            "per_page": per_page,
            "select": (
                "id,doi,title,display_name,publication_year,"
                "cited_by_count,type,open_access,authorships,"
                "primary_location,abstract_inverted_index"
            ),
        }

        if self.email:
            params["mailto"] = self.email

        # Build the filter string for year range.
        filters: list[str] = []
        if year_start is not None and year_end is not None:
            filters.append(f"publication_year:{year_start}-{year_end}")
        elif year_start is not None:
            filters.append(f"publication_year:{year_start}-")
        elif year_end is not None:
            filters.append(f"publication_year:-{year_end}")

        if filters:
            params["filter"] = ",".join(filters)

        papers: list[Paper] = []
        collected = 0
        cursor: str | None = "*"  # initial cursor value for first page
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while cursor is not None and collected < max_results:
                    page_params = {**params, "cursor": cursor}
                    response = await client.get(
                        f"{self.BASE_URL}/works",
                        params=page_params,
                    )
                    response.raise_for_status()
                    data = response.json()

                    total_results = data.get("meta", {}).get("count", 0)
                    results = data.get("results", [])

                    if not results:
                        break

                    for work in results:
                        if collected >= max_results:
                            break
                        paper = self._parse_work(work)
                        if paper is not None:
                            papers.append(paper)
                        collected += 1

                    # Advance cursor for next page.
                    cursor = data.get("meta", {}).get("next_cursor")

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "OpenAlex HTTP error %s for query %r: %s",
                exc.response.status_code,
                query,
                exc,
            )
        except httpx.RequestError as exc:
            self.logger.error(
                "OpenAlex request error for query %r: %s", query, exc
            )
        except Exception:
            self.logger.exception(
                "Unexpected error while searching OpenAlex for query %r", query
            )

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Fetch a single work from OpenAlex by DOI."""
        # Normalise: strip common URL prefixes so we have a bare DOI.
        clean_doi = _strip_doi_prefix(doi)

        params: dict[str, Any] = {}
        if self.email:
            params["mailto"] = self.email

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/works/doi:{clean_doi}",
                    params=params,
                )
                response.raise_for_status()
                work = response.json()
                return self._parse_work(work)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                self.logger.info("DOI %r not found in OpenAlex", clean_doi)
            else:
                self.logger.error(
                    "OpenAlex HTTP error %s fetching DOI %r: %s",
                    exc.response.status_code,
                    clean_doi,
                    exc,
                )
        except httpx.RequestError as exc:
            self.logger.error(
                "OpenAlex request error fetching DOI %r: %s", clean_doi, exc
            )
        except Exception:
            self.logger.exception(
                "Unexpected error fetching DOI %r from OpenAlex", clean_doi
            )

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_work(self, work: dict[str, Any]) -> Paper | None:
        """Convert a raw OpenAlex work dict into a :class:`Paper`."""
        try:
            title = work.get("display_name") or work.get("title") or ""
            if not title:
                return None

            # Abstract reconstruction.
            abstract = _reconstruct_abstract(
                work.get("abstract_inverted_index")
            ) or None

            # DOI: strip URL prefix if present.
            raw_doi = work.get("doi") or ""
            doi = _strip_doi_prefix(raw_doi) if raw_doi else None

            # Authors list.
            authors: list[str] = []
            for authorship in work.get("authorships") or []:
                author = authorship.get("author", {})
                display_name = author.get("display_name")
                if display_name:
                    authors.append(display_name)

            # Venue / journal name from primary_location.
            venue: str | None = None
            primary_location = work.get("primary_location")
            if primary_location and isinstance(primary_location, dict):
                source = primary_location.get("source")
                if source and isinstance(source, dict):
                    venue = source.get("display_name")

            # Open-access status.
            oa_info = work.get("open_access") or {}
            oa_status_str = oa_info.get("oa_status", "")
            open_access_status = _OA_STATUS_MAP.get(oa_status_str)

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=work.get("publication_year"),
                doi=doi,
                url=work.get("id"),
                authors=authors,
                venue=venue,
                citation_count=work.get("cited_by_count"),
                open_access_status=open_access_status,
                raw_metadata=work,
            )

        except Exception:
            self.logger.exception("Failed to parse OpenAlex work: %s", work.get("id"))
            return None


def _strip_doi_prefix(doi: str) -> str:
    """Remove common URL prefixes from a DOI string."""
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi
