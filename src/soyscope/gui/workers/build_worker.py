"""Background worker for the 25-year historical database build.

Mirrors the logic in ``soyscope.cli.build`` but emits Qt signals
instead of writing to a Rich console.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class HistoricalBuildWorker(BaseWorker):
    """Run the full historical build on a background thread.

    Parameters:
        db_path: Absolute path to the SQLite database.
        concurrency: Number of concurrent API queries.
        max_queries: Optional cap on total queries (useful for testing).
    """

    def __init__(
        self,
        db_path: str | Path,
        concurrency: int = 3,
        max_queries: int | None = None,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.concurrency = concurrency
        self.max_queries = max_queries

    def execute(self) -> dict[str, Any]:
        from soyscope.config import get_settings
        from soyscope.db import Database
        from soyscope.cache import SearchCache
        from soyscope.circuit_breaker import setup_circuit_breakers
        from soyscope.orchestrator import SearchOrchestrator
        from soyscope.rate_limit import setup_rate_limiters
        from soyscope.collectors.historical_builder import HistoricalBuilder
        from soyscope.collectors.query_generator import DEFAULT_SECTORS, DEFAULT_DERIVATIVES

        self.emit_log("Initializing database and settings...")
        settings = get_settings()
        db = Database(self.db_path)
        db.init_schema()

        # Seed taxonomy (same as CLI _seed_taxonomy)
        for name in DEFAULT_SECTORS:
            db.insert_sector(name)
        for name in DEFAULT_DERIVATIVES:
            db.insert_derivative(name)

        # Build sources (same pattern as cli._build_sources)
        sources = self._build_sources(settings)

        cache = SearchCache(settings.cache_dir)
        limiters = setup_rate_limiters()
        breakers = setup_circuit_breakers()

        orchestrator = SearchOrchestrator(
            sources=sources,
            db=db,
            cache=cache,
            settings=settings,
            limiters=limiters,
            breakers=breakers,
        )

        builder = HistoricalBuilder(
            orchestrator=orchestrator,
            db=db,
            settings=settings,
        )

        self.emit_log(
            f"Starting historical build (concurrency={self.concurrency}, "
            f"max_queries={self.max_queries})..."
        )
        self.emit_progress(0, 1, "Running historical build (async)...")

        result = asyncio.run(
            builder.build(
                concurrency=self.concurrency,
                max_queries=self.max_queries,
            )
        )

        self.emit_progress(1, 1, "Historical build complete")
        self.emit_log(
            f"Build done: {result.get('findings_added', 0)} new findings, "
            f"{result.get('findings_updated', 0)} updated, "
            f"{result.get('total_queries', 0)} queries in "
            f"{result.get('elapsed_seconds', 0):.1f}s"
        )
        return result

    @staticmethod
    def _build_sources(settings):
        """Instantiate all enabled API source adapters.

        Replicates the logic from ``soyscope.cli._build_sources`` so the
        worker is fully self-contained.
        """
        from soyscope.sources.base import BaseSource

        sources: list[BaseSource] = []
        api_cfg = settings.apis

        if api_cfg["openalex"].enabled:
            from soyscope.sources.openalex_source import OpenAlexSource
            sources.append(OpenAlexSource(email=api_cfg["openalex"].email))

        if api_cfg["semantic_scholar"].enabled:
            from soyscope.sources.semantic_scholar import SemanticScholarSource
            sources.append(SemanticScholarSource(api_key=api_cfg["semantic_scholar"].api_key))

        if api_cfg["exa"].enabled and api_cfg["exa"].api_key:
            from soyscope.sources.exa_source import ExaSource
            sources.append(ExaSource(api_key=api_cfg["exa"].api_key))

        if api_cfg["crossref"].enabled:
            from soyscope.sources.crossref_source import CrossrefSource
            sources.append(CrossrefSource(email=api_cfg["crossref"].email))

        if api_cfg["pubmed"].enabled and api_cfg["pubmed"].email:
            from soyscope.sources.pubmed_source import PubMedSource
            sources.append(PubMedSource(api_key=api_cfg["pubmed"].api_key, email=api_cfg["pubmed"].email))

        if api_cfg["tavily"].enabled and api_cfg["tavily"].api_key:
            from soyscope.sources.tavily_source import TavilySource
            sources.append(TavilySource(api_key=api_cfg["tavily"].api_key))

        if api_cfg["core"].enabled and api_cfg["core"].api_key:
            from soyscope.sources.core_source import CoreSource
            sources.append(CoreSource(api_key=api_cfg["core"].api_key))

        if api_cfg["unpaywall"].enabled and api_cfg["unpaywall"].email:
            from soyscope.sources.unpaywall_source import UnpaywallSource
            sources.append(UnpaywallSource(email=api_cfg["unpaywall"].email))

        return sources
