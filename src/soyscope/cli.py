"""Typer CLI entry point for SoyScope."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .db import Database

app = typer.Typer(
    name="soyscope",
    help="SoyScope: Industrial Soy Uses Search & Tracking Tool",
    rich_markup_mode="rich",
)
export_app = typer.Typer(help="Export data to Excel or Word format.")
app.add_typer(export_app, name="export")

console = Console()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                get_settings().logs_dir / "soyscope.log",
                encoding="utf-8",
            ),
        ],
    )


def _get_db() -> Database:
    settings = get_settings()
    db = Database(settings.db_path)
    db.init_schema()
    return db


def _build_sources():
    """Instantiate all configured API sources."""
    from .sources.base import BaseSource
    settings = get_settings()
    sources: list[BaseSource] = []

    api_cfg = settings.apis

    if api_cfg["openalex"].enabled:
        from .sources.openalex_source import OpenAlexSource
        sources.append(OpenAlexSource(email=api_cfg["openalex"].email))

    if api_cfg["semantic_scholar"].enabled:
        from .sources.semantic_scholar import SemanticScholarSource
        sources.append(SemanticScholarSource(api_key=api_cfg["semantic_scholar"].api_key))

    if api_cfg["exa"].enabled and api_cfg["exa"].api_key:
        from .sources.exa_source import ExaSource
        sources.append(ExaSource(api_key=api_cfg["exa"].api_key))

    if api_cfg["crossref"].enabled:
        from .sources.crossref_source import CrossrefSource
        sources.append(CrossrefSource(email=api_cfg["crossref"].email))

    if api_cfg["pubmed"].enabled and api_cfg["pubmed"].email:
        from .sources.pubmed_source import PubMedSource
        sources.append(PubMedSource(api_key=api_cfg["pubmed"].api_key, email=api_cfg["pubmed"].email))

    if api_cfg["tavily"].enabled and api_cfg["tavily"].api_key:
        from .sources.tavily_source import TavilySource
        sources.append(TavilySource(api_key=api_cfg["tavily"].api_key))

    if api_cfg["core"].enabled and api_cfg["core"].api_key:
        from .sources.core_source import CoreSource
        sources.append(CoreSource(api_key=api_cfg["core"].api_key))

    if api_cfg["unpaywall"].enabled and api_cfg["unpaywall"].email:
        from .sources.unpaywall_source import UnpaywallSource
        sources.append(UnpaywallSource(email=api_cfg["unpaywall"].email))

    return sources


def _build_orchestrator(db: Database):
    from .cache import SearchCache
    from .circuit_breaker import setup_circuit_breakers
    from .orchestrator import SearchOrchestrator
    from .rate_limit import setup_rate_limiters

    settings = get_settings()
    sources = _build_sources()
    cache = SearchCache(settings.cache_dir)
    limiters = setup_rate_limiters()
    breakers = setup_circuit_breakers()

    return SearchOrchestrator(
        sources=sources,
        db=db,
        cache=cache,
        settings=settings,
        limiters=limiters,
        breakers=breakers,
    )


def _seed_taxonomy(db: Database) -> None:
    """Seed the database with the default taxonomy."""
    from .collectors.query_generator import DEFAULT_DERIVATIVES, DEFAULT_SECTORS

    for name in DEFAULT_SECTORS:
        db.insert_sector(name)
    for name in DEFAULT_DERIVATIVES:
        db.insert_derivative(name)


@app.command()
def build(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    concurrency: int = typer.Option(3, "--concurrency", "-c", help="Concurrent API queries"),
    max_queries: Optional[int] = typer.Option(None, "--max-queries", "-m", help="Limit queries (for testing)"),
):
    """Run the initial 25-year historical database build."""
    _setup_logging(verbose)
    db = _get_db()
    _seed_taxonomy(db)
    orchestrator = _build_orchestrator(db)

    from .collectors.historical_builder import HistoricalBuilder
    builder = HistoricalBuilder(orchestrator=orchestrator, db=db)
    result = asyncio.run(builder.build(concurrency=concurrency, max_queries=max_queries))
    console.print(f"\nBuild summary: {result}")


@app.command()
def refresh(
    since: Optional[str] = typer.Option(None, "--since", "-s", help="Start date (YYYY-MM-DD or YYYY)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    concurrency: int = typer.Option(3, "--concurrency", "-c"),
    max_queries: Optional[int] = typer.Option(None, "--max-queries", "-m"),
):
    """Run incremental update since last run or specified date."""
    _setup_logging(verbose)
    db = _get_db()
    orchestrator = _build_orchestrator(db)

    from .collectors.refresh_runner import RefreshRunner
    runner = RefreshRunner(orchestrator=orchestrator, db=db)
    result = asyncio.run(runner.refresh(since=since, concurrency=concurrency, max_queries=max_queries))
    console.print(f"\nRefresh summary: {result}")


@app.command()
def enrich(
    tier: int = typer.Option(0, "--tier", "-t", help="Specific tier (1/2/3), or 0 for all"),
    limit: int = typer.Option(0, "--limit", "-l", help="Max findings to process"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run AI enrichment on un-enriched findings."""
    _setup_logging(verbose)
    db = _get_db()
    settings = get_settings()

    classifier = None
    summarizer = None

    if settings.apis["claude"].enabled and settings.apis["claude"].api_key:
        from .enrichment.classifier import Classifier
        from .enrichment.summarizer import Summarizer
        classifier = Classifier(api_key=settings.apis["claude"].api_key)
        summarizer = Summarizer(api_key=settings.apis["claude"].api_key)

    from .enrichment.batch_enricher import BatchEnricher
    enricher = BatchEnricher(db=db, classifier=classifier, summarizer=summarizer, settings=settings)

    if tier == 0:
        result = asyncio.run(enricher.run_all_tiers(tier1_limit=limit, tier2_limit=limit, tier3_limit=min(limit or 50, 50)))
    elif tier == 1:
        result = asyncio.run(enricher.enrich_tier1_catalog(limit=limit))
    elif tier == 2:
        result = asyncio.run(enricher.enrich_tier2_summary(limit=limit))
    elif tier == 3:
        result = asyncio.run(enricher.enrich_tier3_deep(limit=limit))
    else:
        console.print(f"[red]Invalid tier: {tier}. Use 1, 2, or 3.[/red]")
        raise typer.Exit(1)

    console.print(f"\nEnrichment result: {result}")


