"""Background worker for incremental refresh runs."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class RefreshWorker(BaseWorker):
    """Run incremental refresh in a background thread."""

    def __init__(
        self,
        db_path: str | Path,
        since: str | None = None,
        concurrency: int = 3,
        max_queries: int | None = None,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.since = since
        self.concurrency = concurrency
        self.max_queries = max_queries

    def execute(self) -> dict[str, Any]:
        from soyscope.cache import SearchCache
        from soyscope.circuit_breaker import setup_circuit_breakers
        from soyscope.collectors.refresh_runner import RefreshRunner
        from soyscope.config import get_settings
        from soyscope.db import Database
        from soyscope.orchestrator import SearchOrchestrator
        from soyscope.rate_limit import setup_rate_limiters

        self.emit_log("Initializing refresh pipeline...")
        settings = get_settings()
        db = Database(self.db_path)
        db.init_schema()

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
        runner = RefreshRunner(orchestrator=orchestrator, db=db, settings=settings)

        self.emit_progress(0, 1, "Running incremental refresh...")

        def _on_refresh_progress(data: dict) -> None:
            self.signals.build_progress.emit(data)
            if data.get("event") == "query_complete":
                completed = data.get("completed", 0)
                total = data.get("total", 1)
                msg = (
                    f"Refresh {completed}/{total}: "
                    f"+{data.get('new_findings', 0)} new, "
                    f"+{data.get('updated_findings', 0)} updated"
                )
                self.emit_progress(completed, total, msg)
            elif data.get("event") == "build_started":
                total = data.get("total_queries", 0)
                self.emit_progress(0, total, "Refresh started...")

        result = asyncio.run(
            runner.refresh(
                since=self.since,
                concurrency=self.concurrency,
                max_queries=self.max_queries,
                progress_callback=_on_refresh_progress,
            )
        )

        self.emit_progress(1, 1, "Incremental refresh complete")
        self.emit_log(
            f"Refresh done: {result.get('findings_added', 0)} new findings, "
            f"{result.get('findings_updated', 0)} updated"
        )
        return result

    @staticmethod
    def _build_sources(settings):
        """Instantiate all enabled API source adapters."""
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

        if api_cfg["core"].enabled:
            from soyscope.sources.core_source import CoreSource
            sources.append(CoreSource(api_key=api_cfg["core"].api_key))

        if api_cfg["unpaywall"].enabled and api_cfg["unpaywall"].email:
            from soyscope.sources.unpaywall_source import UnpaywallSource
            sources.append(UnpaywallSource(email=api_cfg["unpaywall"].email))

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
