# SoyScope - Industrial Soy Uses Search & Tracking Tool

## Project Overview
Builds and maintains a comprehensive database of ALL industrial uses of soy over the past 25 years using 8 search APIs + Claude AI enrichment. Outputs to SQLite + Excel + Word + Streamlit.

## Architecture
- `src/soyscope/` - Main package
- `src/soyscope/sources/` - One adapter per API (8 total)
- `src/soyscope/enrichment/` - Claude-based AI classification and analysis
- `src/soyscope/collectors/` - Search orchestration and data collection
- `src/soyscope/outputs/` - Excel, Word, Streamlit exports

## Key Patterns
- All API sources implement the `SearchSource` protocol from `sources/base.py`
- Rate limiting via token bucket in `rate_limit.py`
- Circuit breaker pattern in `circuit_breaker.py`
- DOI-first + fuzzy title deduplication in `dedup.py`
- Reciprocal Rank Fusion for result merging in `ranking.py`
- diskcache for search result caching
- Pydantic models for all data structures

## CLI Commands
```
soyscope build          # Initial 25-year historical build
soyscope refresh        # Incremental update
soyscope enrich         # AI enrichment on un-enriched findings
soyscope import-checkoff # Import soybean_scraper data
soyscope stats          # Database statistics
soyscope export excel   # Excel workbook
soyscope export word    # Word report
soyscope dashboard      # Streamlit dashboard
soyscope search "query" # Ad-hoc search
```

## Database
SQLite at `data/soyscope.db`. Schema in `src/soyscope/db.py`.

## Testing
Run: `pytest tests/`
