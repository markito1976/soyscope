# SoyScope -- Start Here

> Complete onboarding guide for AI agents and developers. If you are new to this project, read this first.
> Also read `CLAUDE.md` at the project root for additional agent-specific instructions.

---

## 1. What Is SoyScope?

SoyScope is an **industrial soy application discovery tool** that systematically searches 14 academic, patent, and government APIs to build a comprehensive SQLite database of every known (and unknown) industrial use of soybeans over the past 25 years (2000--2026). It then uses Claude AI to enrich, classify, and score each finding for novelty.

**The core goal**: find soy applications that fall **outside** the known 200+ commercial products. The most valuable discoveries are the ones that do NOT fit existing categories.

### How It Works (Pipeline Overview)

```
Query Generation (19 derivatives x 19 sectors x 5 time windows)
        |
        v
Multi-API Parallel Search (14 sources, rate-limited, circuit-broken)
        |
        v
Deduplication (DOI-first + fuzzy title matching via rapidfuzz)
        |
        v
Reciprocal Rank Fusion (merge results from multiple APIs)
        |
        v
SQLite Storage (findings, sources, checkpoints)
        |
        v
AI Enrichment (3 tiers: rule-based catalog -> Claude summary -> deep analysis)
        |
        v
Novelty Detection (compare against 152 known commercial products)
        |
        v
Outputs (SQLite, Excel, Word, Streamlit dashboard, PySide6 desktop GUI)
```

### Who Uses It

This is a single-user desktop application used by the United Soybean Board (USB) to track and discover industrial applications of soy-based materials. It runs on one computer.

---

## 2. Project Structure

```
C:\EvalToolVersions\soy-industrial-tracker\
|
|-- CLAUDE.md                   -- AI agent instructions (READ FIRST)
|-- start-here.md               -- This document
|-- pyproject.toml              -- Package config, dependencies, entry points
|-- requirements.txt            -- Pinned dependencies (alternative to pyproject.toml)
|-- README.md                   -- Brief project readme
|-- SoyScope.bat                -- Windows launcher for the PySide6 GUI
|
|-- data/
|   |-- taxonomy.json           -- 19 sectors x 19 derivatives with keywords and subtypes
|   `-- soyscope.db             -- SQLite database (created at runtime by `soyscope init`)
|
|-- docs/
|   |-- soy-uses.md             -- Ground-truth reference: 200+ known soy applications (17 chapters)
|   `-- search-approaches.md    -- Blueprint: 27+ databases across 4 tiers
|
|-- cache/                      -- diskcache directory for search result caching
|-- exports/                    -- Generated Excel/Word reports
|-- logs/                       -- Application log files (soyscope.log)
|-- scripts/                    -- Utility scripts
|
|-- src/soyscope/               -- Main Python package
|   |-- __init__.py
|   |-- cli.py                  -- Typer CLI (build, refresh, enrich, init, gui, etc.)
|   |-- config.py               -- Settings from .env + defaults (APIConfig, Settings)
|   |-- db.py                   -- SQLite schema + Database class (all CRUD operations)
|   |-- models.py               -- Pydantic models (Paper, Finding, Enrichment, etc.)
|   |-- novelty.py              -- Novelty scoring against known applications
|   |-- known_apps_seed.py      -- 152 known commercial soy products (seed data)
|   |-- orchestrator.py         -- Multi-source parallel search orchestrator
|   |-- rate_limit.py           -- Token bucket rate limiter (per API)
|   |-- circuit_breaker.py      -- Circuit breaker for API fault tolerance
|   |-- dedup.py                -- DOI-first + fuzzy title deduplication (rapidfuzz)
|   |-- ranking.py              -- Reciprocal Rank Fusion for multi-source merging
|   |-- cache.py                -- diskcache wrapper for search results
|   |
|   |-- collectors/
|   |   |-- query_generator.py          -- Query plan: 19x19x5 grid + semantic + routing
|   |   |-- historical_builder.py       -- Full 25-year build with checkpoint/resume
|   |   |-- refresh_runner.py           -- Incremental updates since last run
|   |   |-- checkoff_importer.py        -- Soybean Checkoff DB JSON import
|   |   |-- usb_deliverables_importer.py -- USB deliverables CSV import
|   |   `-- oa_resolver.py              -- Unpaywall Open Access URL resolution
|   |
|   |-- enrichment/
|   |   |-- classifier.py       -- Claude-based sector/derivative classification
|   |   |-- summarizer.py       -- Claude-based finding summarization
|   |   |-- novelty_scorer.py   -- Heuristic novelty scoring (used in Tier 1)
|   |   `-- batch_enricher.py   -- 3-tier enrichment pipeline orchestrator
|   |
|   |-- sources/                -- One adapter per API (all implement SearchSource protocol)
|   |   |-- base.py             -- SearchSource protocol + BaseSource abstract class
|   |   |-- openalex_source.py  -- OpenAlex API adapter
|   |   |-- semantic_scholar.py -- Semantic Scholar API adapter
|   |   |-- crossref_source.py  -- Crossref API adapter
|   |   |-- pubmed_source.py    -- PubMed/NCBI API adapter
|   |   |-- exa_source.py       -- EXA neural search adapter
|   |   |-- tavily_source.py    -- Tavily web search adapter
|   |   |-- core_source.py      -- CORE open access aggregator adapter
|   |   |-- unpaywall_source.py -- Unpaywall OA resolver adapter
|   |   |-- osti_source.py      -- OSTI.gov (DOE research) adapter
|   |   |-- patentsview_source.py -- USPTO PatentsView adapter
|   |   |-- sbir_source.py      -- SBIR/STTR federal awards adapter
|   |   |-- agris_source.py     -- AGRIS/FAO agricultural records adapter
|   |   |-- lens_source.py      -- Lens.org scholarly + patents adapter
|   |   `-- usda_ers_source.py  -- USDA ERS/PubAg adapter
|   |
|   |-- outputs/
|   |   |-- excel_export.py     -- openpyxl Excel workbook generator
|   |   |-- word_export.py      -- python-docx Word report generator
|   |   `-- dashboard.py        -- Streamlit dashboard (launched via `soyscope dashboard`)
|   |
|   `-- gui/                    -- PySide6 desktop GUI
|       |-- main_window.py      -- QMainWindow with tabs, menu bar, shortcuts
|       |-- models/
|       |   |-- findings_model.py  -- QAbstractTableModel for findings table
|       |   `-- filter_proxy.py    -- QSortFilterProxyModel for search/filter
|       |-- views/              -- 6 tab views
|       |   |-- overview_tab.py    -- KPI cards, summary charts
|       |   |-- explorer_tab.py    -- Findings table with search, filter, detail panel
|       |   |-- matrix_tab.py      -- 19x19 sector/derivative heatmap
|       |   |-- trends_tab.py      -- Timeline and trend charts
|       |   |-- novel_uses_tab.py  -- High-novelty findings
|       |   `-- run_history_tab.py -- Build history + live Build Dashboard
|       |-- workers/            -- QRunnable background threads
|       |   |-- base_worker.py     -- Abstract base with signal support
|       |   |-- build_worker.py    -- Runs HistoricalBuilder in background
|       |   |-- data_worker.py     -- Loads findings from DB
|       |   |-- enrich_worker.py   -- Runs BatchEnricher in background
|       |   |-- import_worker.py   -- Runs CSV/JSON import in background
|       |   |-- stats_worker.py    -- Loads statistics from DB
|       |   `-- signals.py         -- Custom Qt signals
|       |-- widgets/            -- Reusable UI components
|       |   |-- kpi_card.py        -- KPI display card
|       |   |-- progress_panel.py  -- Build progress with ETA
|       |   |-- heatmap_widget.py  -- Sector x derivative heatmap
|       |   |-- timeline_widget.py -- Year-based timeline chart
|       |   |-- search_bar.py      -- Search input with live filtering
|       |   `-- detail_panel.py    -- Finding detail side panel
|       |-- delegates/          -- Custom QStyledItemDelegate renderers
|       |   |-- badge_delegate.py    -- Sector/source badge pills
|       |   |-- link_delegate.py     -- Clickable DOI/URL links
|       |   |-- multi_delegate.py    -- Multi-cell composite renderer
|       |   `-- progress_delegate.py -- Inline progress bar
|       `-- resources/
|           `-- themes/
|               |-- dark.qss    -- Dark mode stylesheet
|               `-- light.qss   -- Light mode stylesheet
|
`-- tests/
    |-- test_query_generator.py     -- Query plan generation and synonym expansion
    |-- test_known_applications.py  -- Known apps seed and DB seeding
    |-- test_novelty.py             -- Novelty scoring logic
    |-- test_db.py                  -- Database CRUD operations
    |-- test_dedup.py               -- Deduplication logic
    |-- test_enrichment.py          -- Enrichment pipeline
    |-- test_multi_source.py        -- Multi-source tracking (finding_sources)
    |-- test_checkpoints.py         -- Checkpoint/resume for builds
    |-- test_usb_deliverables.py    -- USB CSV import
    |-- test_oa_resolver.py         -- Unpaywall OA resolution
    `-- test_sources/
        |-- test_openalex.py        -- OpenAlex adapter tests
        `-- test_tier1_sources.py   -- Tier 1 source adapter tests
```

