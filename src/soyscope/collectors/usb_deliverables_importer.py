"""Import USB-funded research deliverables from CSV."""

from __future__ import annotations

import asyncio
import csv
import logging
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from ..db import Database
from ..dedup import Deduplicator
from ..models import Paper, SourceType, USBDeliverable

logger = logging.getLogger(__name__)
console = Console()

# Map CSV deliverable types to SourceType
_TYPE_MAP: dict[str, SourceType] = {
    "primary research": SourceType.PAPER,
    "review": SourceType.PAPER,
    "meta analysis": SourceType.PAPER,
    "modeling": SourceType.PAPER,
    "methodology": SourceType.PAPER,
    "response/commentary": SourceType.PAPER,
    "book chapter": SourceType.PAPER,
    "proceedings article": SourceType.CONFERENCE,
    "patent": SourceType.PATENT,
    "survey": SourceType.REPORT,
    "strategic plan": SourceType.REPORT,
}

_DOI_RE = re.compile(r"(10\.\d{4,}/[^\s]+)")


def _clean_no_match(value: str | None) -> str | None:
    """Return None if value is '#NO MATCH' or empty."""
    if not value:
        return None
    v = value.strip()
    if v.upper() == "#NO MATCH" or not v:
        return None
    return v


def _extract_doi(doi_link: str | None) -> str | None:
    """Extract a DOI from a URL or string. Returns None for patents/non-DOI links."""
    if not doi_link:
        return None
    # Skip patent URLs
    if "patents.google.com" in doi_link or "patft.uspto.gov" in doi_link:
        return None
    m = _DOI_RE.search(doi_link)
    if m:
        return m.group(1).rstrip(".,;)")
    return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _map_source_type(deliverable_type: str | None) -> SourceType:
    if not deliverable_type:
        return SourceType.PAPER
    return _TYPE_MAP.get(deliverable_type.strip().lower(), SourceType.PAPER)


