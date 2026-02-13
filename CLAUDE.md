# SoyScope - Industrial Soy Uses Search & Tracking Tool

## Project Overview
Builds and maintains a comprehensive database of ALL industrial uses of soy over the past 25 years using 14 search APIs + Claude AI enrichment. Outputs to SQLite + Excel + Word + Streamlit.

## Architecture
- `src/soyscope/` - Main package
- `src/soyscope/sources/` - One adapter per API (14 total: 8 original + 6 Tier 1)
- `src/soyscope/enrichment/` - Claude-based AI classification and analysis
- `src/soyscope/collectors/` - Search orchestration and data collection
- `src/soyscope/outputs/` - Excel, Word, Streamlit exports
- `src/soyscope/gui/` - PySide6 desktop GUI (MVD architecture, dark/light themes)

## Key Patterns
- All API sources implement the `SearchSource` protocol from `sources/base.py`
- Rate limiting via token bucket in `rate_limit.py`
- Circuit breaker pattern in `circuit_breaker.py`
- DOI-first + fuzzy title deduplication in `dedup.py`
- Reciprocal Rank Fusion for result merging in `ranking.py`
- diskcache for search result caching
- Pydantic models for all data structures
- **Checkpoint/resume** for large builds via `search_checkpoints` table

## API Sources (14 total)
### Original (8)
- EXA, OpenAlex, Semantic Scholar, Crossref, PubMed, Tavily, CORE, Unpaywall

### Tier 1 — Free, no/light auth (6, added Feb 13 2026)
- **OSTI.gov** — DOE research (no auth)
- **USPTO PatentsView** — U.S. patents (free key optional, 45 req/min)
- **SBIR/STTR** — Federal innovation awards (no auth)
- **AGRIS/FAO** — 7M+ multilingual ag records (no auth)
- **Lens.org** — 200M+ scholarly + patents (bearer token, 50 req/min)
- **USDA ERS/PubAg** — USDA publications (free key optional)

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

## Database
SQLite at `data/soyscope.db`. Schema in `src/soyscope/db.py`.
Key tables: findings, finding_sources, search_checkpoints, enrichments, sectors, derivatives, tags.

## Testing
Run: `pytest tests/` — **121 tests passing** (as of Feb 13 2026)
