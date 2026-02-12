"""Multi-API parallel search orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .cache import SearchCache
from .circuit_breaker import CircuitBreakerRegistry, circuit_breakers
from .config import Settings, get_settings
from .db import Database
from .dedup import Deduplicator, deduplicate_papers
from .models import Paper
from .ranking import reciprocal_rank_fusion
from .rate_limit import RateLimiterRegistry, rate_limiters
from .sources.base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orchestrates parallel searches across multiple API sources."""

    def __init__(
        self,
        sources: list[BaseSource],
        db: Database,
        cache: SearchCache,
        settings: Settings | None = None,
        limiters: RateLimiterRegistry | None = None,
        breakers: CircuitBreakerRegistry | None = None,
    ) -> None:
        self.sources = {s.name: s for s in sources}
        self.db = db
        self.cache = cache
        self.settings = settings or get_settings()
        self.limiters = limiters or rate_limiters
        self.breakers = breakers or circuit_breakers

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        source_names: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[Paper]:
        """Search across all (or specified) sources and return deduplicated, ranked results."""

        targets = source_names or list(self.sources.keys())
        tasks = []

        for name in targets:
            if name not in self.sources:
                logger.warning(f"Source '{name}' not registered, skipping")
                continue
            if not self.breakers.is_available(name):
                logger.warning(f"Circuit breaker open for '{name}', skipping")
                continue
            tasks.append(self._search_one(name, query, max_results, year_start, year_end, use_cache))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        ranked_lists: list[list[Paper]] = []
        for name, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {name}: {result}")
                self.breakers.get(name).record_failure()
                continue
            if result.papers:
                ranked_lists.append(result.papers)
                self.breakers.get(name).record_success()
                logger.info(f"{name}: {len(result.papers)} results for '{query}'")

        if not ranked_lists:
            return []

        # Merge with RRF
        merged = reciprocal_rank_fusion(ranked_lists)

        # Deduplicate against existing DB
        existing_dois = self.db.get_existing_dois()
        existing_titles = self.db.get_existing_titles()
        unique = deduplicate_papers(merged, existing_dois, existing_titles)

        logger.info(f"Merged: {len(merged)} total, {len(unique)} new unique papers for '{query}'")
        return unique

    async def _search_one(
        self,
        source_name: str,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
        use_cache: bool,
    ) -> SearchResult:
        """Search a single source with rate limiting and caching."""

        # Check cache
        if use_cache:
            cached = self.cache.get(source_name, query, {"year_start": year_start, "year_end": year_end})
            if cached is not None:
                logger.debug(f"Cache hit for {source_name}: '{query}'")
                return cached

        # Rate limit
        await self.limiters.acquire(source_name)

        # Record circuit breaker call
        self.breakers.get(source_name).record_call()

        # Execute search
        source = self.sources[source_name]
        result = await source.search(
            query=query,
            max_results=max_results,
            year_start=year_start,
            year_end=year_end,
        )

        # Cache result
        if use_cache and result.papers:
            self.cache.set(source_name, query, result, {"year_start": year_start, "year_end": year_end})

        return result

    async def search_and_store(
        self,
        query: str,
        run_id: int | None = None,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        source_names: list[str] | None = None,
    ) -> tuple[int, int]:
        """Search, deduplicate, and store results in the database.

        Returns (new_count, updated_count).
        """
        papers = await self.search(query, max_results, year_start, year_end, source_names)

        new_count = 0
        updated_count = 0

        for paper in papers:
            result_id = self.db.insert_finding(paper)
            if result_id is not None:
                new_count += 1
            else:
                updated_count += 1

        # Log query
        if run_id is not None:
            total_results = new_count + updated_count
            self.db.log_search_query(
                run_id=run_id,
                query_text=query,
                api_source=",".join(source_names or list(self.sources.keys())),
                results_returned=len(papers),
                new_findings=new_count,
            )

        return new_count, updated_count

    async def enrich_dois_with_unpaywall(self, dois: list[str]) -> int:
        """Use Unpaywall to find PDF URLs for DOIs that don't have them."""
        if "unpaywall" not in self.sources:
            return 0

        unpaywall = self.sources["unpaywall"]
        enriched = 0

        for doi in dois:
            await self.limiters.acquire("unpaywall")
            paper = await unpaywall.get_by_doi(doi)
            if paper and paper.pdf_url:
                with self.db.connect() as conn:
                    conn.execute(
                        "UPDATE findings SET pdf_url = ? WHERE doi = ? AND pdf_url IS NULL",
                        (paper.pdf_url, doi),
                    )
                enriched += 1

        return enriched
