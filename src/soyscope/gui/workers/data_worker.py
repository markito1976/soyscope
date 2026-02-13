"""Background worker for loading findings data into the table view.

Keeps the GUI responsive while pulling potentially large result sets
from SQLite.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class FindingsLoadWorker(BaseWorker):
    """Load a page of findings from the database.

    Parameters:
        db_path: Absolute path to the SQLite database.
        limit: Maximum number of rows to fetch (0 = all).
        offset: Row offset for pagination.

    The ``result`` signal carries a dict with::

        {
            "findings": [...],      # list of finding dicts
            "total_count": int,     # total rows in the table
            "limit": int,
            "offset": int,
        }
    """

    def __init__(
        self,
        db_path: str | Path,
        limit: int = 500,
        offset: int = 0,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.limit = limit
        self.offset = offset

    def execute(self) -> dict[str, Any]:
        from soyscope.db import Database

        self.emit_log(
            f"Loading findings (limit={self.limit}, offset={self.offset})..."
        )
        db = Database(self.db_path)
        db.init_schema()

        findings = db.get_all_findings(limit=self.limit, offset=self.offset)
        total_count = db.get_findings_count()

        try:
            sources_map = db.get_all_finding_sources_map()
        except Exception:
            sources_map = {}

        self.emit_log(
            f"Loaded {len(findings)} findings "
            f"(offset {self.offset}, total {total_count})"
        )
        return {
            "findings": findings,
            "total_count": total_count,
            "limit": self.limit,
            "offset": self.offset,
            "sources_map": sources_map,
        }
