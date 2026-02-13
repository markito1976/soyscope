"""Import from soybean_scraper data (Soybean Checkoff Research DB)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from ..db import Database
from ..models import CheckoffProject, Paper, SourceType

logger = logging.getLogger(__name__)
console = Console()

# Known locations for soybean_scraper data
SCRAPER_PATHS = [
    Path(r"C:\EvalToolVersions\soybean_scraper\data"),
    Path(r"C:\EvalToolVersions\soybean_scraper\output"),
    Path(r"C:\EvalToolVersions\soybean_scraper"),
]


class CheckoffImporter:
    """Import Soybean Checkoff Research DB projects."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def find_scraper_data(self) -> list[Path]:
        """Find all JSON/CSV data files from the soybean_scraper project."""
        found: list[Path] = []
        for base in SCRAPER_PATHS:
            if not base.exists():
                continue
            found.extend(base.glob("*.json"))
            found.extend(base.glob("**/*.json"))
        # Deduplicate
        return list({p.resolve() for p in found})

    def import_from_json(self, json_path: Path) -> int:
        """Import projects from a JSON file.

        Supports both array-of-objects and single-object formats.
        Returns number of projects imported.
        """
        console.print(f"Importing from [bold]{json_path}[/bold]...")

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Could be {projects: [...]} or a single project
            if "projects" in data:
                projects = data["projects"]
            elif "results" in data:
                projects = data["results"]
            else:
                projects = [data]
        elif isinstance(data, list):
            projects = data
        else:
            logger.warning(f"Unexpected data format in {json_path}")
            return 0

        imported = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task = progress.add_task("Importing checkoff projects", total=len(projects))

            for item in projects:
                try:
                    project = self._parse_project(item)
                    result = self.db.insert_checkoff_project(project)
                    if result is not None:
                        imported += 1
                        # Also create a Finding entry for cross-referencing
                        self._create_finding_from_project(project)
                except Exception as e:
                    logger.warning(f"Failed to import project: {e}")
                progress.update(task, advance=1)

        console.print(f"  Imported [bold]{imported}[/bold] of {len(projects)} projects")
        return imported

    def import_all(self) -> dict[str, Any]:
        """Find and import all available scraper data."""
        files = self.find_scraper_data()
        if not files:
            console.print("[yellow]No soybean_scraper data files found.[/yellow]")
            console.print("Expected data in one of:")
            for p in SCRAPER_PATHS:
                console.print(f"  {p}")
            return {"files_found": 0, "total_imported": 0}

        console.print(f"Found [bold]{len(files)}[/bold] data files")
        total_imported = 0
        for f in files:
            try:
                count = self.import_from_json(f)
                total_imported += count
            except Exception as e:
                logger.error(f"Failed to import {f}: {e}")

        return {"files_found": len(files), "total_imported": total_imported}

    def _parse_project(self, item: dict[str, Any]) -> CheckoffProject:
        """Parse a raw JSON object into a CheckoffProject."""
        keywords = item.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        funding = (item.get("checkoff_funding") or item.get("funding")
                   or item.get("total_funding") or item.get("amount"))
        if isinstance(funding, str):
            funding = float(funding.replace("$", "").replace(",", "")) if funding.strip() else None

        summary = (item.get("brief_summary") or item.get("project_summary")
                   or item.get("summary") or item.get("description") or item.get("abstract", ""))

        return CheckoffProject(
            year=str(item.get("year", "")),
            title=item.get("title") or item.get("project_title", ""),
            category=item.get("category") or item.get("research_area", ""),
            keywords=keywords,
            lead_pi=item.get("lead_pi") or item.get("pi") or item.get("principal_investigator", ""),
            institution=(item.get("lead_pi_institution") or item.get("institution")
                         or item.get("university", "")),
            funding=float(funding) if funding else None,
            summary=summary,
            objectives=item.get("objectives") or item.get("deliverables", ""),
            url=item.get("url") or item.get("link", ""),
        )

    def _create_finding_from_project(self, project: CheckoffProject) -> None:
        """Create a Finding entry from a checkoff project for unified search."""
        if not project.title:
            return

        paper = Paper(
            title=project.title,
            abstract=project.summary or project.objectives,
            year=int(project.year) if project.year and project.year.isdigit() else None,
            url=project.url,
            authors=[project.lead_pi] if project.lead_pi else [],
            venue=project.institution or "Soybean Checkoff Research",
            source_api="checkoff",
            source_type=SourceType.REPORT,
        )
        self.db.insert_finding(paper)