---

## 3. Tech Stack

| Component              | Technology                            | Purpose                                     |
|------------------------|---------------------------------------|---------------------------------------------|
| Language               | **Python 3.14**                       | Requires `>=3.11` per pyproject.toml        |
| Database               | **SQLite** (WAL mode)                 | All data storage, single-file DB            |
| Data Models            | **Pydantic v2**                       | Validated data structures throughout        |
| CLI Framework          | **Typer + Rich**                      | CLI commands with progress bars, tables     |
| Desktop GUI            | **PySide6** (Qt 6)                    | 6-tab desktop application with dark theme   |
| Web Dashboard          | **Streamlit + Plotly**                | Interactive web-based data exploration       |
| HTTP Client            | **httpx** (async)                     | API calls with async/await support          |
| Academic APIs          | **pyalex, semanticscholar, habanero** | OpenAlex, Semantic Scholar, Crossref SDKs   |
| Bio APIs               | **biopython**                         | PubMed/NCBI access                          |
| Neural Search          | **exa_py, tavily-python**             | EXA and Tavily web search                   |
| AI Enrichment          | **anthropic** (Claude SDK)            | Classification, summarization, deep analysis|
| Fuzzy Matching         | **rapidfuzz**                         | Title deduplication (>=90% threshold)        |
| Caching                | **diskcache**                         | Persistent on-disk search result cache       |
| Rate Limiting          | **aiolimiter, tenacity**              | Per-API rate limiting and retry logic        |
| Excel Export           | **openpyxl**                          | Multi-sheet workbook generation              |
| Word Export            | **python-docx**                       | Formatted report documents                   |
| Environment            | **python-dotenv**                     | .env file for API keys                       |
| Testing                | **pytest**                            | 243 tests                                   |
| Package Build          | **setuptools**                        | Editable install via `pip install -e .`      |

### Entry Point

Defined in `pyproject.toml`:
```toml
[project.scripts]
soyscope = "soyscope.cli:app"
```

This means after `pip install -e .`, the `soyscope` command is available globally. However, in some shell environments you may need to invoke it as:
```bash
python -c "from soyscope.cli import app; app()" -- <command>
```

---

## 4. Database Schema

The SQLite database lives at `data/soyscope.db` (configurable via `SOYSCOPE_DB_PATH` env var). The full schema is defined in `src/soyscope/db.py` in the `SCHEMA_SQL` constant. It uses WAL journal mode and has foreign keys enabled.

### Table: `findings`
The core table. One row per discovered paper/patent/report.

| Column              | Type      | Notes                                          |
|---------------------|-----------|-------------------------------------------------|
| id                  | INTEGER   | Primary key, autoincrement                      |
| title               | TEXT      | NOT NULL                                        |
| abstract            | TEXT      | May be NULL                                     |
| year                | INTEGER   | Publication year                                |
| doi                 | TEXT      | UNIQUE constraint -- primary dedup key          |
| url                 | TEXT      | Paper/patent URL                                |
| pdf_url             | TEXT      | Direct PDF link (from OA resolution)            |
| authors             | TEXT      | JSON array of author names                      |
| venue               | TEXT      | Journal/conference name                         |
| source_api          | TEXT      | Which API first found this (e.g. "openalex")    |
| source_type         | TEXT      | paper, patent, report, news, etc.               |
| citation_count      | INTEGER   | From API metadata                               |
| open_access_status  | TEXT      | gold, green, hybrid, bronze, closed             |
| raw_metadata        | TEXT      | JSON blob of original API response              |
| created_at          | TIMESTAMP | Auto-set                                        |
| updated_at          | TIMESTAMP | Auto-set, updated on DOI collision              |

Indexes: `doi`, `year`, `source_api`, `title`.

### Table: `sectors`
The 19 industry sectors.

| Column           | Type    | Notes                                        |
|------------------|---------|----------------------------------------------|
| id               | INTEGER | Primary key                                  |
| name             | TEXT    | UNIQUE, e.g. "Construction & Building Materials" |
| parent_id        | INTEGER | Self-referencing FK for subsectors           |
| description      | TEXT    | Optional                                     |
| is_ai_discovered | BOOLEAN | 0 = seeded from taxonomy, 1 = AI found new  |

### Table: `derivatives`
The 19 soy derivatives.

| Column           | Type    | Notes                                        |
|------------------|---------|----------------------------------------------|
| id               | INTEGER | Primary key                                  |
| name             | TEXT    | UNIQUE, e.g. "Soy Oil"                      |
| parent_id        | INTEGER | Self-referencing FK for sub-derivatives      |
| description      | TEXT    | Optional                                     |
| is_ai_discovered | BOOLEAN | 0 = seeded from taxonomy, 1 = AI found new  |

### Table: `finding_sectors`
Many-to-many: links findings to sectors.

| Column     | Type    | Notes                                |
|------------|---------|--------------------------------------|
| finding_id | INTEGER | FK -> findings(id)                   |
| sector_id  | INTEGER | FK -> sectors(id)                    |
| confidence | REAL    | 0.0--1.0 (0.6 = keyword, 0.85 = AI) |

### Table: `finding_derivatives`
Many-to-many: links findings to derivatives.

| Column        | Type    | Notes                                |
|---------------|---------|--------------------------------------|
| finding_id    | INTEGER | FK -> findings(id)                   |
| derivative_id | INTEGER | FK -> derivatives(id)                |
| confidence    | REAL    | 0.0--1.0 (0.6 = keyword, 0.85 = AI) |

### Table: `enrichments`
AI enrichment results. One row per finding (UNIQUE on finding_id).

| Column                  | Type      | Notes                                    |
|-------------------------|-----------|------------------------------------------|
| id                      | INTEGER   | Primary key                              |
| finding_id              | INTEGER   | UNIQUE FK -> findings(id)                |
| tier                    | TEXT      | "catalog", "summary", or "deep"          |
| trl_estimate            | INTEGER   | Technology Readiness Level (1--9)        |
| commercialization_status| TEXT      | research/pilot/scaling/commercial/mature |
| novelty_score           | REAL      | 0 = known, 100 = novel                  |
| ai_summary              | TEXT      | Claude-generated summary                 |
| key_metrics             | TEXT      | JSON blob                                |
| key_players             | TEXT      | JSON array of company/researcher names   |
| soy_advantage           | TEXT      | Why soy is better than alternatives      |
| barriers                | TEXT      | Commercialization barriers               |
| enriched_at             | TIMESTAMP | Auto-set                                 |
| model_used              | TEXT      | e.g. "claude-3-sonnet" or "dummy-seed-v1"|

