"""Incremental update logic."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..config import Settings, get_settings
from ..db import Database
from ..orchestrator import SearchOrchestrator
from .query_generator import generate_refresh_queries

logger = logging.getLogger(__name__)
console = Console()


class RefreshRunner:
    """Runs incremental updates since the last search run."""

    def __init__(
        self,
        orchestrator: SearchOrchestrator,
        db: Database,
        settings: Settings | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.db = db
        self.settings = settings or get_settings()

    def _get_since_year(self, since: str | None = None) -> int:
        """Determine the start year for refresh."""
        if since:
            return int(since[:4])

        last_run = self.db.get_last_search_run()
        if last_run and last_run.get("completed_at"):
            completed = last_run["completed_at"]
            if isinstance(completed, str):
                return int(completed[:4])
        # Default: last year
        return datetime.now().year - 1

    async def refresh(
        self,
        since: str | None = None,
        concurrency: int = 3,
        max_queries: int | None = None,
    ) -> dict[str, Any]:
        """Run incremental refresh.

        Args:
            since: Start date as "YYYY-MM-DD" or "YYYY". If None, uses last run date.
            concurrency: Number of concurrent queries.
            max_queries: Limit total queries (for testing).

        Returns:
            Summary statistics.
        """
        since_year = self._get_since_year(since)
        console.print(f"[bold green]Starting refresh since {since_year}...[/bold green]")

        taxonomy_path = self.settings.data_dir / "taxonomy.json"
        plans = generate_refresh_queries(
            since_year=since_year,
            taxonomy_path=taxonomy_path if taxonomy_path.exists() else None,
        )

        if max_queries:
            plans = plans[:max_queries]

        console.print(f"Generated [bold]{len(plans)}[/bold] refresh queries")

        run_id = self.db.start_search_run("refresh")
        total_new = 0
        total_updated = 0
        total_queries = 0
        errors = 0
        start_time = time.time()

        semaphore = asyncio.Semaphore(concurrency)

        async def execute_query(plan):
            async with semaphore:
                try:
                    new, updated = await self.orchestrator.search_and_store(
                        query=plan.query,
                        run_id=run_id,
                        max_results=self.settings.max_results_per_query,
                        year_start=plan.year_start,
                        year_end=plan.year_end,
                        source_names=plan.target_apis,
                    )
                    return new, updated
                except Exception as e:
                    logger.error(f"Refresh query failed: {plan.query}: {e}")
                    return 0, 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Refreshing since {since_year}", total=len(plans))

            batch_size = concurrency * 2
            for i in range(0, len(plans), batch_size):
                batch = plans[i : i + batch_size]
                tasks = [execute_query(plan) for plan in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    total_queries += 1
                    if isinstance(result, Exception):
                        errors += 1
                    else:
                        new, updated = result
                        total_new += new
                        total_updated += updated
                    progress.update(task, advance=1)

        elapsed = time.time() - start_time

        self.db.complete_search_run(
            run_id=run_id,
            queries_executed=total_queries,
            findings_added=total_new,
            findings_updated=total_updated,
        )

        summary = {
            "run_id": run_id,
            "since_year": since_year,
            "total_queries": total_queries,
            "findings_added": total_new,
            "findings_updated": total_updated,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 1),
        }

        console.print(f"\n[bold green]Refresh complete![/bold green]")
        console.print(f"  Since: {since_year}")
        console.print(f"  Queries: {total_queries}")
        console.print(f"  New findings: {total_new}")
        console.print(f"  Updated: {total_updated}")
        console.print(f"  Errors: {errors}")
        console.print(f"  Time: {elapsed:.1f}s")

        return summary
