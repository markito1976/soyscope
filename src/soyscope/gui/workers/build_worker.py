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

        # Rich progress callback: forward data dicts to the GUI via
        # the build_progress signal.  Qt signals are thread-safe, and
        # asyncio.run() blocks this worker thread, so direct emission
        # from the async context is safe.
        def _on_build_progress(data: dict) -> None:
            self.signals.build_progress.emit(data)
            # Also update the simpler progress signal for progress bars
            if data.get("event") == "query_complete":
                completed = data.get("completed", 0)
                total = data.get("total", 1)
                msg = (
                    f"Query {completed}/{total}: "
                    f"+{data.get('new_findings', 0)} new, "
                    f"+{data.get('updated_findings', 0)} updated"
                )
                self.emit_progress(completed, total, msg)
            elif data.get("event") == "build_started":
                total = data.get("total_queries", 0)
                src_count = len(data.get("sources", []))
                self.emit_log(
                    f"Build started: {total} queries across {src_count} sources"
                )
                self.emit_progress(0, total, "Build started...")

        result = asyncio.run(
            builder.build(
                concurrency=self.concurrency,
                max_queries=self.max_queries,
                progress_callback=_on_build_progress,
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

        # --- Tier 1 sources ---
        if api_cfg["osti"].enabled:
            from soyscope.sources.osti_source import OSTISource
            sources.append(OSTISource())

        if api_cfg["patentsview"].enabled:
            from soyscope.sources.patentsview_source import PatentsViewSource
            sources.append(PatentsViewSource(api_key=api_cfg["patentsview"].api_key))

        if api_cfg["sbir"].enabled:
            from soyscope.sources.sbir_source import SBIRSource
            sources.append(SBIRSource())

        if api_cfg["agris"].enabled:
            from soyscope.sources.agris_source import AGRISSource
            sources.append(AGRISSource())

        if api_cfg["lens"].enabled and api_cfg["lens"].api_key:
            from soyscope.sources.lens_source import LensSource
            sources.append(LensSource(api_key=api_cfg["lens"].api_key))

        if api_cfg["usda_ers"].enabled:
            from soyscope.sources.usda_ers_source import USDAERSSource
            sources.append(USDAERSSource(api_key=api_cfg["usda_ers"].api_key))

        return sources
