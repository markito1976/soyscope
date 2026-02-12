"""Crossref API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from habanero import Crossref

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)

# Mapping from Crossref work types to SourceType enum values.
_TYPE_MAP: dict[str, SourceType] = {
    "journal-article": SourceType.PAPER,
    "proceedings-article": SourceType.CONFERENCE,
    "patent": SourceType.PATENT,
    "report": SourceType.REPORT,
    "book-chapter": SourceType.PAPER,
    "book": SourceType.PAPER,
    "posted-content": SourceType.PAPER,
    "monograph": SourceType.PAPER,
    "dissertation": SourceType.PAPER,
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML/JATS tags from a string."""
    return _HTML_TAG_RE.sub("", text).strip()


class CrossrefSource(BaseSource):
    """Search adapter for the Crossref REST API via habanero."""

    def __init__(self, email: str | None = None) -> None:
        if email:
            self.cr = Crossref(mailto=email)
        else:
            self.cr = Crossref()
        super().__init__(email=email)

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "crossref"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search Crossref for works matching *query*."""
        try:
            return await asyncio.to_thread(
                self._search_sync, query, max_results, year_start, year_end
            )
        except Exception:
            self.logger.exception("Crossref search failed for query=%r", query)
            return SearchResult(papers=[], total_results=0, query=query, api_source=self.name)

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Retrieve a single work by DOI."""
        try:
            response = await asyncio.to_thread(self.cr.works, ids=doi)
            item = response["message"]
            return self._parse_item(item)
        except Exception:
            self.logger.exception("Crossref get_by_doi failed for doi=%r", doi)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_sync(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> SearchResult:
        """Synchronous search executed in a thread."""
        filter_dict: dict[str, str] = {}
        if year_start is not None:
            filter_dict["from-pub-date"] = f"{year_start}"
        if year_end is not None:
            filter_dict["until-pub-date"] = f"{year_end}"

        response = self.cr.works(
            query=query,
            limit=min(max_results, 1000),
            filter=filter_dict if filter_dict else None,
        )

        message = response["message"]
        items = message.get("items", [])
        total_results = message.get("total-results", 0)

        papers: list[Paper] = []
        for item in items:
            try:
                paper = self._parse_item(item)
                papers.append(paper)
            except Exception:
                self.logger.debug("Skipping unparseable Crossref item: %s", item.get("DOI", "?"))

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
            raw_response=response,
        )

    def _parse_item(self, item: dict[str, Any]) -> Paper:
        """Convert a single Crossref work item into a :class:`Paper`."""
        # Title
        title_list = item.get("title", [])
        title = title_list[0] if title_list else "Untitled"

        # Abstract (may contain JATS/HTML tags)
        abstract_raw = item.get("abstract", "")
        abstract = _strip_html(abstract_raw) if abstract_raw else ""

        # Year - try published-print first, then published-online
        year = self._extract_year(item)

        # DOI
        doi = item.get("DOI")

        # URL
        url = item.get("URL")

        # Authors
        authors: list[str] = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            full = f"{given} {family}".strip()
            if full:
                authors.append(full)

        # Venue (container-title)
        container = item.get("container-title", [None])
        venue = container[0] if container else None

        # Citation count
        citation_count = item.get("is-referenced-by-count")

        # Source type mapping
        crossref_type = item.get("type", "")
        source_type = _TYPE_MAP.get(crossref_type, SourceType.PAPER)

        return self._make_paper(
            title=title,
            abstract=abstract or None,
            year=year,
            doi=doi,
            url=url,
            authors=authors,
            venue=venue,
            citation_count=citation_count,
            source_type=source_type,
            raw_metadata=item,
        )

    @staticmethod
    def _extract_year(item: dict[str, Any]) -> int | None:
        """Extract publication year from date-parts, trying multiple fields."""
        for key in ("published-print", "published-online"):
            try:
                date_parts = item[key]["date-parts"][0]
                if date_parts and date_parts[0]:
                    return int(date_parts[0])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        return None
