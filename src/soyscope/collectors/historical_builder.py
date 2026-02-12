"""25-year initial build orchestration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..config import Settings, get_settings
from ..db import Database
from ..orchestrator import SearchOrchestrator
from .query_generator import QueryPlan, generate_full_query_plan

logger = logging.getLogger(__name__)
console = Console()


class HistoricalBuilder:
    """Orchestrates the 25-year initial database build."""

    def __init__(
        self,
        orchestrator: SearchOrchestrator,
        db: Database,
        settings: Settings | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.db = db
        self.settings = settings or get_settings()

    async def build(
        self,
        concurrency: int = 3,
        max_queries: int | None = None,
    ) -> dict[str, Any]:
        """Execute the full historical build.

        Args:
            concurrency: Number of concurrent API queries.
            max_queries: Limit total queries (for testing).

        Returns:
            Summary statistics.
        """
        console.print("[bold green]Starting 25-year historical build...[/bold green]")

        # Generate query plan
        taxonomy_path = self.settings.data_dir / "taxonomy.json"
        plans = generate_full_query_plan(
            taxonomy_path=taxonomy_path if taxonomy_path.exists() else None,
        )

        if max_queries:
            plans = plans[:max_queries]

        console.print(f"Generated [bold]{len(plans)}[/bold] queries")

        # Start search run
        run_id = self.db.start_search_run("historical_build")

        total_new = 0
        total_updated = 0
        total_queries = 0
        errors = 0
        start_time = time.time()

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def execute_query(plan: QueryPlan) -> tuple[int, int]:
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
                    logger.error(f"Query failed: {plan.query}: {e}")
                    return 0, 0

        # Execute with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Building database", total=len(plans))

            # Process in batches for better progress tracking
            batch_size = concurrency * 2
            for i in range(0, len(plans), batch_size):
                batch = plans[i : i + batch_size]
                tasks = [execute_query(plan) for plan in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    total_queries += 1
                    if isinstance(result, Exception):
                        errors += 1
                        logger.error(f"Batch query error: {result}")
                    else:
                        new, updated = result
                        total_new += new
                        total_updated += updated

                    progress.update(task, advance=1)

                # Log periodic stats
                if total_queries % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = total_queries / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {total_queries}/{len(plans)} queries, "
                        f"{total_new} new, {total_updated} updated, "
                        f"{rate:.1f} queries/sec"
                    )

        elapsed = time.time() - start_time

        # Complete run
        self.db.complete_search_run(
            run_id=run_id,
            queries_executed=total_queries,
            findings_added=total_new,
            findings_updated=total_updated,
        )

        summary = {
            "run_id": run_id,
            "total_queries": total_queries,
            "findings_added": total_new,
            "findings_updated": total_updated,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 1),
            "queries_per_second": round(total_queries / elapsed, 2) if elapsed > 0 else 0,
        }

        console.print(f"\n[bold green]Build complete![/bold green]")
        console.print(f"  Queries executed: {total_queries}")
        console.print(f"  New findings: {total_new}")
        console.print(f"  Updated findings: {total_updated}")
        console.print(f"  Errors: {errors}")
        console.print(f"  Time: {elapsed:.1f}s")

        return summary
