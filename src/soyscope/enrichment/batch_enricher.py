"""Batch processing of raw findings through the enrichment pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..collectors.query_generator import SECTOR_KEYWORDS
from ..config import Settings, get_settings
from ..db import Database
from ..models import Enrichment, EnrichmentTier
from ..novelty import score_finding_novelty
from .classifier import Classifier
from .novelty_scorer import score_novelty
from .summarizer import Summarizer

logger = logging.getLogger(__name__)
console = Console()


class BatchEnricher:
    """Processes findings through the tiered enrichment pipeline."""

    def __init__(
        self,
        db: Database,
        classifier: Classifier | None = None,
        summarizer: Summarizer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.classifier = classifier
        self.summarizer = summarizer
        self.settings = settings or get_settings()

    async def enrich_tier1_catalog(self, limit: int = 0) -> int:
        """Tier 1: Rule-based cataloging for all un-enriched findings.

        - Keyword-based sector/derivative tagging
        - Novelty scoring (heuristic)
        - No AI cost.
        """
        console.print("[bold]Running Tier 1: Catalog enrichment...[/bold]")
        findings = self.db.get_unenriched_findings(tier="catalog", limit=limit or 10000)

        if not findings:
            console.print("  No un-enriched findings found.")
            return 0

        sectors = self.db.get_all_sectors()
        derivatives = self.db.get_all_derivatives()
        known_apps = self.db.get_all_known_applications()
        use_known_baseline = bool(known_apps)
        sector_names = {s["name"].lower(): s["id"] for s in sectors}
        derivative_names = {d["name"].lower(): d["id"] for d in derivatives}

        enriched = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task = progress.add_task("Tier 1 cataloging", total=len(findings))

            for finding in findings:
                text = f"{finding['title']} {finding.get('abstract', '')}".lower()

                # Keyword-match sectors
                for sname, sid in sector_names.items():
                    keywords = sname.replace("&", "").replace(",", "").split()
                    if any(kw in text for kw in keywords if len(kw) > 3):
                        self.db.link_finding_sector(finding["id"], sid, confidence=0.6)

                # Keyword-match derivatives
                for dname, did in derivative_names.items():
                    keywords = dname.replace("-", " ").split()
                    if any(kw in text for kw in keywords if len(kw) > 3):
                        self.db.link_finding_derivative(finding["id"], did, confidence=0.6)

                # Novelty score:
                # - Primary path: compare against known commercial applications.
                # - Fallback path: heuristic scorer when no known-app baseline exists.
                if use_known_baseline:
                    novelty_result = score_finding_novelty(
                        finding={
                            "id": finding["id"],
                            "title": finding["title"],
                            "abstract": finding.get("abstract"),
                        },
                        known_apps=known_apps,
                        sector_keywords=SECTOR_KEYWORDS,
                    )
                    novelty = round(novelty_result.novelty_score / 100.0, 3)
                else:
                    novelty = score_novelty(
                        title=finding["title"],
                        abstract=finding.get("abstract"),
                        year=finding.get("year"),
                        citation_count=finding.get("citation_count"),
                        source_type=finding.get("source_type"),
                    )

                # Store enrichment
                enrichment = Enrichment(
                    finding_id=finding["id"],
                    tier=EnrichmentTier.CATALOG,
                    novelty_score=novelty,
                )
                self.db.insert_enrichment(enrichment)
                enriched += 1
                progress.update(task, advance=1)

        console.print(f"  Cataloged [bold]{enriched}[/bold] findings")
        return enriched

    async def enrich_tier2_summary(self, limit: int = 0, batch_size: int = 20) -> int:
        """Tier 2: Claude-based batch classification and summarization.

        Processes findings in batches of `batch_size`.
        """
        if not self.classifier:
            console.print("[yellow]No classifier configured (need ANTHROPIC_API_KEY).[/yellow]")
            return 0

        console.print("[bold]Running Tier 2: AI summary enrichment...[/bold]")
        findings = self.db.get_unenriched_findings(tier="summary", limit=limit or 5000)

        if not findings:
            console.print("  No findings need Tier 2 enrichment.")
            return 0

        sectors = [s["name"] for s in self.db.get_all_sectors()]
        derivatives = [d["name"] for d in self.db.get_all_derivatives()]

        enriched = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Tier 2 AI enrichment", total=len(findings))

            for i in range(0, len(findings), batch_size):
                batch = findings[i : i + batch_size]

                try:
                    results = await self.classifier.classify_batch(batch, sectors, derivatives)

                    for result in results:
                        # Link sectors
                        for sector_name in result.sectors:
                            sector = self.db.get_sector_by_name(sector_name)
                            if sector:
                                self.db.link_finding_sector(result.finding_id, sector["id"], confidence=0.85)

                        # Link derivatives
                        for deriv_name in result.derivatives:
                            deriv = self.db.get_derivative_by_name(deriv_name)
                            if deriv:
                                self.db.link_finding_derivative(result.finding_id, deriv["id"], confidence=0.85)

                        # Add new AI-discovered sectors
                        for new_sector in result.new_sectors:
                            self.db.insert_sector(new_sector, is_ai_discovered=True)

                        # Add new AI-discovered derivatives
                        for new_deriv in result.new_derivatives:
                            self.db.insert_derivative(new_deriv, is_ai_discovered=True)

                        # Add tags
                        for tag_name in result.tags:
                            tag_id = self.db.insert_tag(tag_name)
                            self.db.link_finding_tag(result.finding_id, tag_id)

                        # Store enrichment
                        enrichment = Enrichment(
                            finding_id=result.finding_id,
                            tier=EnrichmentTier.SUMMARY,
                            trl_estimate=result.trl_estimate,
                            commercialization_status=result.commercialization_status,
                            novelty_score=result.novelty_score,
                            ai_summary=result.summary,
                            key_metrics=result.key_metrics,
                            key_players=result.key_players,
                            soy_advantage=result.soy_advantage,
                            barriers=result.barriers,
                            model_used=self.classifier.model,
                        )
                        self.db.insert_enrichment(enrichment)
                        enriched += 1

                except Exception as e:
                    logger.error(f"Tier 2 batch failed: {e}")

                progress.update(task, advance=len(batch))

        console.print(f"  AI-enriched [bold]{enriched}[/bold] findings")
        return enriched

    async def enrich_tier3_deep(self, limit: int = 50) -> int:
        """Tier 3: Deep analysis for high-novelty findings.

        Uses Claude Sonnet for detailed market/competitive analysis.
        """
        if not self.summarizer:
            console.print("[yellow]No summarizer configured (need ANTHROPIC_API_KEY).[/yellow]")
            return 0

        console.print("[bold]Running Tier 3: Deep analysis...[/bold]")

        # Get high-novelty findings that haven't had deep analysis
        with self.db.connect() as conn:
            findings = [
                dict(r)
                for r in conn.execute(
                    """SELECT f.*, n.novelty_score FROM findings f
                       JOIN (
                           SELECT finding_id, MAX(novelty_score) AS novelty_score
                           FROM enrichments
                           WHERE tier IN ('catalog', 'summary')
                           GROUP BY finding_id
                       ) n ON f.id = n.finding_id
                       WHERE n.novelty_score >= ?
                         AND NOT EXISTS (
                             SELECT 1 FROM enrichments d
                             WHERE d.finding_id = f.id AND d.tier = 'deep'
                         )
                       ORDER BY n.novelty_score DESC
                       LIMIT ?""",
                    (self.settings.novelty_threshold, limit),
                ).fetchall()
            ]

        if not findings:
            console.print("  No findings qualify for deep analysis.")
            return 0

        enriched = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task = progress.add_task("Tier 3 deep analysis", total=len(findings))

            for finding in findings:
                try:
                    result = await self.summarizer.deep_analyze(finding)
                    if result:
                        enrichment = Enrichment(
                            finding_id=finding["id"],
                            tier=EnrichmentTier.DEEP,
                            trl_estimate=result.get("trl_estimate"),
                            novelty_score=finding.get("novelty_score"),
                            ai_summary=result.get("summary"),
                            key_metrics=result.get("key_metrics", {}),
                            key_players=result.get("key_players", []),
                            soy_advantage=result.get("soy_advantage"),
                            barriers=result.get("barriers"),
                            model_used="claude-sonnet-4-5-20250929",
                        )
                        self.db.insert_enrichment(enrichment)
                        enriched += 1
                except Exception as e:
                    logger.error(f"Deep analysis failed for finding {finding['id']}: {e}")

                progress.update(task, advance=1)

        console.print(f"  Deep-analyzed [bold]{enriched}[/bold] findings")
        return enriched

    async def run_all_tiers(self, tier1_limit: int = 0, tier2_limit: int = 0, tier3_limit: int = 50) -> dict[str, int]:
        """Run all enrichment tiers in sequence."""
        results = {}
        results["tier1"] = await self.enrich_tier1_catalog(limit=tier1_limit)
        results["tier2"] = await self.enrich_tier2_summary(limit=tier2_limit)
        results["tier3"] = await self.enrich_tier3_deep(limit=tier3_limit)
        console.print(f"\n[bold green]Enrichment complete:[/bold green] {results}")
        return results