### Table: `tags`
Freeform tags for findings.

| Column | Type    | Notes          |
|--------|---------|----------------|
| id     | INTEGER | Primary key    |
| name   | TEXT    | UNIQUE tag name|

### Table: `finding_tags`
Many-to-many: findings to tags.

| Column     | Type    | Notes              |
|------------|---------|--------------------|
| finding_id | INTEGER | FK -> findings(id) |
| tag_id     | INTEGER | FK -> tags(id)     |

### Table: `search_runs`
Tracks each build/refresh/search run.

| Column           | Type      | Notes                           |
|------------------|-----------|---------------------------------|
| id               | INTEGER   | Primary key                     |
| run_type         | TEXT      | "historical", "refresh", etc.   |
| started_at       | TIMESTAMP |                                 |
| completed_at     | TIMESTAMP |                                 |
| queries_executed | INTEGER   |                                 |
| findings_added   | INTEGER   |                                 |
| findings_updated | INTEGER   |                                 |
| api_costs_json   | TEXT      | JSON blob of per-API costs      |
| status           | TEXT      | "running", "completed", "failed"|

### Table: `search_queries`
Individual query records within a run.

| Column           | Type      | Notes                          |
|------------------|-----------|---------------------------------|
| id               | INTEGER   | Primary key                    |
| run_id           | INTEGER   | FK -> search_runs(id)          |
| query_text       | TEXT      |                                |
| api_source       | TEXT      |                                |
| results_returned | INTEGER   |                                |
| new_findings     | INTEGER   |                                |
| executed_at      | TIMESTAMP |                                |

### Table: `checkoff_projects`
Imported records from the Soybean Checkoff Research Database.

| Column      | Type      | Notes                              |
|-------------|-----------|-------------------------------------|
| id          | INTEGER   | Primary key (from source)          |
| year        | TEXT      |                                    |
| title       | TEXT      |                                    |
| category    | TEXT      |                                    |
| keywords    | TEXT      | JSON array                         |
| lead_pi     | TEXT      |                                    |
| institution | TEXT      |                                    |
| funding     | REAL      | Dollar amount                      |
| summary     | TEXT      |                                    |
| objectives  | TEXT      |                                    |
| url         | TEXT      |                                    |
| imported_at | TIMESTAMP | Auto-set                           |

### Table: `usb_deliverables`
USB-funded research deliverables imported from CSV.

| Column             | Type      | Notes                                    |
|--------------------|-----------|------------------------------------------|
| id                 | INTEGER   | Primary key, autoincrement               |
| title              | TEXT      | NOT NULL                                 |
| doi_link           | TEXT      | DOI or URL                               |
| deliverable_type   | TEXT      |                                          |
| submitted_year     | INTEGER   |                                          |
| published_year     | INTEGER   |                                          |
| month              | TEXT      |                                          |
| journal_name       | TEXT      |                                          |
| authors            | TEXT      |                                          |
| combined_authors   | TEXT      |                                          |
| funders            | TEXT      |                                          |
| usb_project_number | TEXT      |                                          |
| investment_category| TEXT      |                                          |
| key_categories     | TEXT      |                                          |
| keywords           | TEXT      | JSON array                               |
| pi_name            | TEXT      |                                          |
| pi_email           | TEXT      |                                          |
| organization       | TEXT      |                                          |
| priority_area      | TEXT      |                                          |
| raw_csv_row        | TEXT      | JSON blob of the original CSV row        |
| imported_at        | TIMESTAMP | Auto-set                                 |

UNIQUE constraint on `(title, doi_link)`.

### Table: `finding_sources`
Multi-source tracking: records which API sources discovered each finding. A finding found by 3 APIs will have 3 rows here.

| Column        | Type      | Notes                              |
|---------------|-----------|------------------------------------|
| finding_id    | INTEGER   | FK -> findings(id)                 |
| source_api    | TEXT      | e.g. "openalex", "crossref"       |
| discovered_at | TIMESTAMP | Auto-set                           |

Primary key on `(finding_id, source_api)`.

### Table: `search_checkpoints`
Checkpoint/resume support for large builds. Each completed query is recorded so interrupted builds can skip already-completed work.

| Column           | Type      | Notes                                    |
|------------------|-----------|------------------------------------------|
| id               | INTEGER   | Primary key                              |
| run_id           | INTEGER   | FK -> search_runs(id)                    |
| query_hash       | TEXT      | SHA-256 hash of the query plan           |
| query_text       | TEXT      | The actual query string                  |
| query_type       | TEXT      | academic, semantic, web, patent, govt    |
| derivative       | TEXT      | Which derivative this query targets      |
| sector           | TEXT      | Which sector this query targets          |
| year_start       | INTEGER   |                                          |
| year_end         | INTEGER   |                                          |
| status           | TEXT      | "pending", "completed", "failed"         |
| new_findings     | INTEGER   |                                          |
| updated_findings | INTEGER   |                                          |
| completed_at     | TIMESTAMP |                                          |

UNIQUE constraint on `(run_id, query_hash)`.

### Table: `known_applications`
Ground-truth inventory of 152 known commercial soy-based products, seeded from `known_apps_seed.py`.

| Column            | Type    | Notes                                    |
|-------------------|---------|------------------------------------------|
| id                | INTEGER | Primary key                              |
| product_name      | TEXT    | e.g. "PureBond", "Envirotemp FR3"       |
| manufacturer      | TEXT    | e.g. "Columbia Forest Products"          |
| sector            | TEXT    | NOT NULL, e.g. "Adhesives & Sealants"   |
| derivative        | TEXT    | e.g. "Soy Protein"                      |
| category          | TEXT    | NOT NULL, e.g. "Wood adhesives"          |
| market_size       | TEXT    | e.g. "$2.3B soy adhesive market by 2028"|
| description       | TEXT    | Product description                      |
| year_introduced   | INTEGER | Year product was launched                |
| is_commercialized | BOOLEAN | Default 1                                |
| source_doc        | TEXT    | Default "soy-uses.md"                   |

---

## 5. The Taxonomy (19 x 19)

The taxonomy defines the complete search space: every combination of soy derivative and industry sector. It is stored in `data/taxonomy.json` and also hard-coded in `src/soyscope/collectors/query_generator.py`.

### 19 Soy Derivatives

1. **Soy Oil** -- Primary industrial derivative (coatings, lubricants, biodiesel, plastics)
2. **Soy Protein** -- Isolate/concentrate/flour for adhesives, fibers, bio-materials
3. **Soy Meal** -- Defatted byproduct for adhesives, fermentation substrates
4. **Soy Lecithin** -- Phospholipid emulsifier for coatings, release agents
5. **Soy Fiber** -- Cellulosic/dietary fiber for composites, building materials
6. **Soy Wax** -- Hydrogenated soy oil for candles, coatings, packaging
7. **Soy Hulls** -- Outer coating for composites, fermentation feedstock
8. **Soy-based Polyols** -- For polyurethane foams, coatings, elastomers
9. **Soy Isoflavones** -- Genistein/daidzein for nutraceuticals, biomaterials
10. **Soy Fatty Acids** -- Oleic/linoleic for surfactants, lubricants
11. **Glycerol soy-derived** -- Biodiesel byproduct for chemicals, solvents
12. **Soy-based Resins** -- Alkyd/epoxy/polyester for composites, coatings
13. **Whole Soybean** -- Direct processing and fermentation
14. **Methyl Soyate** -- Industrial solvent, agricultural adjuvant, cleaning agent
15. **Epoxidized Soybean Oil** -- PVC plasticizer/stabilizer, coating intermediate
16. **Phytosterols** -- Steroid drug precursors, nutraceuticals
17. **Azelaic Acid** -- C9 dicarboxylic acid for polymers, lubricants, cosmetics
18. **Dimer Fatty Acids** -- Hot-melt adhesives, polyamide resins, corrosion inhibitors
19. **Soy Molasses** -- Fermentation substrate from SPC production