class USBDeliverablesImporter:
    """Import USB-funded research deliverables from CSV into SoyScope."""

    def __init__(self, db: Database, unpaywall_email: str | None = None) -> None:
        self.db = db
        self.unpaywall_email = unpaywall_email

    def _parse_row(self, row: dict[str, str]) -> USBDeliverable:
        """Parse a CSV row into a USBDeliverable model."""
        # Consolidate USB project numbers from multiple columns
        usb_nums = []
        for col in ("USB Project Number Lookup", "USB #", "Project Number"):
            v = _clean_no_match(row.get(col))
            if v and v not in usb_nums:
                usb_nums.append(v)
        usb_project_number = "; ".join(usb_nums) if usb_nums else None

        # Split keywords on comma/semicolon
        raw_kw = row.get("Keywords", "")
        keywords = [k.strip() for k in re.split(r"[,;/]", raw_kw) if k.strip()] if raw_kw else []

        return USBDeliverable(
            title=row.get("Title", "").strip(),
            doi_link=row.get("DOI Link", "").strip() or None,
            deliverable_type=_clean_no_match(row.get("Type")),
            submitted_year=_parse_int(row.get("Submitted Year")),
            published_year=_parse_int(row.get("Published Year")),
            month=row.get("Month", "").strip() or None,
            journal_name=row.get("Journal Name", "").strip() or None,
            authors=row.get("Authors", "").strip() or None,
            combined_authors=row.get("Combined Authors", "").strip() or None,
            funders=row.get("Funders", "").strip() or None,
            usb_project_number=usb_project_number,
            investment_category=_clean_no_match(row.get("Investment Category")),
            key_categories=_clean_no_match(row.get("Key Categories")),
            keywords=keywords,
            pi_name=row.get("PI Name", "").strip() or None,
            pi_email=row.get("PI Email", "").strip() or None,
            organization=row.get("Organization", "").strip() or None,
            priority_area=_clean_no_match(row.get("Priority Area")),
            raw_csv_row=dict(row),
        )

    def _create_paper_from_deliverable(self, deliverable: USBDeliverable) -> Paper:
        """Create a Paper/Finding from a USB deliverable for the unified findings table."""
        doi = _extract_doi(deliverable.doi_link)
        source_type = _map_source_type(deliverable.deliverable_type)

        # Build authors list
        authors: list[str] = []
        author_str = deliverable.combined_authors or deliverable.authors
        if author_str:
            authors = [a.strip() for a in author_str.split(",") if a.strip()]

        year = deliverable.published_year or deliverable.submitted_year

        return Paper(
            title=deliverable.title,
            year=year,
            doi=doi,
            url=deliverable.doi_link,
            authors=authors,
            venue=deliverable.journal_name,
            source_api="usb_deliverables",
            source_type=source_type,
            raw_metadata={
                "usb_project_number": deliverable.usb_project_number,
                "investment_category": deliverable.investment_category,
                "key_categories": deliverable.key_categories,
                "priority_area": deliverable.priority_area,
                "pi_name": deliverable.pi_name,
                "organization": deliverable.organization,
                "funders": deliverable.funders,
            },
        )

    async def import_from_csv(self, csv_path: Path, resolve_oa: bool = True) -> dict[str, Any]:
        """Import USB deliverables from CSV.

        Returns summary dict with counts of imported, skipped, etc.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Start a search run
        run_id = self.db.start_search_run("import-usb-deliverables")

        # Load deduplicator with existing data (including DOI-to-ID for source tracking)
        dedup = Deduplicator()
        existing_dois = self.db.get_existing_dois()
        existing_titles = self.db.get_existing_titles()
        doi_to_id = self.db.get_doi_to_id_map()
        dedup.load_existing(existing_dois, existing_titles, doi_to_id=doi_to_id)

        # Read CSV
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        raw_imported = 0
        raw_skipped = 0
        findings_added = 0
        findings_skipped = 0
        oa_pairs: list[tuple[int, str]] = []  # (finding_id, doi) for Unpaywall

        console.print(f"Importing [bold]{total}[/bold] USB deliverables from [bold]{csv_path.name}[/bold]...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task = progress.add_task("Importing deliverables", total=total)

            for row in rows:
                try:
                    # Parse raw CSV row into USBDeliverable
                    deliverable = self._parse_row(row)
                    if not deliverable.title:
                        raw_skipped += 1
                        progress.update(task, advance=1)
                        continue

                    # Insert into usb_deliverables table (raw record)
                    raw_id = self.db.insert_usb_deliverable(deliverable)
                    if raw_id is None:
                        raw_skipped += 1
                    else:
                        raw_imported += 1

                    # Create Paper for unified findings table
                    paper = self._create_paper_from_deliverable(deliverable)

                    # Dedup check (track source even on duplicates)
                    is_dup, existing_id = dedup.is_duplicate(paper)
                    if is_dup:
                        if existing_id and paper.source_api:
                            self.db.add_finding_source(existing_id, paper.source_api)
                        findings_skipped += 1
                        progress.update(task, advance=1)
                        continue

                    # Insert finding
                    finding_id = self.db.insert_finding(paper)
                    if finding_id is not None:
                        findings_added += 1
                        dedup.register(paper, finding_id)

                        # Tag keywords
                        for kw in deliverable.keywords:
                            tag_id = self.db.insert_tag(kw.lower())
                            self.db.link_finding_tag(finding_id, tag_id)

                        # Collect DOI for Unpaywall resolution
                        if paper.doi:
                            oa_pairs.append((finding_id, paper.doi))
                    else:
                        findings_skipped += 1

                except Exception as e:
                    logger.warning("Failed to import row: %s", e)
                    raw_skipped += 1

                progress.update(task, advance=1)

        # Unpaywall OA resolution
        oa_resolved = 0
        if resolve_oa and oa_pairs and self.unpaywall_email:
            oa_resolved = await self._resolve_oa(oa_pairs)

        # Complete search run
        self.db.complete_search_run(
            run_id,
            queries_executed=1,
            findings_added=findings_added,
            findings_updated=oa_resolved,
        )

        summary = {
            "total_rows": total,
            "raw_imported": raw_imported,
            "raw_skipped": raw_skipped,
            "findings_added": findings_added,
            "findings_skipped": findings_skipped,
            "oa_resolved": oa_resolved,
            "dois_for_oa": len(oa_pairs),
        }

        console.print(f"\n[bold]Import complete:[/bold]")
        console.print(f"  Raw records: {raw_imported} imported, {raw_skipped} skipped (duplicates)")
        console.print(f"  Findings: {findings_added} added, {findings_skipped} skipped (dedup)")
        console.print(f"  Unpaywall OA: {oa_resolved}/{len(oa_pairs)} DOIs resolved")

        return summary

    async def _resolve_oa(self, oa_pairs: list[tuple[int, str]]) -> int:
        """Resolve OA links via Unpaywall for a list of (finding_id, doi) pairs."""
        from ..sources.unpaywall_source import UnpaywallSource

        unpaywall = UnpaywallSource(email=self.unpaywall_email)
        resolved = 0

        console.print(f"\nResolving OA links for [bold]{len(oa_pairs)}[/bold] DOIs via Unpaywall...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task = progress.add_task("Unpaywall OA resolution", total=len(oa_pairs))

            for finding_id, doi in oa_pairs:
                try:
                    paper = await unpaywall.get_by_doi(doi)
                    if paper and (paper.pdf_url or paper.open_access_status):
                        oa_status = paper.open_access_status.value if paper.open_access_status else None
                        self.db.update_finding_oa(finding_id, paper.pdf_url, oa_status)
                        resolved += 1
                except Exception as e:
                    logger.debug("Unpaywall failed for DOI %s: %s", doi, e)

                # Rate limit: 0.5s between requests
                await asyncio.sleep(0.5)
                progress.update(task, advance=1)

        console.print(f"  Unpaywall resolved {resolved}/{len(oa_pairs)} DOIs")
        return resolved
