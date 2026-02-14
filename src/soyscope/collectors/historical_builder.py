"""25-year initial build orchestration with checkpoint/resume support."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..config import Settings, get_settings
from ..db import Database
from ..orchestrator import SearchOrchestrator
from .query_generator import QueryPlan, generate_full_query_plan

logger = logging.getLogger(__name__)
console = Console()


def _query_hash(plan: QueryPlan) -> str:
    """Deterministic hash for a QueryPlan so we can checkpoint it."""
    key = f"{plan.query}|{plan.query_type}|{plan.year_start}|{plan.year_end}|{','.join(sorted(plan.target_apis))}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class HistoricalBuilder:
    """Orchestrates the 25-year initial database build.

    Supports checkpoint/resume: if a build is interrupted (Ctrl+C, crash,
    session close), the next ``build --resume`` picks up exactly where it
    left off.  Every completed query is checkpointed in the
    ``search_checkpoints`` table so no work is repeated.
    """

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
        resume: bool = False,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict[str, Any]:
        """Execute the full historical build.

        Args:
            concurrency: Number of concurrent API queries.
            max_queries: Limit total queries (for testing).
            resume: If True, resume the last interrupted build run.
            progress_callback: Optional callback invoked with a dict of
                progress data after each query and at build start/end.

        Returns:
            Summary statistics.
        """
        run_id: int | None = None

        # --- Resume logic ---
        if resume:
            prev = self.db.get_last_incomplete_run("historical_build")
            if prev:
                run_id = prev["id"]
                self.db.reset_failed_checkpoints(run_id)
                progress_info = self.db.get_checkpoint_progress(run_id)
                console.print(
                    f"[bold yellow]Resuming build run #{run_id}[/bold yellow]  "
                    f"({progress_info['completed']} done, "
                    f"{progress_info['pending']} pending, "
                    f"{progress_info['failed']} failed → retrying)"
                )
            else:
                console.print("[dim]No interrupted build found — starting fresh.[/dim]")

        # --- Generate query plan ---
        taxonomy_path = self.settings.data_dir / "taxonomy.json"
        plans = generate_full_query_plan(
            taxonomy_path=taxonomy_path if taxonomy_path.exists() else None,
        )

        if max_queries:
            plans = plans[:max_queries]

        console.print(f"Generated [bold]{len(plans)}[/bold] total queries")

        # --- Create or reuse run ---
        if run_id is None:
            run_id = self.db.start_search_run("historical_build")

        # --- Seed checkpoints ---
        checkpoint_records = [
            {
                "query_hash": _query_hash(p),
                "query_text": p.query,
                "query_type": p.query_type,
                "derivative": p.derivative,
                "sector": p.sector,
                "year_start": p.year_start,
                "year_end": p.year_end,
            }
            for p in plans
        ]
        new_cp = self.db.insert_checkpoint_batch(run_id, checkpoint_records)
        if new_cp > 0:
            console.print(f"Seeded [bold]{new_cp}[/bold] new checkpoints")

        # --- Load pending work ---
        pending = self.db.get_pending_checkpoints(run_id)
        if not pending:
            console.print("[green]All queries already completed. Nothing to do.[/green]")
            return {"run_id": run_id, "total_queries": 0, "findings_added": 0,
                    "findings_updated": 0, "errors": 0, "resumed": resume}

        console.print(f"[bold]{len(pending)}[/bold] queries remaining")

        # Build a hash→plan lookup for matching checkpoints to plans
        plan_by_hash: dict[str, QueryPlan] = {_query_hash(p): p for p in plans}

        total_new = 0
        total_updated = 0
        total_queries = 0
        errors = 0
        start_time = time.time()

        # Emit build_started event
        if progress_callback:
            source_names = list({api for p in plans for api in p.target_apis})
            progress_callback({
                "event": "build_started",
                "total_queries": len(pending),
                "sources": source_names,
                "concurrency": concurrency,
                "resumed": resume,
                "run_id": run_id,
            })

        semaphore = asyncio.Semaphore(concurrency)

        async def execute_query(cp: dict[str, Any]) -> tuple[int, int, int]:
            """Returns (new, updated, checkpoint_id)."""
            cp_id = cp["id"]
            q_hash = cp["query_hash"]
            plan = plan_by_hash.get(q_hash)

            if plan is None:
                # Orphan checkpoint — query plan changed. Skip it.
                self.db.complete_checkpoint(cp_id, 0, 0)
                return 0, 0, cp_id

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
                    self.db.complete_checkpoint(cp_id, new, updated)

                    # Nonlocal counters are updated by the caller after
                    # gather(), so we pass the running totals via the
                    # callback *after* the caller updates them.  Instead
                    # we report per-query results here and let the caller
                    # aggregate.
                    if progress_callback:
                        progress_callback({
                            "event": "query_complete",
                            "completed": total_queries + 1,
                            "total": len(pending),
                            "query": plan.query,
                            "query_type": plan.query_type,
                            "derivative": plan.derivative,
                            "sector": plan.sector,
                            "new_findings": new,
                            "updated_findings": updated,
                            "total_new": total_new + new,
                            "total_updated": total_updated + updated,
                            "errors": errors,
                            "elapsed_seconds": time.time() - start_time,
                        })

                    return new, updated, cp_id
                except Exception as e:
                    logger.error(f"Query failed (cp #{cp_id}): {plan.query}: {e}")
                    self.db.fail_checkpoint(cp_id)

                    if progress_callback:
                        progress_callback({
                            "event": "source_error",
                            "source": ", ".join(plan.target_apis),
                            "query": plan.query,
                            "error": str(e),
                            "errors": errors + 1,
                            "elapsed_seconds": time.time() - start_time,
                        })

                    return 0, 0, cp_id

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
            task = progress.add_task("Building database", total=len(pending))

            batch_size = concurrency * 2
            try:
                for i in range(0, len(pending), batch_size):
                    batch = pending[i : i + batch_size]
                    tasks = [execute_query(cp) for cp in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in results:
                        total_queries += 1
                        if isinstance(result, Exception):
                            errors += 1
                            logger.error(f"Batch query error: {result}")
                        else:
                            new, updated, _ = result
                            total_new += new
                            total_updated += updated

                        progress.update(task, advance=1)

                    # Log periodic stats
                    if total_queries % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = total_queries / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"Progress: {total_queries}/{len(pending)} queries, "
                            f"{total_new} new, {total_updated} updated, "
                            f"{rate:.1f} queries/sec"
                        )

            except (KeyboardInterrupt, asyncio.CancelledError):
                # Graceful interruption — mark run as interrupted so it's resumable
                console.print("\n[bold yellow]Build interrupted! Progress saved.[/bold yellow]")
                self.db.interrupt_search_run(run_id)
                cp_progress = self.db.get_checkpoint_progress(run_id)
                console.print(
                    f"  Saved: {cp_progress['completed']}/{cp_progress['total']} "
                    f"queries completed, {cp_progress['pending']} remaining"
                )
                console.print("  Resume with: [bold]soyscope build --resume[/bold]")
                return {
                    "run_id": run_id,
                    "total_queries": total_queries,
                    "findings_added": total_new,
                    "findings_updated": total_updated,
                    "errors": errors,
                    "interrupted": True,
                }

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
            "resumed": resume,
        }

        console.print(f"\n[bold green]Build complete![/bold green]")
        console.print(f"  Queries executed: {total_queries}")
        console.print(f"  New findings: {total_new}")
        console.print(f"  Updated findings: {total_updated}")
        console.print(f"  Errors: {errors}")
        console.print(f"  Time: {elapsed:.1f}s")

        if progress_callback:
            progress_callback({
                "event": "build_complete",
                **summary,
            })

        return summary