### 19 Industry Sectors

1. Construction & Building Materials
2. Automotive & Transportation
3. Packaging & Containers
4. Textiles & Fibers
5. Coatings, Paints & Inks
6. Adhesives & Sealants
7. Plastics & Bioplastics
8. Lubricants & Metalworking Fluids
9. Energy & Biofuels
10. Chemicals & Solvents
11. Personal Care & Cosmetics
12. Cleaning Products & Surfactants
13. Agriculture
14. Electronics
15. Firefighting Foam
16. Rubber & Elastomers
17. Pharmaceuticals & Medical
18. Candles & Home Products
19. Paper & Printing

### SECTOR_KEYWORDS

Each sector has 15--25 targeted keywords defined in `SECTOR_KEYWORDS` (in `query_generator.py`). These are used instead of sector names in queries to prevent Crossref from matching journal names. For example:

```python
SECTOR_KEYWORDS = {
    "Construction & Building Materials": [
        "adhesive", "insulation", "composite", "concrete", "plywood",
        "particleboard", "oriented strand board", "OSB", "structural panel",
        "spray foam", "rigid foam", "PoreShield", "asphalt rejuvenator",
        "recycled asphalt pavement", "dust suppressant", "concrete sealant",
        "SME-PS", "wood panel", "structural adhesive", "subfloor adhesive",
        "foundation coating", "roof insulation", "building envelope",
    ],
    # ... 18 more sectors
}
```

### How Queries Are Generated

For each derivative-sector pair, the generator produces multiple query types:

1. **Academic queries** (`generate_academic_queries`): derivative name + 2 sector keywords with Boolean operators. Example: `"Soy Oil" AND ("adhesive" OR "insulation")`
2. **Synonym expansion**: soy/soybean/soy bean variants paired with derivative + keyword
3. **Semantic queries** (`generate_semantic_queries`): natural language for EXA neural search
4. **Web queries** (`generate_web_queries`): industry/market-focused for Tavily
5. **Patent queries** (`generate_patent_queries`): derivative synonyms + keywords for PatentsView/Lens
6. **Government queries** (`generate_govt_queries`): research-focused for OSTI/SBIR/USDA

---

## 6. API Sources (14)

All sources implement the `SearchSource` protocol defined in `src/soyscope/sources/base.py`:

```python
class SearchSource(Protocol):
    @property
    def name(self) -> str: ...
    async def search(self, query: str, max_results: int = 100,
                     year_start: int | None = None,
                     year_end: int | None = None, **kwargs) -> SearchResult: ...
    async def get_by_doi(self, doi: str) -> Paper | None: ...
```

### Original 8 Sources

| # | Source           | File                    | Auth Required     | Rate Limit | Status    |
|---|------------------|-------------------------|-------------------|------------|-----------|
| 1 | **OpenAlex**     | `openalex_source.py`    | Email (polite)    | 10 qps     | Working   |
| 2 | **Semantic Scholar** | `semantic_scholar.py` | API key (optional)| 1 qps      | Working   |
| 3 | **Crossref**     | `crossref_source.py`    | Email (polite)    | 50 qps     | Working   |
| 4 | **PubMed**       | `pubmed_source.py`      | API key + email   | 10 qps     | Working   |
| 5 | **EXA**          | `exa_source.py`         | API key (required)| 5 qps      | Working   |
| 6 | **Tavily**       | `tavily_source.py`      | API key (required)| 5 qps      | Working   |
| 7 | **CORE**         | `core_source.py`        | API key (optional)| 0.5 qps    | Working   |
| 8 | **Unpaywall**    | `unpaywall_source.py`   | Email (required)  | 10 qps     | Working   |

### Tier 1 Sources (added Feb 13, 2026)

| # | Source           | File                     | Auth Required      | Rate Limit | Status               |
|---|------------------|--------------------------|--------------------|------------|----------------------|
| 9 | **OSTI.gov**     | `osti_source.py`         | None               | 1 qps      | Working              |
| 10| **PatentsView**  | `patentsview_source.py`  | Free key (pending) | 0.75 qps   | Key pending          |
| 11| **SBIR/STTR**    | `sbir_source.py`         | None               | 1 qps      | Working              |
| 12| **AGRIS/FAO**    | `agris_source.py`        | None               | 1 qps      | **403 errors**       |
| 13| **Lens.org**     | `lens_source.py`         | Bearer token       | 0.83 qps   | Token pending        |
| 14| **USDA ERS**     | `usda_ers_source.py`     | API key (optional) | 1 qps      | **APIs currently down** |

### API Routing

The query generator routes different query types to appropriate APIs:

```python
_ACADEMIC_APIS_TIER1 = ["openalex", "semantic_scholar", "pubmed", "crossref", "agris"]
_SEMANTIC_APIS = ["exa"]
_WEB_APIS = ["tavily"]
_PATENT_APIS = ["patentsview", "lens"]
_GOVT_REPORT_APIS = ["osti", "sbir", "usda_ers"]
```

### Environment Variables for API Keys

Set these in a `.env` file at the project root:

```env
# Required for full functionality
EXA_API_KEY=your_key
TAVILY_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Recommended (polite pool / higher rate limits)
OPENALEX_EMAIL=you@example.com
CROSSREF_EMAIL=you@example.com
PUBMED_API_KEY=your_key
PUBMED_EMAIL=you@example.com
UNPAYWALL_EMAIL=you@example.com

# Optional
SEMANTIC_SCHOLAR_API_KEY=your_key
CORE_API_KEY=your_key

# Tier 1 (pending registration)
PATENTSVIEW_API_KEY=your_key
LENS_API_KEY=your_key
USDA_ERS_API_KEY=your_key

# Optional overrides
SOYSCOPE_DB_PATH=data/soyscope.db
SOYSCOPE_CACHE_DIR=cache
SOYSCOPE_LOG_LEVEL=INFO
```

---

## 7. CLI Commands

The CLI is built with Typer and uses Rich for console output. All commands are defined in `src/soyscope/cli.py`.

### `soyscope init`
Initialize the database, create schema, seed the 19x19 taxonomy and 152 known applications.

```bash
soyscope init
soyscope init --verbose
```

### `soyscope build`
Run the full 25-year historical database build. This generates thousands of queries across all derivative x sector x time window combinations and searches all enabled APIs.

```bash
soyscope build                        # Full build
soyscope build --resume               # Resume interrupted build
soyscope build --concurrency 5        # 5 concurrent API queries (default: 3)
soyscope build --max-queries 100      # Limit to 100 queries (for testing)
soyscope build -v -c 3 -m 50 -r      # All flags combined
```

### `soyscope refresh`
Incremental update since last run or a specified date. Uses a lighter query set than full build.

```bash
soyscope refresh                      # Since last run
soyscope refresh --since 2025         # Since 2025
soyscope refresh --since 2025-06-01   # Since June 2025
soyscope refresh -c 5 -m 200         # Concurrent + limit
```

### `soyscope enrich`
Run AI enrichment on un-enriched findings. Has 3 tiers.

```bash
soyscope enrich                       # All tiers
soyscope enrich --tier 1              # Tier 1 only (rule-based, no AI cost)
soyscope enrich --tier 2              # Tier 2 only (Claude classification)
soyscope enrich --tier 3              # Tier 3 only (Claude deep analysis)
soyscope enrich --tier 2 --limit 100  # Process max 100 findings
```

