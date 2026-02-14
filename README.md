# SoyScope: Industrial Soy Uses Search & Tracking Tool

A comprehensive tool that builds and maintains a database of **all industrial uses (and potential uses) of soy** over the past 25 years. Uses 14 search APIs, AI enrichment via Claude, and outputs to SQLite + Excel + Word + Streamlit + PySide6 desktop GUI.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in API keys
cp .env.example .env
# Edit .env with your API keys

# Initialize database and seed taxonomy
soyscope init

# Import existing Soybean Checkoff data (if available)
soyscope import-checkoff

# Run the full 25-year historical build
soyscope build

# If interrupted, resume where you left off
soyscope build --resume

# Run AI enrichment
soyscope enrich

# View statistics
soyscope stats

# Export reports
soyscope export excel
soyscope export word

# Launch PySide6 desktop GUI
soyscope gui

# Or launch Streamlit dashboard
soyscope dashboard
```

## API Sources (14)

| # | API | Purpose | Auth Required |
|---|-----|---------|---------------|
| 1 | EXA | Neural semantic search | API key |
| 2 | OpenAlex | Academic metadata | Email (polite pool) |
| 3 | Semantic Scholar | Citations, TLDRs | API key (free) |
| 4 | Crossref | DOI resolution | Email (polite pool) |
| 5 | PubMed/Entrez | Biomedical literature | API key (free) |
| 6 | Tavily | Web/news/industry | API key |
| 7 | CORE | Full-text open access | API key (free) |
| 8 | Unpaywall | OA PDF location | Email |
| 9 | OSTI.gov | DOE research | None |
| 10 | PatentsView | USPTO patents | API key (free) |
| 11 | SBIR/STTR | Federal innovation awards | None |
| 12 | AGRIS/FAO | Multilingual ag records | None |
| 13 | Lens.org | Scholarly + patents | Bearer token (free trial) |
| 14 | USDA ERS | USDA publications | API key (free) |

Plus **Claude AI** for enrichment and analysis.

## PySide6 Desktop GUI

Launch with `soyscope gui` or `SoyScope.bat`. Features:

- **Overview** — KPI cards, charts, database statistics
- **Explorer** — Searchable, filterable findings table (50K+ row virtual scrolling)
- **Matrix** — Interactive heatmap (derivative × sector)
- **Trends** — Timeline/area charts by year
- **Novel Uses** — AI-enriched findings ranked by novelty score
- **Run History** — Full Build Dashboard with live transparency:
  - 14-source health grid with status indicators
  - Real-time progress (query counter, ETA, rate)
  - Live findings feed as data arrives
  - Per-source statistics table

## CLI Commands

```
soyscope build [--resume]   # Initial 25-year historical build (checkpoint/resume)
soyscope refresh            # Incremental update since last run
soyscope enrich             # Run AI enrichment on un-enriched findings
soyscope import-checkoff    # Import soybean_scraper data
soyscope import-deliverables --path FILE  # Import USB deliverables CSV
soyscope resolve-oa         # Resolve OA links via Unpaywall
soyscope stats              # Show database statistics
soyscope export excel       # Generate Excel workbook
soyscope export word        # Generate Word summary report
soyscope dashboard          # Launch Streamlit dashboard
soyscope gui                # Launch PySide6 desktop GUI
soyscope search "query"     # Ad-hoc search across all APIs
soyscope init               # Initialize DB and seed taxonomy
```

## Enrichment Tiers

- **Tier 1 (Catalog)**: Rule-based keyword matching, novelty scoring. Free.
- **Tier 2 (Summary)**: Claude Haiku batch classification, sector/derivative tagging, TRL estimation.
- **Tier 3 (Deep)**: Claude Sonnet detailed analysis for high-novelty findings.

## Testing

```bash
pytest tests/  # 200 tests passing
```

## Project Structure

```
src/soyscope/
├── config.py          # Settings management
├── db.py              # SQLite schema + CRUD
├── models.py          # Pydantic models
├── cli.py             # Typer CLI
├── orchestrator.py    # Multi-API parallel search
├── rate_limit.py      # Token bucket rate limiters
├── circuit_breaker.py # Fault tolerance
├── dedup.py           # DOI + fuzzy title deduplication
├── ranking.py         # Reciprocal Rank Fusion
├── cache.py           # diskcache search caching
├── sources/           # 14 API adapters
├── enrichment/        # Claude AI classification + analysis
├── collectors/        # Search orchestration + query generation + data import
├── gui/               # PySide6 desktop GUI (32 files, MVD architecture)
└── outputs/           # Excel, Word, Streamlit exports
```
