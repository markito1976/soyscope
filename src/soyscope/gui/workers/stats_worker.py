"""Background worker for loading database statistics.

Runs all the aggregation queries on a background thread so the GUI
stays responsive while SQLite crunches numbers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class StatsWorker(BaseWorker):
    """Load comprehensive database statistics.

    Parameters:
        db_path: Absolute path to the SQLite database.

    The ``result`` signal carries a dict identical to the one returned
    by :meth:`soyscope.db.Database.get_stats`, augmented with
    ``findings_sample`` (a small list of recent findings for preview).
    """

    def __init__(self, db_path: str | Path) -> None:
        super().__init__()
        self.db_path = Path(db_path)

    def execute(self) -> dict[str, Any]:
        from soyscope.db import Database

        self.emit_log("Loading database statistics...")
        db = Database(self.db_path)
        db.init_schema()

        stats = db.get_stats()

        # Attach a small sample of recent findings for quick preview
        findings_sample = db.get_all_findings(limit=25, offset=0)
        stats["findings_sample"] = findings_sample

        # Also include raw table counts that are useful for the GUI
        # dashboard but not part of the standard get_stats() output.
        stats["findings_count"] = stats.get("total_findings", 0)
        stats["checkoff_count"] = stats.get("total_checkoff", 0)
        stats["usb_deliverables_count"] = stats.get("total_usb_deliverables", 0)
        stats["enriched_count"] = stats.get("total_enriched", 0)

        self.emit_log(
            f"Stats loaded: {stats['total_findings']} findings, "
            f"{stats['total_enriched']} enriched, "
            f"{stats['total_checkoff']} checkoff, "
            f"{stats['total_usb_deliverables']} USB deliverables"
        )
        return stats