### `soyscope search`
Ad-hoc search across all APIs. Results displayed in Rich table.

```bash
soyscope search "soybean adhesive wood panel"
soyscope search "soy biodiesel" --sources openalex,crossref
soyscope search "soy foam insulation" --max 50 --store  # Save to DB
```

### `soyscope import-checkoff`
Import Soybean Checkoff Research DB data (7,344 projects from `soybean_scraper`).

```bash
soyscope import-checkoff
soyscope import-checkoff --path /path/to/all_projects.json
```

### `soyscope import-deliverables`
Import USB-funded research deliverables from CSV.

```bash
soyscope import-deliverables --path deliverables.csv
soyscope import-deliverables --path deliverables.csv --no-resolve-oa
```

### `soyscope resolve-oa`
Resolve Open Access URLs for findings with DOIs via Unpaywall.

```bash
soyscope resolve-oa                   # Resolve all unresolved
soyscope resolve-oa --limit 500       # Max 500 DOIs
```

### `soyscope backfill-sources`
Seed the `finding_sources` junction table from existing `findings.source_api` column.

```bash
soyscope backfill-sources
```

### `soyscope stats`
Display database statistics: total findings, enrichments by tier, findings by source, etc.

```bash
soyscope stats
```

### `soyscope export excel`
Generate a multi-sheet Excel workbook.

```bash
soyscope export excel
soyscope export excel --output my_report.xlsx
```

### `soyscope export word`
Generate a formatted Word document report.

```bash
soyscope export word
soyscope export word --output my_report.docx
```

### `soyscope dashboard`
Launch the Streamlit web dashboard.

```bash
soyscope dashboard
```

### `soyscope gui`
Launch the PySide6 desktop GUI application.

```bash
soyscope gui
```

---

## 8. Search Strategy

### The Grid: 19 x 19 x 5

The core search strategy is a systematic grid search across:
- **19 derivatives** (soy materials)
- **19 sectors** (industry applications)
- **5 time windows**: (2000-2004), (2005-2009), (2010-2014), (2015-2019), (2020-2026)

For each cell in this 19 x 19 x 5 grid, multiple query types are generated.

### SOY_SYNONYMS Expansion

Every search query containing a soy reference is expanded using 5 synonyms for worldwide coverage:

```python
SOY_SYNONYMS = ["soy", "soybean", "soy bean", "soya", "soja"]
```

The `expand_soy_synonyms("{soy} oil adhesive")` function produces:
```
["soy oil adhesive", "soybean oil adhesive", "soy bean oil adhesive",
 "soya oil adhesive", "soja oil adhesive"]
```

### Query Types and Their Targets

For each derivative-sector combination, the following query types are generated:

1. **Academic** (5 queries per cell x 5 time windows = 25 per pair)
   - Target: OpenAlex, Semantic Scholar, PubMed, Crossref, AGRIS
   - Example: `"Soy Oil" AND ("adhesive" OR "insulation")`
   - Includes synonym variants: `"soybean" AND "oil" AND "adhesive"`

2. **Government** (4 queries per cell x 5 time windows = 20 per pair)
   - Target: OSTI, SBIR, USDA ERS
   - Example: `"soy oil adhesive research"`, `"soybean adhesive biobased"`

3. **Semantic** (4 queries per cell, no time split)
   - Target: EXA neural search
   - Example: `"soy Soy Oil used as alternative adhesive"`

4. **Web** (4 queries per cell, no time split)
   - Target: Tavily
   - Example: `"soy-based adhesive product commercial market"`

5. **Patent** (3 queries per cell, no time split)
   - Target: PatentsView, Lens.org
   - Example: `"soy oil adhesive"`, `"soybean oil adhesive"`

6. **Implicit Semantic** (25 cross-cutting queries)
   - Target: EXA, OpenAlex, Semantic Scholar
   - These queries do NOT mention soy -- they target the chemistry/technology
   - Example: `"polyurethane foam plant-derived polyol"`
   - Purpose: discover papers that describe soy applications without ever saying "soy"

### Total Query Count

The full build plan generates approximately:

```
Academic:  19 x 19 x 5 x ~5 queries  = ~9,025
Government: 19 x 19 x 5 x ~4 queries = ~7,220
Semantic:  19 x 19 x ~4 queries       = ~1,444
Web:       19 x 19 x ~4 queries       = ~1,444
Patent:    19 x 19 x ~3 queries       = ~1,083
Implicit:  25 queries                  =    25
                                         ------
Total:                                  ~19,975+ queries
```

### Checkpoint/Resume

Large builds can be interrupted and resumed. Each completed query is recorded in `search_checkpoints` with a deterministic SHA-256 hash. When `--resume` is used, the builder checks which query hashes are already marked as "completed" and skips them.

```python
def _query_hash(plan: QueryPlan) -> str:
    key = f"{plan.query}|{plan.query_type}|{plan.year_start}|{plan.year_end}|{','.join(sorted(plan.target_apis))}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

### Deduplication

Results from multiple APIs are deduplicated using a two-stage approach:

1. **DOI-first**: If two papers share the same DOI (normalized to lowercase, URL prefixes stripped), they are the same paper.
2. **Fuzzy title matching**: If no DOI match, use rapidfuzz `fuzz.ratio()` with a threshold of 90% to catch title variants.

```python
from rapidfuzz import fuzz

def is_duplicate_title(title_a: str, title_b: str, threshold: float = 90.0) -> bool:
    na = normalize_title(title_a)  # lowercase, strip punctuation, collapse whitespace
    nb = normalize_title(title_b)
    return fuzz.ratio(na, nb) >= threshold
```

### Reciprocal Rank Fusion

After deduplication, results from multiple APIs are merged using RRF scoring:

```
score(paper) = sum(1 / (k + rank_i))  for each API that returned it
```

where `k = 60` (per the original RRF paper). Papers that appear in more result lists get higher scores. The richest metadata version (most fields populated) is kept.

---

## 9. Known Applications and Novelty Detection

### Known Applications

The `known_applications` table contains 152 entries of known commercial soy-based products, extracted from the comprehensive reference document `docs/soy-uses.md`. The seed data is in `src/soyscope/known_apps_seed.py`.

Example entries:

```python
KnownApplication(
    sector="Adhesives & Sealants",
    derivative="Soy Protein",
    category="Wood adhesives",
    product_name="PureBond",
    manufacturer="Columbia Forest Products",
    description="Formaldehyde-free soy protein adhesive for hardwood plywood",
    year_introduced=2005,
    market_size="$2.3B soy adhesive market by 2028",
)
KnownApplication(
    sector="Lubricants & Metalworking Fluids",
    derivative="Soy Oil",
    category="Dielectric fluids",
    product_name="Envirotemp FR3",
    manufacturer="Cargill",
    description="Soy natural ester for power transformers; 3M+ units installed globally",
    year_introduced=1998,
)
```

The `soyscope init` command seeds both the taxonomy and known applications automatically.

### Novelty Scoring

The novelty scorer (`src/soyscope/novelty.py`) compares each finding against all 152 known applications to determine if it describes something truly new.

**Scoring method** (from `score_finding_novelty()`):

1. **Product name matching** (highest weight): Direct substring match (sim = 1.0) or fuzzy match (sim x 0.7)
2. **Manufacturer matching**: Substring (0.5) or fuzzy (x 0.3)
3. **Description similarity**: Fuzzy match against title (x 0.6) or abstract (x 0.5)
4. **Category keyword matching**: Word overlap (x 0.4)
5. **Sector keyword cross-check**: SECTOR_KEYWORDS overlap contributes up to 0.3

The composite similarity is converted to novelty:
```python
novelty_score = (1.0 - best_similarity) * 100  # 0 = known, 100 = novel
```

**Interpretation**:
| Score Range | Meaning                                          |
|-------------|--------------------------------------------------|
| 0--19       | Strong match to known product                    |
| 20--39      | Moderate match to known application               |
| 40--59      | Weak match -- may be a variant                   |
| 60--79      | Low similarity -- potentially novel              |
| 80--100     | No significant match -- high novelty             |

**Threshold**: Findings with novelty score >= 70 are considered "high novelty" candidates.

**Batch scoring**:
```python
from soyscope.novelty import get_novel_findings

