"""Background worker for AI enrichment of findings.

Mirrors the logic in ``soyscope.cli.enrich`` but runs on a
QThreadPool thread and emits Qt signals for progress.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class EnrichmentWorker(BaseWorker):
    """Run enrichment tiers on a background thread.

    Parameters:
        db_path: Absolute path to the SQLite database.
        tier: Which tier to run (0 = all, 1 = catalog, 2 = summary,
              3 = deep).
        limit: Maximum number of findings to process per tier
               (0 = use defaults).
    """

    def __init__(
        self,
        db_path: str | Path,
        tier: int = 0,
        limit: int = 0,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.tier = tier
        self.limit = limit

    def execute(self) -> dict[str, Any]:
        from soyscope.config import get_settings
        from soyscope.db import Database
        from soyscope.enrichment.batch_enricher import BatchEnricher

        self.emit_log("Initializing enrichment pipeline...")
        settings = get_settings()
        db = Database(self.db_path)
        db.init_schema()

        # Build optional AI components
        classifier = None
        summarizer = None
        if settings.apis["claude"].enabled and settings.apis["claude"].api_key:
            from soyscope.enrichment.classifier import Classifier
            from soyscope.enrichment.summarizer import Summarizer
            classifier = Classifier(api_key=settings.apis["claude"].api_key)
            summarizer = Summarizer(api_key=settings.apis["claude"].api_key)
            self.emit_log("Claude AI classifier + summarizer enabled")
        else:
            self.emit_log(
                "No ANTHROPIC_API_KEY configured; Tier 2/3 will be skipped"
            )

        enricher = BatchEnricher(
            db=db,
            classifier=classifier,
            summarizer=summarizer,
            settings=settings,
        )

        tier_label = f"tier {self.tier}" if self.tier else "all tiers"
        self.emit_log(f"Running enrichment ({tier_label}, limit={self.limit})...")
        self.emit_progress(0, 1, f"Running enrichment ({tier_label})...")

        if self.tier == 0:
            result = asyncio.run(
                enricher.run_all_tiers(
                    tier1_limit=self.limit,
                    tier2_limit=self.limit,
                    tier3_limit=min(self.limit or 50, 50),
                )
            )
        elif self.tier == 1:
            count = asyncio.run(enricher.enrich_tier1_catalog(limit=self.limit))
            result = {"tier1": count}
        elif self.tier == 2:
            count = asyncio.run(enricher.enrich_tier2_summary(limit=self.limit))
            result = {"tier2": count}
        elif self.tier == 3:
            count = asyncio.run(enricher.enrich_tier3_deep(limit=self.limit))
            result = {"tier3": count}
        else:
            raise ValueError(f"Invalid tier: {self.tier}. Use 0 (all), 1, 2, or 3.")

        self.emit_progress(1, 1, "Enrichment complete")
        self.emit_log(f"Enrichment result: {result}")
        return result
