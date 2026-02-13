"""Background workers for data import operations.

Each worker creates its own :class:`Database` instance from *db_path*
because SQLite connections are not safe to share across threads.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)


class CheckoffImportWorker(BaseWorker):
    """Import Soybean Checkoff Research DB projects from a JSON file.

    Parameters:
        db_path: Absolute path to the SQLite database.
        json_path: Path to the JSON file produced by soybean_scraper.
    """

    def __init__(self, db_path: str | Path, json_path: str | Path) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.json_path = Path(json_path)

    def execute(self) -> dict[str, Any]:
        from soyscope.db import Database
        from soyscope.collectors.checkoff_importer import CheckoffImporter
        from soyscope.models import CheckoffProject, Paper, SourceType

        self.emit_log(f"Opening database: {self.db_path}")
        db = Database(self.db_path)
        db.init_schema()

        self.emit_log(f"Loading JSON file: {self.json_path}")
        with open(self.json_path, encoding="utf-8") as f:
            data = json.load(f)

        # Normalise to a list (mirrors CheckoffImporter._parse logic)
        if isinstance(data, dict):
            if "projects" in data:
                projects_raw = data["projects"]
            elif "results" in data:
                projects_raw = data["results"]
            else:
                projects_raw = [data]
        elif isinstance(data, list):
            projects_raw = data
        else:
            raise ValueError(f"Unexpected data format in {self.json_path}")

        total = len(projects_raw)
        self.emit_log(f"Found {total} records to import")
        self.emit_progress(0, total, "Starting checkoff import...")

        importer = CheckoffImporter(db=db)
        imported = 0
        parse_errors = 0
        batch_size = 500

        for chunk_start in range(0, total, batch_size):
            if self.is_cancelled:
                self.emit_log("Import cancelled by user.")
                break

            chunk = projects_raw[chunk_start : chunk_start + batch_size]
            parsed_projects: list = []
            parsed_papers: list = []

            for item in chunk:
                try:
                    project = importer._parse_project(item)
                    parsed_projects.append(project)
                    paper = importer._paper_from_project(project)
                    if paper is not None:
                        parsed_papers.append(paper)
                except Exception as exc:
                    logger.warning("Failed to parse checkoff project: %s", exc)
                    parse_errors += 1

            chunk_imported = db.insert_checkoff_projects_batch(parsed_projects)
            imported += chunk_imported

            if parsed_papers:
                db.insert_findings_batch(parsed_papers)

            processed = min(chunk_start + len(chunk), total)
            self.emit_progress(
                processed, total,
                f"Imported {imported} projects ({parse_errors} errors)",
            )

        summary = {
            "total_records": total,
            "imported": imported,
            "parse_errors": parse_errors,
        }
        self.emit_log(
            f"Checkoff import complete: {imported}/{total} imported, "
            f"{parse_errors} parse errors"
        )
        return summary


class USBDeliverablesImportWorker(BaseWorker):
    """Import USB-funded research deliverables from a CSV file.

    Parameters:
        db_path: Absolute path to the SQLite database.
        csv_path: Path to the USB deliverables CSV.
        unpaywall_email: Email for Unpaywall API (None to skip OA).
        resolve_oa: Whether to resolve Open Access links via Unpaywall.
    """

    def __init__(
        self,
        db_path: str | Path,
        csv_path: str | Path,
        unpaywall_email: str | None = None,
        resolve_oa: bool = True,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.csv_path = Path(csv_path)
        self.unpaywall_email = unpaywall_email
        self.resolve_oa = resolve_oa

    def execute(self) -> dict[str, Any]:
        from soyscope.db import Database
        from soyscope.collectors.usb_deliverables_importer import USBDeliverablesImporter

        self.emit_log(f"Opening database: {self.db_path}")
        db = Database(self.db_path)
        db.init_schema()

        self.emit_log(f"Importing USB deliverables from: {self.csv_path}")
        self.emit_progress(0, 1, "Running USB deliverables import (async)...")

        importer = USBDeliverablesImporter(
            db=db,
            unpaywall_email=self.unpaywall_email,
        )

        # The importer is async — run it via asyncio.run() on this
        # background thread (which has no running event loop).
        result = asyncio.run(
            importer.import_from_csv(
                csv_path=self.csv_path,
                resolve_oa=self.resolve_oa,
            )
        )

        self.emit_progress(1, 1, "USB deliverables import complete")
        self.emit_log(
            f"USB import done: {result.get('findings_added', 0)} findings added, "
            f"{result.get('raw_imported', 0)} raw records imported, "
            f"{result.get('oa_resolved', 0)} OA resolved"
        )
        return result
