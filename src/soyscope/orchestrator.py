"""Multi-API parallel search orchestrator."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from .cache import SearchCache
from .circuit_breaker import CircuitBreakerRegistry, circuit_breakers
from .config import Settings, get_settings
from .db import Database
from .dedup import Deduplicator, deduplicate_papers, normalize_doi, normalize_title
from .models import Paper
from .ranking import reciprocal_rank_fusion
from .rate_limit import RateLimiterRegistry, rate_limiters
from .sources.base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


def _paper_key(paper: Paper) -> str:
    """Stable dedup key for cross-source attribution."""
    ndoi = normalize_doi(paper.doi)
    if ndoi:
        return f"doi:{ndoi}"
    return f"title:{normalize_title(paper.title)}"


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
        active_targets: list[str] = []

        for name in targets:
            if name not in self.sources:
                logger.warning(f"Source '{name}' not registered, skipping")
                continue
            if not self.breakers.is_available(name):
                logger.warning(f"Circuit breaker open for '{name}', skipping")
                continue
            active_targets.append(name)
            tasks.append(self._search_one(name, query, max_results, year_start, year_end, use_cache))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        ranked_lists: list[list[Paper]] = []
        for name, result in zip(active_targets, results):
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

        Records all API sources that discover a paper (multi-source tracking).
        Returns (new_count, updated_count).
        """
        targets = source_names or list(self.sources.keys())
        tasks = []
        active_targets: list[str] = []

        for name in targets:
            if name not in self.sources:
                logger.warning(f"Source '{name}' not registered, skipping")
                continue
            if not self.breakers.is_available(name):
                logger.warning(f"Circuit breaker open for '{name}', skipping")
                continue
            active_targets.append(name)
            tasks.append(self._search_one(name, query, max_results, year_start, year_end, True))

        if not tasks:
            return 0, 0

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect per-source ranked lists and attribution for each dedup key.
        ranked_lists: list[list[Paper]] = []
        key_sources: dict[str, set[str]] = defaultdict(set)
        for name, result in zip(active_targets, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {name}: {result}")
                self.breakers.get(name).record_failure()
                continue
            if result.papers:
                ranked_lists.append(result.papers)
                for paper in result.papers:
                    key_sources[_paper_key(paper)].add(name)
                self.breakers.get(name).record_success()
                logger.info(f"{name}: {len(result.papers)} results for '{query}'")

        if not ranked_lists:
            return 0, 0

        # Merge with RRF
        merged = reciprocal_rank_fusion(ranked_lists)

        # Load dedup state with DOI-to-ID mapping for source tracking
        existing_dois = self.db.get_existing_dois()
        existing_titles = self.db.get_existing_titles()
        doi_to_id = self.db.get_doi_to_id_map()

        dedup = Deduplicator()
        dedup.load_existing(existing_dois, existing_titles, doi_to_id=doi_to_id)

        new_count = 0
        updated_count = 0

        for paper in merged:
            sources_for_paper = key_sources.get(_paper_key(paper), set())
            if not sources_for_paper and paper.source_api:
                sources_for_paper = {paper.source_api}

            is_dup, existing_id = dedup.is_duplicate(paper)

            if is_dup:
                if existing_id:
                    for source in sources_for_paper:
                        self.db.add_finding_source(existing_id, source)
                updated_count += 1
            else:
                result_id = self.db.insert_finding(paper)
                if result_id is not None:
                    new_count += 1
                    for source in sources_for_paper:
                        self.db.add_finding_source(result_id, source)
                    dedup.register(paper, result_id)
                else:
                    updated_count += 1
                    if paper.doi:
                        existing = self.db.get_finding_by_doi(paper.doi)
                        if existing:
                            for source in sources_for_paper:
                                self.db.add_finding_source(existing["id"], source)

        # Log query
        if run_id is not None:
            self.db.log_search_query(
                run_id=run_id,
                query_text=query,
                api_source=",".join(targets),
                results_returned=len(merged),
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