novel = get_novel_findings(findings, known_apps, threshold=70.0)
# Returns list of NoveltyResult sorted by novelty_score descending
```

---

## 10. Enrichment Pipeline

The enrichment pipeline (`src/soyscope/enrichment/batch_enricher.py`) processes findings through 3 tiers of increasing depth and cost.

### Tier 1: Catalog (Rule-Based, No AI Cost)

- **Input**: All un-enriched findings
- **Method**: Keyword matching against sector names and derivative names
- **Output**:
  - `finding_sectors` links (confidence 0.6)
  - `finding_derivatives` links (confidence 0.6)
  - Heuristic novelty score via `enrichment/novelty_scorer.py`
  - Enrichment record with `tier="catalog"`
- **Cost**: Zero (no API calls)
- **Speed**: Fast -- processes thousands per minute

### Tier 2: Summary (Claude AI Classification)

- **Input**: Findings that have Tier 1 but no Tier 2 enrichment
- **Method**: Claude API batch classification
- **Batch size**: 20 findings per API call (configurable)
- **Output**:
  - Sector/derivative classification (confidence 0.85)
  - **AI-discovered sectors/derivatives** (new categories not in the taxonomy)
  - Tags
  - TRL estimate (Technology Readiness Level 1--9)
  - Commercialization status (research/pilot/scaling/commercial/mature)
  - Novelty score (AI-assessed)
  - AI summary
  - Key metrics, key players
  - Soy advantage description
  - Barriers to commercialization
- **Cost**: ~$0.01 per finding (Claude Sonnet)
- **Requires**: `ANTHROPIC_API_KEY` in `.env`

### Tier 3: Deep Analysis (Claude AI Deep Dive)

- **Input**: High-value findings (high novelty, high citation count)
- **Method**: Individual Claude API calls with detailed prompts
- **Limit**: Default max 50 findings per run
- **Output**: Extended analysis, market assessment, competitive landscape
- **Cost**: ~$0.05 per finding (Claude Sonnet with longer prompts)

### Running Enrichment

```bash
soyscope enrich              # All tiers sequentially
soyscope enrich --tier 1     # Tier 1 only (fast, free)
soyscope enrich --tier 2 --limit 200  # Tier 2 for 200 findings
soyscope enrich --tier 3 --limit 20   # Tier 3 for top 20
```

---

## 11. GUI Architecture

The PySide6 desktop GUI (`src/soyscope/gui/`) follows an MVD (Model-View-Delegate) architecture with background workers for non-blocking operations.

### Main Window

`main_window.py` creates a `QMainWindow` with:
- **Menu bar**: File (import, export), View (themes), Run (build, enrich)
- **Tab widget**: 6 tabs
- **Status bar**: Database path, finding count, last refresh
- **Keyboard shortcuts**: Ctrl+I (import), Ctrl+E (export), Ctrl+R (refresh)
- **Theme**: Dark mode by default (dark.qss/light.qss)

### 6 Tabs

1. **Overview** (`overview_tab.py`): KPI cards (total findings, enriched count, novel count, source breakdown), summary charts
2. **Explorer** (`explorer_tab.py`): Full findings table with search bar, column sorting, filter proxy, detail side panel
3. **Matrix** (`matrix_tab.py`): 19x19 sector-derivative heatmap showing finding density
4. **Trends** (`trends_tab.py`): Timeline chart showing findings by year, trend analysis
5. **Novel Uses** (`novel_uses_tab.py`): High-novelty findings filtered and ranked
6. **Run History** (`run_history_tab.py`): Past build/refresh runs + live Build Dashboard

### Build Dashboard (in Run History tab)

When a build is running, the dashboard shows:
- **API Source Health Grid**: 14 sources with green/red/grey status dots
- **Live Progress Panel**: Query counter, progress bar, ETA, queries/sec rate
- **Findings Feed**: Scrolling list of newly discovered findings, color-coded by source type
- **Per-Source Stats Table**: Queries sent, results returned, errors, status per API
- Auto-shows on build start, auto-hides on completion

### Background Workers

All long-running operations use `QRunnable` workers that run in `QThreadPool`:

- `BuildWorker`: Runs `HistoricalBuilder.build()` in background
- `EnrichWorker`: Runs `BatchEnricher.run_all_tiers()` in background
- `ImportWorker`: Runs CSV/JSON import in background
- `DataWorker` / `FindingsLoadWorker`: Loads findings from DB for display
- `StatsWorker`: Loads aggregate statistics

Workers emit custom Qt signals for progress updates, completion, and errors.

### Custom Widgets

- `KPICard`: Displays a metric with label, value, and optional trend indicator
- `ProgressPanel`: Build progress with progress bar, ETA, rate display
- `HeatmapWidget`: Sector x derivative heatmap with color gradient
- `TimelineWidget`: Year-based bar/line chart
- `SearchBar`: Live-filtering text input
- `DetailPanel`: Side panel showing full finding details

### Custom Delegates

- `BadgeDelegate`: Renders sector/source names as colored badge pills
- `LinkDelegate`: Renders DOIs/URLs as clickable hyperlinks
- `MultiDelegate`: Composites multiple renderers in one cell
- `ProgressDelegate`: Inline progress bar in table cells

### Launching

```bash
soyscope gui          # From CLI
python -m soyscope.gui.main_window  # Direct
# Or use the batch file:
SoyScope.bat
```

---

## 12. Testing

### Test Suite: 243 Tests

Run all tests:
```bash
pytest tests/
```

Run specific test files:
```bash
pytest tests/test_query_generator.py   # Query generation and synonym expansion
pytest tests/test_novelty.py           # Novelty scoring
pytest tests/test_db.py                # Database CRUD
pytest tests/test_dedup.py             # Deduplication logic
pytest tests/test_enrichment.py        # Enrichment pipeline
pytest tests/test_multi_source.py      # finding_sources junction table
pytest tests/test_checkpoints.py       # Checkpoint/resume
pytest tests/test_usb_deliverables.py  # USB CSV import
pytest tests/test_oa_resolver.py       # Unpaywall OA resolution
pytest tests/test_known_applications.py # Known apps seeding
pytest tests/test_sources/             # API source adapters
```

### Test Configuration

From `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Tests use in-memory SQLite databases (`:memory:`) and mock API responses. No API keys or network access needed to run tests.

### Key Test Files

| File                          | Tests                                           |
|-------------------------------|--------------------------------------------------|
| `test_query_generator.py`     | Full plan generation, synonym expansion, routing, SECTOR_KEYWORDS, query counts |
| `test_novelty.py`             | Novelty scoring: known products score low, unknown score high |
| `test_db.py`                  | Schema creation, insert/get/update findings, sector/derivative CRUD |
| `test_dedup.py`               | DOI normalization, fuzzy title matching, Deduplicator class |
| `test_enrichment.py`          | Tier 1 keyword matching, Tier 2 mock classification |
| `test_multi_source.py`        | finding_sources tracking, backfill, multi-source queries |
| `test_checkpoints.py`         | Checkpoint creation, resume logic, query hash determinism |
| `test_usb_deliverables.py`    | CSV parsing, import, OA resolution |
| `test_oa_resolver.py`         | Unpaywall DOI resolution, batch processing |
| `test_known_applications.py`  | Seed data integrity, DB seeding, sector coverage |
| `test_sources/test_openalex.py`   | OpenAlex adapter with mocked responses |
| `test_sources/test_tier1_sources.py` | OSTI, SBIR, PatentsView, AGRIS, Lens adapters |