@app.command(name="import-checkoff")
def import_checkoff(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to JSON data file"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Import soybean_scraper data (Soybean Checkoff Research DB)."""
    _setup_logging(verbose)
    db = _get_db()
    _seed_taxonomy(db)

    from .collectors.checkoff_importer import CheckoffImporter
    importer = CheckoffImporter(db=db)

    if path:
        count = importer.import_from_json(Path(path))
        console.print(f"Imported {count} projects from {path}")
    else:
        result = importer.import_all()
        console.print(f"Import result: {result}")


@app.command()
def stats(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Show database statistics."""
    _setup_logging(verbose)
    db = _get_db()
    s = db.get_stats()

    table = Table(title="SoyScope Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Findings", f"{s['total_findings']:,}")
    table.add_row("Total Sectors", str(s["total_sectors"]))
    table.add_row("Total Derivatives", str(s["total_derivatives"]))
    table.add_row("Total Enriched", f"{s['total_enriched']:,}")
    table.add_row("  Tier 1 (Catalog)", f"{s['enrichment_catalog']:,}")
    table.add_row("  Tier 2 (Summary)", f"{s['enrichment_summary']:,}")
    table.add_row("  Tier 3 (Deep)", f"{s['enrichment_deep']:,}")
    table.add_row("Total Tags", str(s["total_tags"]))
    table.add_row("Checkoff Projects", f"{s['total_checkoff']:,}")
    table.add_row("Search Runs", str(s["total_runs"]))

    console.print(table)

    if s["by_source"]:
        source_table = Table(title="Findings by Source API")
        source_table.add_column("Source", style="cyan")
        source_table.add_column("Count", style="green")
        for source, count in sorted(s["by_source"].items(), key=lambda x: x[1], reverse=True):
            source_table.add_row(source, f"{count:,}")
        console.print(source_table)

    if s["by_type"]:
        type_table = Table(title="Findings by Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="green")
        for stype, count in sorted(s["by_type"].items(), key=lambda x: x[1], reverse=True):
            type_table.add_row(stype, f"{count:,}")
        console.print(type_table)


@export_app.command(name="excel")
def export_excel(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate Excel workbook report."""
    _setup_logging(verbose)
    db = _get_db()
    settings = get_settings()

    from .outputs.excel_export import ExcelExporter
    exporter = ExcelExporter(db=db, output_dir=settings.exports_dir)
    path = exporter.export(filename=output)
    console.print(f"[green]Excel report saved to:[/green] {path}")


@export_app.command(name="word")
def export_word(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate Word summary report."""
    _setup_logging(verbose)
    db = _get_db()
    settings = get_settings()

    from .outputs.word_export import WordExporter
    exporter = WordExporter(db=db, output_dir=settings.exports_dir)
    path = exporter.export(filename=output)
    console.print(f"[green]Word report saved to:[/green] {path}")


@app.command()
def dashboard():
    """Launch Streamlit dashboard."""
    import subprocess
    dashboard_path = Path(__file__).parent / "outputs" / "dashboard.py"
    console.print(f"[green]Launching Streamlit dashboard...[/green]")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)], check=True)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    sources: Optional[str] = typer.Option(None, "--sources", "-s", help="Comma-separated source names"),
    max_results: int = typer.Option(20, "--max", "-m", help="Max results per source"),
    store: bool = typer.Option(False, "--store", help="Store results in database"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Ad-hoc search across all APIs."""
    _setup_logging(verbose)
    db = _get_db()
    _seed_taxonomy(db)
    orchestrator = _build_orchestrator(db)

    source_list = sources.split(",") if sources else None

    async def _search():
        if store:
            new, updated = await orchestrator.search_and_store(
                query=query, max_results=max_results, source_names=source_list,
            )
            console.print(f"Stored {new} new, {updated} updated findings")
        else:
            papers = await orchestrator.search(
                query=query, max_results=max_results, source_names=source_list,
            )
            table = Table(title=f"Search Results: {query}")
            table.add_column("#", style="dim")
            table.add_column("Title", style="cyan", max_width=60)
            table.add_column("Year", style="green")
            table.add_column("Source", style="yellow")
            table.add_column("DOI", style="dim", max_width=30)

            for i, p in enumerate(papers[:50], 1):
                table.add_row(str(i), p.title[:60], str(p.year or ""), p.source_api, p.doi or "")

            console.print(table)
            console.print(f"\nTotal: {len(papers)} results")

    asyncio.run(_search())


@app.command(name="init")
def init_db(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Initialize database and seed taxonomy."""
    _setup_logging(verbose)
    db = _get_db()
    _seed_taxonomy(db)
    console.print("[green]Database initialized and taxonomy seeded.[/green]")
    stats_cmd = db.get_stats()
    console.print(f"  Sectors: {stats_cmd['total_sectors']}")
    console.print(f"  Derivatives: {stats_cmd['total_derivatives']}")


if __name__ == "__main__":
    app()
