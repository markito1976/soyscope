# SoyScope - Industrial Soy Uses Search & Tracking Tool

## Project Overview
Builds and maintains a comprehensive database of ALL industrial uses of soy over the past 25 years using 14 search APIs + Claude AI enrichment. Primary goal: **discover novel/unexpected soy applications that fall outside known categories**. Outputs to SQLite + Excel + Word + Streamlit + PySide6 desktop GUI.

## Architecture
- `src/soyscope/` - Main package
- `src/soyscope/sources/` - One adapter per API (14 total: 8 original + 6 Tier 1)
- `src/soyscope/enrichment/` - Claude-based AI classification and analysis
- `src/soyscope/collectors/` - Search orchestration, query generation, historical builder
- `src/soyscope/outputs/` - Excel, Word, Streamlit exports
- `src/soyscope/gui/` - PySide6 desktop GUI (MVD architecture, dark/light themes)
  - `gui/views/` - 6 tabs: Overview, Explorer, Matrix, Trends, Novel Uses, Run History
  - `gui/workers/` - Background workers: build, import, enrich, data, stats
  - `gui/widgets/` - Progress panel, KPI cards, heatmap, timeline, search bar
  - `gui/delegates/` - Badge, link, progress bar cell renderers

## Key Patterns
- All API sources implement the `SearchSource` protocol from `sources/base.py`
- Rate limiting via token bucket in `rate_limit.py`
- Circuit breaker pattern in `circuit_breaker.py`
- DOI-first + fuzzy title deduplication in `dedup.py`
- Reciprocal Rank Fusion for result merging in `ranking.py`
- diskcache for search result caching
- Pydantic models for all data structures
- **Checkpoint/resume** for large builds via `search_checkpoints` table
- **Progress callbacks** from HistoricalBuilder → BuildWorker → GUI dashboard
- Query generator uses **sector keywords** (not sector names) to avoid journal-name matching

## API Sources (14 total)
### Original (8)
- EXA, OpenAlex, Semantic Scholar, Crossref, PubMed, Tavily, CORE, Unpaywall

### Tier 1 — Free, no/light auth (6, added Feb 13 2026)
- **OSTI.gov** — DOE research (no auth)
- **USPTO PatentsView** — U.S. patents (free key, pending registration)
- **SBIR/STTR** — Federal innovation awards (no auth)
- **AGRIS/FAO** — 7M+ multilingual ag records (no auth, currently returning 403)
- **Lens.org** — 200M+ scholarly + patents (bearer token, pending registration)
- **USDA ERS/PubAg** — USDA publications (key registered, APIs currently down)

## CLI Commands
```
soyscope build [--resume]   # Initial 25-year historical build (checkpoint/resume supported)
soyscope refresh            # Incremental update
soyscope enrich             # AI enrichment on un-enriched findings
soyscope import-checkoff    # Import soybean_scraper data
soyscope import-deliverables --path FILE [--no-resolve-oa]  # Import USB deliverables CSV
soyscope resolve-oa         # Resolve OA links via Unpaywall
soyscope backfill-sources   # Seed finding_sources from existing data
soyscope stats              # Database statistics
soyscope export excel       # Excel workbook
soyscope export word        # Word report
soyscope dashboard          # Streamlit dashboard
soyscope search "query"     # Ad-hoc search
soyscope gui                # Launch PySide6 desktop GUI
soyscope init               # Initialize database and seed taxonomy
```

## GUI Build Dashboard
The Run History tab includes a transparent Build Dashboard with:
- **API Source Health Grid** — 14 sources with green/red/grey status dots
- **Live Progress Panel** — query counter, progress bar, ETA, rate
- **Findings Feed** — scrolling list of new findings color-coded by source type
- **Per-Source Stats Table** — queries/results/errors/status per API
- Dashboard auto-shows on build start, auto-hides on completion

## Database
SQLite at `data/soyscope.db`. Schema in `src/soyscope/db.py`.
Key tables: findings, finding_sources, search_checkpoints, enrichments, sectors, derivatives, tags.
- **WARNING:** enrichments table contains 300 dummy records from `seed_dummy_data.py` — must be purged before real enrichment

## Search Strategy (EVOLVING)
Current: grid search (14 derivatives × 16 sectors × 5 time windows) with synonym expansion.
Next: **open-ended discovery queries** to find novel soy uses OUTSIDE the known matrix.
The most valuable findings are the ones that DON'T fit existing categories.

## Testing
Run: `pytest tests/` — **200 tests passing** (as of Feb 13 2026)
