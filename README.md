# SoyScope: Industrial Soy Uses Search & Tracking Tool

A comprehensive tool that builds and maintains a database of **all industrial uses (and potential uses) of soy** over the past 25 years. Uses 8 search APIs, AI enrichment via Claude, and outputs to SQLite + Excel + Word + Streamlit dashboard.

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

# Run AI enrichment
soyscope enrich

# View statistics
soyscope stats

# Export reports
soyscope export excel
soyscope export word

# Launch interactive dashboard
soyscope dashboard
```

## API Sources (8)

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

Plus **Claude AI** for enrichment and analysis.

## CLI Commands

```
soyscope build              # Initial 25-year historical build
soyscope refresh            # Incremental update since last run
soyscope enrich             # Run AI enrichment on un-enriched findings
soyscope import-checkoff    # Import soybean_scraper data
soyscope stats              # Show database statistics
soyscope export excel       # Generate Excel workbook
soyscope export word        # Generate Word summary report
soyscope dashboard          # Launch Streamlit dashboard
soyscope search "query"     # Ad-hoc search across all APIs
soyscope init               # Initialize DB and seed taxonomy
```

## Enrichment Tiers

- **Tier 1 (Catalog)**: Rule-based keyword matching, novelty scoring. Free.
- **Tier 2 (Summary)**: Claude Haiku batch classification, sector/derivative tagging, TRL estimation.
- **Tier 3 (Deep)**: Claude Sonnet detailed analysis for high-novelty findings.

## Testing

```bash
pytest tests/
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
├── sources/           # 8 API adapters
├── enrichment/        # Claude AI classification + analysis
├── collectors/        # Search orchestration + data import
└── outputs/           # Excel, Word, Streamlit exports
```
