"""Tavily web search API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from tavily import TavilyClient

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


class TavilySource(BaseSource):
    """Adapter for the Tavily web search API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client: TavilyClient | None = (
            TavilyClient(api_key=api_key) if api_key else None
        )
        super().__init__(api_key=api_key)

    @property
    def name(self) -> str:
        return "tavily"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search Tavily using advanced web search.

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
        SearchResult with papers converted from Tavily results.
        """
        if self.client is None:
            self.logger.error("Tavily client not initialized (no API key provided)")
            return SearchResult(
                papers=[], total_results=0, query=query, api_source="tavily"
            )

        try:
            results = await asyncio.to_thread(
                self._search_sync, query, max_results, year_start, year_end
            )
            return results
        except Exception:
            self.logger.exception("Tavily search failed for query: %s", query)
            return SearchResult(
                papers=[], total_results=0, query=query, api_source="tavily"
            )

    def _search_sync(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> SearchResult:
        """Synchronous search implementation called via asyncio.to_thread."""
        modified_query = query
        if year_start is not None or year_end is not None:
            start = year_start if year_start is not None else ""
            end = year_end if year_end is not None else ""
            modified_query = f"{query} {start}-{end}"

        try:
            response = self.client.search(  # type: ignore[union-attr]
                query=modified_query,
                max_results=min(max_results, 20),
                search_depth="advanced",
                include_raw_content=False,
            )
        except Exception:
            self.logger.exception(
                "Tavily API call failed for query: %s", modified_query
            )
            return SearchResult(
                papers=[], total_results=0, query=query, api_source="tavily"
            )

        papers: list[Paper] = []
        results = response.get("results", [])

        for result in results:
            title = result.get("title", "") or ""
            content = result.get("content", "") or ""
            url = result.get("url", "") or ""
            score = result.get("score")

            # Truncate content to first 2000 chars for abstract
            abstract = content[:2000] if content else None

            # Try to extract year from content or URL using regex
            year = self._extract_year(content, url)

            # Determine source type from URL
            source_type = self._determine_source_type(url)

            paper = Paper(
                title=title,
                abstract=abstract,
                url=url or None,
                year=year,
                source_api="tavily",
                source_type=source_type,
                raw_metadata={"score": score} if score is not None else {},
            )
            papers.append(paper)

        return SearchResult(
            papers=papers,
            total_results=len(results),
            query=query,
            api_source="tavily",
        )

    @staticmethod
    def _extract_year(content: str, url: str) -> int | None:
        """Try to extract a publication year from content or URL."""
        # Look for 4-digit years in a reasonable range
        year_pattern = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")

        # Try content first
        if content:
            match = year_pattern.search(content)
            if match:
                return int(match.group(1))

        # Fall back to URL
        if url:
            match = year_pattern.search(url)
            if match:
                return int(match.group(1))

        return None

    @staticmethod
    def _determine_source_type(url: str) -> SourceType:
        """Determine the source type based on URL patterns."""
        url_lower = url.lower()

        if "patent" in url_lower:
            return SourceType.PATENT

        if any(domain in url_lower for domain in NEWS_DOMAINS):
            return SourceType.NEWS

        if ".gov" in url_lower:
            return SourceType.GOVT_REPORT

        return SourceType.REPORT

    async def get_by_doi(self, doi: str) -> Paper | None:
        """DOI lookup is not supported by Tavily."""
        return None