---

## 13. Current Data State

As of February 14, 2026:

| Metric                  | Value                                          |
|-------------------------|-------------------------------------------------|
| USB Deliverables        | 1,010 imported findings                         |
| Known Applications      | 152 commercial products in `known_applications` |
| Sectors                 | 19 (16 original + 3 added)                     |
| Derivatives             | 19 (14 original - 1 duplicate + 6 new)         |
| Enrichments (DUMMY)     | 300 dummy records (model_used='dummy-seed-v1')  |
| Irrelevant Findings     | ~1,640 from old Crossref query bug (now fixed) |
| Multi-source Records    | 6,619 in finding_sources                        |
| OA Resolved DOIs        | 979/982                                         |
| Test Count              | 243 passing                                     |
| Total Query Plan        | ~19,975 queries in full build plan              |

### Imported Data Sources

- **USB Deliverables**: 1,027 raw CSV rows -> 1,010 unique findings after deduplication
- **Soybean Checkoff DB**: 7,344 projects available at `C:\EvalToolVersions\soybean_scraper\all_projects.json`
- **API Searches**: Not yet run at scale (pending historical build)

---

## 14. Known Issues and Warnings

### Critical: Dummy Enrichments Must Be Purged

The enrichments table contains **300 dummy records** inserted by `seed_dummy_data.py` for UI development. These have `model_used = 'dummy-seed-v1'` and contain fake data. **They must be purged before running real AI enrichment.**

To identify them:
```sql
SELECT COUNT(*) FROM enrichments WHERE model_used = 'dummy-seed-v1';
```

To purge:
```sql
DELETE FROM enrichments WHERE model_used = 'dummy-seed-v1';
```

### Irrelevant Crossref Findings

Approximately **1,640 irrelevant findings** were imported from a now-fixed Crossref query bug. The old queries used sector names (e.g., "Textiles & Fibers") which Crossref matched against journal titles (e.g., "Journal of Textiles and Fiber Science") instead of article content. The fix: use SECTOR_KEYWORDS (specific terms like "fiber", "fabric", "textile") instead of full sector names.

### API Issues

| Source     | Issue                                                     |
|------------|-----------------------------------------------------------|
| AGRIS/FAO  | Currently returning HTTP 403 (access denied)              |
| USDA ERS   | PubAg APIs currently down / unreachable                   |
| PatentsView| API key registration submitted Feb 13, pending            |
| Lens.org   | Bearer token registration submitted Feb 13, pending       |

### Other Notes

- The `Soybean Hulls` derivative was consolidated into `Soy Hulls` (subtypes merged)
- Some findings have NULL abstracts (especially from Crossref and patent sources)
- The novelty scorer works best when findings have both title AND abstract

---

## 15. Next Steps / Priorities

Listed in priority order:

1. **Search strategy redesign** -- The user's core interest is finding novel soy uses that fall OUTSIDE the known 200+ application matrix. Current grid search is systematic but may miss truly novel uses that do not fit any existing derivative-sector pair. Needs open-ended discovery queries.

2. **Run historical build via GUI** -- Execute the full ~19,975-query build using the Build Dashboard for transparency. Use `soyscope build` or the GUI's Run History tab.

3. **Purge dummy enrichments** -- Delete the 300 `model_used='dummy-seed-v1'` records from the enrichments table.

4. **Run real AI enrichment** -- After purging dummies, run `soyscope enrich` to process findings through all 3 tiers using Claude.

5. **GUI updates**:
   - Matrix tab should display the full 19x19 heatmap
   - Novel Uses tab should use novelty scoring from `novelty.py`
   - Add time, country, geography as selectable matrix dimensions

6. **API key activation** -- PatentsView and Lens.org API keys were submitted Feb 13 and take days to process. Once received, update `.env` and test.

7. **Investigate soybeanresearchdata.com** -- Potential new data source.

8. **Matrix visualization** -- Add time, country, and geography as selectable dimensions.

---

## 16. Environment Setup

### Prerequisites

- Python 3.11 or newer (project uses 3.14)
- pip (for editable install)
- Git (for cloning)

### Installation

```bash
# Clone
git clone https://github.com/markito1976/soyscope.git
cd soy-industrial-tracker

# Editable install (installs all dependencies from pyproject.toml)
pip install -e .

# Verify
soyscope --help
```

### Configuration

Create a `.env` file at the project root:

```env
# Required for AI enrichment
ANTHROPIC_API_KEY=sk-ant-...

# Required for EXA neural search
EXA_API_KEY=...

# Required for Tavily web search
TAVILY_API_KEY=...

# Recommended for polite API access
OPENALEX_EMAIL=you@example.com
CROSSREF_EMAIL=you@example.com
PUBMED_EMAIL=you@example.com
UNPAYWALL_EMAIL=you@example.com

# Optional
SEMANTIC_SCHOLAR_API_KEY=...
CORE_API_KEY=...
PUBMED_API_KEY=...
```

### Initialize Database

```bash
soyscope init
```

This creates `data/soyscope.db`, applies the schema, seeds 19 sectors, 19 derivatives, and 152 known applications.

### Verify Installation

```bash
soyscope stats          # Should show sector/derivative counts
pytest tests/           # Should pass all 243 tests
soyscope gui            # Should launch the PySide6 desktop app
```

### PySide6 GUI

The GUI requires PySide6 which is not in `pyproject.toml` dependencies (it is a large optional dependency). Install it separately:

```bash
pip install PySide6
soyscope gui
```

Or use the Windows launcher batch file:
```bash
SoyScope.bat
```

---

## 17. Key Design Decisions

### Sector Keywords Instead of Sector Names

**Problem**: When we used full sector names like "Textiles & Fibers" in Crossref queries, Crossref matched them against journal names (e.g., "Journal of Textiles and Fiber Science"), returning thousands of irrelevant results.

**Solution**: Use SECTOR_KEYWORDS -- specific technical terms like "fiber", "fabric", "textile", "yarn", "nonwoven" -- paired with derivative names. This forces Crossref (and other APIs) to match against article content rather than metadata.

### SOY_SYNONYMS for Worldwide Coverage

**Problem**: Different regions use different terms for soy. American papers say "soybean", British papers say "soya", Latin American and European papers say "soja".

**Solution**: Every query containing a soy reference is expanded into 5 variants:
```python
SOY_SYNONYMS = ["soy", "soybean", "soy bean", "soya", "soja"]
```

### Checkpoint/Resume for Large Builds

**Problem**: The full build plan has ~19,975 queries. At 3 concurrent queries, this takes hours. Network failures, rate limiting, and session interruptions are inevitable.

**Solution**: Every completed query is checkpointed in `search_checkpoints` with a deterministic hash. The `--resume` flag loads previously completed hashes and skips them, so no work is repeated.

### Multi-Source Tracking via Junction Table

**Problem**: The same paper can be found by multiple APIs (e.g., both OpenAlex and Semantic Scholar return the same DOI). We need to know which APIs discovered each finding.

**Solution**: The `finding_sources` junction table records every (finding_id, source_api) pair. This enables statistics like "how many findings were discovered by 3+ APIs" and helps assess API coverage.

### DOI-First Deduplication with Fuzzy Fallback

**Problem**: DOIs are the best dedup key, but not all papers have DOIs (especially patents, reports, and web results). Title matching catches these, but must handle minor formatting differences.

**Solution**: Two-stage approach:
1. First, check DOI (normalized to lowercase, URL prefixes stripped)
2. If no DOI match, use rapidfuzz with 90% similarity threshold on normalized titles

### Circuit Breaker Pattern

