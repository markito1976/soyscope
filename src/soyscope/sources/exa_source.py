"""EXA neural search API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from exa_py import Exa

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)

NEWS_DOMAINS = [
    "reuters.com",
    "bloomberg.com",
    "apnews.com",
    "bbc.com",
    "cnn.com",
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "news.google.com",
    "news.yahoo.com",
]


class ExaSource(BaseSource):
    """Adapter for the EXA neural search API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client: Exa | None = Exa(api_key=api_key) if api_key else None
        super().__init__(api_key=api_key)

    @property
    def name(self) -> str:
        return "exa"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search EXA using neural semantic search.

        Parameters
        ----------
        query:
            The search query string.
        max_results:
            Maximum number of results to return (default 100).
        year_start:
            Filter results published on or after this year.
        year_end:
            Filter results published on or before this year.

        Returns
        -------
        SearchResult with papers converted from EXA results.
        """
        if self.client is None:
            self.logger.error("EXA client not initialized (no API key provided)")
            return SearchResult(papers=[], total_results=0, query=query, api_source="exa")

        search_kwargs: dict[str, Any] = {
            "query": query,
            "num_results": max_results,
            "type": "neural",
            "text": True,
        }

        if year_start is not None:
            search_kwargs["start_published_date"] = f"{year_start}-01-01"
        if year_end is not None:
            search_kwargs["end_published_date"] = f"{year_end}-12-31"

        try:
            response = await asyncio.to_thread(
                self.client.search_and_contents, **search_kwargs
            )
        except Exception:
            self.logger.exception("EXA search failed for query: %s", query)
            return SearchResult(papers=[], total_results=0, query=query, api_source="exa")

        papers: list[Paper] = []
        for result in response.results:
            # Determine source type based on URL
            source_type = SourceType.PAPER
            url = getattr(result, "url", None) or ""
            if any(domain in url for domain in NEWS_DOMAINS):
                source_type = SourceType.NEWS

            # Try to parse year from published_date
            year: int | None = None
            published_date = getattr(result, "published_date", None)
            if published_date:
                try:
                    year = int(str(published_date)[:4])
                except (ValueError, IndexError):
                    pass

            # Truncate text to first 2000 chars for abstract
            text = getattr(result, "text", None) or ""
            abstract = text[:2000] if text else None

            paper = Paper(
                title=getattr(result, "title", "") or "",
                abstract=abstract,
                url=url or None,
                year=year,
                source_api="exa",
                source_type=source_type,
            )
            papers.append(paper)

        return SearchResult(
            papers=papers,
            total_results=len(papers),
            query=query,
            api_source="exa",
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """DOI lookup is not supported by EXA."""
        return None
