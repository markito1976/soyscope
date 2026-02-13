"""Standalone OA resolution via Unpaywall for findings with DOIs."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from ..db import Database
from ..sources.unpaywall_source import UnpaywallSource

logger = logging.getLogger(__name__)


class OAResolver:
    """Resolve Open Access pdf_url and oa_status for findings that have DOIs.

    Parameters:
        db: Database instance.
        email: Email address for Unpaywall API authentication.
        rate_delay: Seconds between requests (default 0.5).
        progress_callback: Optional callable(current, total, message) for GUI.
    """

    def __init__(
        self,
        db: Database,
        email: str,
        rate_delay: float = 0.5,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        self.db = db
        self.email = email
        self.rate_delay = rate_delay
        self.progress_callback = progress_callback
        self._unpaywall = UnpaywallSource(email=email)

    def get_unresolved_dois(self, limit: int = 0) -> list[tuple[int, str]]:
        """Return (finding_id, doi) pairs for findings needing OA resolution."""
        with self.db.connect() as conn:
            q = """SELECT id, doi FROM findings
                   WHERE doi IS NOT NULL AND doi != ''
                   AND (pdf_url IS NULL OR pdf_url = '')"""
            if limit > 0:
                q += f" LIMIT {limit}"
            return [(r[0], r[1]) for r in conn.execute(q).fetchall()]

    async def resolve_all(self, limit: int = 0) -> int:
        """Resolve OA links for all (or limited) unresolved findings.

        Returns the number of findings successfully resolved.
        """
        pairs = self.get_unresolved_dois(limit=limit)
        total = len(pairs)
        if total == 0:
            logger.info("No unresolved DOIs found.")
            return 0

        logger.info("Resolving OA for %d DOIs via Unpaywall...", total)
        resolved = 0

        for i, (finding_id, doi) in enumerate(pairs):
            try:
                paper = await self._unpaywall.get_by_doi(doi)
                if paper and (paper.pdf_url or paper.open_access_status):
                    oa_status = (
                        paper.open_access_status.value
                        if paper.open_access_status
                        else None
                    )
                    self.db.update_finding_oa(finding_id, paper.pdf_url, oa_status)
                    resolved += 1
            except Exception as e:
                logger.debug("Unpaywall failed for DOI %s: %s", doi, e)

            if self.progress_callback:
                self.progress_callback(i + 1, total, f"Resolved {resolved}/{i + 1}")

            if i < total - 1:
                await asyncio.sleep(self.rate_delay)

        logger.info("OA resolution complete: %d/%d resolved", resolved, total)
        return resolved