**Problem**: When an API goes down, continuing to send requests wastes time and may trigger rate limits.

**Solution**: Each API has a circuit breaker that tracks failures. After 5 consecutive failures, the breaker "opens" and rejects all calls for 60 seconds. After recovery timeout, it enters "half-open" state and allows 1 test call.

### Token Bucket Rate Limiting

**Problem**: Each API has different rate limits (0.5--50 qps). Exceeding them causes 429 errors and potential bans.

**Solution**: Per-API token bucket rate limiters configured in `config.py`. The async `acquire()` method blocks until a token is available, naturally throttling request rates.

### Reciprocal Rank Fusion for Result Merging

**Problem**: Different APIs return results in different orders with different relevance scoring. How to merge them fairly?

**Solution**: RRF assigns each paper a score of `sum(1/(k+rank))` across all APIs that returned it. Papers that appear near the top of multiple APIs get the highest scores. The constant k=60 prevents any single API from dominating.

### Enrichment Tiers for Cost Control

**Problem**: Claude AI enrichment costs money. Running deep analysis on every finding is expensive and wasteful.

**Solution**: 3-tier pipeline:
- Tier 1 (free): Rule-based keyword matching, processes all findings
- Tier 2 (cheap): Claude batch classification at ~$0.01/finding, processes thousands
- Tier 3 (expensive): Claude deep analysis at ~$0.05/finding, limited to high-value findings

### Known Applications as Novelty Baseline

**Problem**: Without a reference set, there is no way to distinguish "novel discovery" from "well-known product".

**Solution**: 152 known commercial soy products are seeded from `docs/soy-uses.md` into the `known_applications` table. Every finding is scored against this baseline. Findings with no match (score >= 70) are flagged as potentially novel.

---

## 18. Code Patterns and Conventions

### All source adapters follow the same protocol

```python
# src/soyscope/sources/base.py
class BaseSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def search(self, query, max_results=100,
                     year_start=None, year_end=None, **kwargs) -> SearchResult: ...

    async def get_by_doi(self, doi: str) -> Paper | None:
        return None  # Default: not supported

    def _make_paper(self, **kwargs) -> Paper:
        return Paper(source_api=self.name, **kwargs)
```

### Database uses context manager pattern

```python
# All DB operations use the connect() context manager
class Database:
    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
```

### Pydantic models for all data structures

Every data type has a Pydantic model in `models.py`. Key enums:

```python
class SourceType(str, Enum):
    PAPER = "paper"
    PATENT = "patent"
    NEWS = "news"
    REPORT = "report"
    TRADE_PUB = "trade_pub"
    CONFERENCE = "conference"
    GOVT_REPORT = "govt_report"

class EnrichmentTier(str, Enum):
    CATALOG = "catalog"
    SUMMARY = "summary"
    DEEP = "deep"

class CommercializationStatus(str, Enum):
    RESEARCH = "research"
    PILOT = "pilot"
    SCALING = "scaling"
    COMMERCIAL = "commercial"
    MATURE = "mature"
```

### Settings from environment with sensible defaults

```python
# src/soyscope/config.py
settings = get_settings()
settings.db_path          # Path("data/soyscope.db")
settings.cache_dir        # Path("cache")
settings.exports_dir      # Path("exports")
settings.logs_dir         # Path("logs")
settings.time_windows     # [(2000,2004), (2005,2009), (2010,2014), (2015,2019), (2020,2026)]
settings.apis["exa"]      # APIConfig(name="exa", api_key="...", rate_limit_qps=5.0, ...)
```

### Async everywhere for API calls

All API interactions are async. The CLI bridges sync-to-async with `asyncio.run()`:

```python
@app.command()
def build(resume: bool = False, ...):
    builder = HistoricalBuilder(orchestrator=orchestrator, db=db)
    result = asyncio.run(builder.build(resume=resume, ...))
```

---

## 19. Quick Reference Card

```
INITIALIZE:     soyscope init
FULL BUILD:     soyscope build [--resume] [--concurrency N] [--max-queries N]
REFRESH:        soyscope refresh [--since YYYY]
ENRICH:         soyscope enrich [--tier 1|2|3] [--limit N]
SEARCH:         soyscope search "query" [--sources x,y] [--store]
IMPORT USB:     soyscope import-deliverables --path file.csv
IMPORT CHECKOFF: soyscope import-checkoff [--path file.json]
RESOLVE OA:     soyscope resolve-oa [--limit N]
BACKFILL:       soyscope backfill-sources
STATS:          soyscope stats
EXPORT EXCEL:   soyscope export excel [--output file.xlsx]
EXPORT WORD:    soyscope export word [--output file.docx]
DASHBOARD:      soyscope dashboard
GUI:            soyscope gui
TESTS:          pytest tests/
```

---

## 20. Glossary

| Term               | Definition                                                             |
|--------------------|------------------------------------------------------------------------|
| **Finding**        | A single paper, patent, report, or article discovered by an API search |
| **Derivative**     | A soy-based material (e.g., Soy Oil, Soy Protein, Methyl Soyate)     |
| **Sector**         | An industry application area (e.g., Construction, Automotive)          |
| **Taxonomy**       | The 19x19 grid of derivatives and sectors                             |
| **Enrichment**     | AI-powered classification and analysis of a finding                    |
| **TRL**            | Technology Readiness Level (1=basic research, 9=proven commercial)     |
| **Novelty Score**  | 0=known product, 100=never-seen-before application                    |
| **Known App**      | A commercially available soy-based product in the reference inventory  |
| **RRF**            | Reciprocal Rank Fusion -- algorithm for merging multi-source results   |
| **OA**             | Open Access -- whether a paper's full text is freely available         |
| **USB**            | United Soybean Board -- the organization funding this project          |
| **SOY_SYNONYMS**   | ["soy", "soybean", "soy bean", "soya", "soja"]                       |
| **SECTOR_KEYWORDS**| Targeted search terms per sector (not sector names)                   |
| **Checkpoint**     | A saved query completion record for build resume                       |
| **Circuit Breaker**| Fault tolerance pattern that disables a failing API temporarily        |

---

## 19. External Reference Files (Outside This Repo)

These files are NOT in the repo but contain important context that Claude Code agents use:

| File | Location | Purpose |
|------|----------|---------|
| **Global CLAUDE.md** | `~/.claude/CLAUDE.md` | User's global instructions for ALL projects (key projects list, preferences) |
| **Project MEMORY.md** | `~/.claude/projects/C--EvalToolVersions/memory/MEMORY.md` | Persistent session memory for SoyScope — state, preferences, next priorities |
| **TODO Tracker** | `~/.claude/projects/C--Users-mbahar/memory/TODO-next-session.md` | Cross-session priority list |
| **PySide6 Skill** | `~/.claude/skills/pyside6-dashboard/SKILL.md` | GUI development reference for PySide6 dashboards |
| **Search API Skill** | `~/.claude/skills/search-api-reference/` | 4 reference files for academic search API integration |
| **USB PM Dashboard** | `~/.claude/projects/C--Users-mbahar/memory/usb-project-management.md` | Related project context |

### Key User Preferences (from MEMORY.md)
- Always deploy agent teams for parallel work
- Always show progress via task tracking
- Monitor background tasks — never fire-and-forget
- Ask one question at a time
- Always launch GUI/apps — don't just say "you can launch it"
- Be polite and friendly

### In-Repo Reference Documents
| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI agent instructions — **READ FIRST** when working on this project |
| `start-here.md` | This comprehensive onboarding document |
| `docs/soy-uses.md` | Ground-truth: 200+ known soy applications across 17 categories |
| `data/taxonomy.json` | 19 sectors × 19 derivatives with keywords and subtypes |
| `src/soyscope/known_apps_seed.py` | 152 commercial soy products for novelty baseline |
