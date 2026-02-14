# Claude Code Handoff (Audit Fixes)

Last updated: `2026-02-14 17:43:05 -06:00`

## Repository + Branch Data

- Repository path: `C:\EvalToolVersions\soy-industrial-tracker`
- Remote: `origin = https://github.com/markito1976/soyscope.git`
- Active branch: `audit-fixes-2026-02-14`
- Branch base commit: `0151140` (`master` and `origin/master` are at the same commit)
- Branch creation (reflog): `2026-02-14 17:12:45 -06:00`, checked out from `master`
- Latest branch commit: `d5fa2c4` (`Add Claude handoff with branch metadata and validation results`)
- Branch commits in this session:
  - `640b963` (`Fix audit findings: enrichment tiers, refresh flow, source attribution`)
  - `d5fa2c4` (`Add Claude handoff with branch metadata and validation results`)

## Working Tree Snapshot

### Modified tracked files

- `src/soyscope/cli.py`
- `src/soyscope/collectors/historical_builder.py`
- `src/soyscope/collectors/query_generator.py`
- `src/soyscope/collectors/refresh_runner.py`
- `src/soyscope/config.py`
- `src/soyscope/db.py`
- `src/soyscope/enrichment/batch_enricher.py`
- `src/soyscope/gui/main_window.py`
- `src/soyscope/gui/views/run_history_tab.py`
- `src/soyscope/gui/workers/build_worker.py`
- `src/soyscope/orchestrator.py`
- `src/soyscope/sources/exa_source.py`

### New/untracked files intended as source/docs

- `src/soyscope/gui/workers/refresh_worker.py`
- `.claude/agents/system-auditor.md`
- `.claude/agents/context-effectiveness-auditor.md`

### New/untracked local artifacts (not source)

- `.tmp_cache/cache.db`
- `.tmp_cache_zip/cache.db`
- `.tmp_historical.db`
- `.tmp_multisource.db`
- `.tmp_refresh.db`
- `.tmp_validate_db.db`
- `.tmp_zipbug.db`

## Detailed Change Log (What + Why + Impact)

### 1) Enrichment schema correctness and migration

File: `src/soyscope/db.py`

- Changed `enrichments.finding_id` from globally `UNIQUE` to per-tier uniqueness via new unique index on `(finding_id, tier)`.
- Added schema migration function `_migrate_enrichments_schema(...)` that detects legacy DDL (`finding_id integer unique`) and rebuilds table safely.
- Updated `insert_enrichment(...)` from `INSERT OR REPLACE` to `INSERT ... ON CONFLICT(finding_id, tier) DO UPDATE`.
- Updated `get_enrichment(finding_id)` to return highest-value tier deterministically (`deep`, then `summary`, then `catalog`), newest first.

Why:
- Old model allowed only one enrichment row per finding, causing later writes to overwrite other tiers and lose data.

Impact:
- Tiered enrichment now preserves all stages per finding and query behavior aligns with intended 3-tier pipeline.

### 2) Known applications idempotency

File: `src/soyscope/db.py`

- Added `_known_application_exists(...)` semantic duplicate check.
- `insert_known_application(...)` and `seed_known_applications(...)` now skip equivalent rows instead of repeatedly inserting duplicates.

Why:
- Seeding should be repeatable and idempotent in build/init flows.

Impact:
- Stable known-app baseline, no silent growth from repeated seed runs.

### 3) Tier-1 novelty baseline alignment

File: `src/soyscope/enrichment/batch_enricher.py`

- Integrated `score_finding_novelty(...)` (`novelty.py`) with `SECTOR_KEYWORDS` from query generator.
- Tier 1 now prefers known-application baseline scoring; falls back to heuristic novelty scorer only when known baseline unavailable.
- Tier-3 candidate selection now aggregates max novelty from non-deep tiers and excludes already deep-enriched findings with `NOT EXISTS`.

Why:
- Project intent is novelty against known commercial applications, not just generic heuristic novelty.

Impact:
- Better ranking for true novelty and no duplicate deep-selection due to multi-tier rows.

### 4) Search source/result mapping and attribution fixes

File: `src/soyscope/orchestrator.py`

- Added stable paper key helper (`DOI` first, normalized title fallback).
- Fixed async result attribution bug by zipping search results with actual active targets, not raw requested targets.
- Switched RRF input from flattened single list to per-source ranked lists.
- Added robust multi-source writeback for both new and existing findings, including DOI backfill when duplicate insert path triggers.

Why:
- Prior logic could misattribute errors/sources and undercount multi-source provenance.

Impact:
- Accurate source-level attribution and better fused ranking behavior.

### 5) Error accounting and progress event parity

Files:
- `src/soyscope/collectors/historical_builder.py`
- `src/soyscope/collectors/refresh_runner.py`

- `HistoricalBuilder.execute_query(...)` now returns failure flag and increments `errors` when query-level failure occurs.
- `RefreshRunner.refresh(...)` gained `progress_callback` with `build_started`, `query_complete`, `source_error`, `build_complete` events.
- Refresh now also increments `errors` from result-level failure flag (not only thrown gather exceptions).

Why:
- Previous counters underreported failures, and refresh lacked GUI event parity with historical build.

Impact:
- More truthful run metrics and consistent telemetry shape for GUI consumers.

### 6) GUI refresh path correction

Files:
- `src/soyscope/gui/workers/refresh_worker.py` (new)
- `src/soyscope/gui/views/run_history_tab.py`

- Added dedicated `RefreshWorker` that executes real `RefreshRunner.refresh(...)`.
- Run History tab now launches refresh via `RefreshWorker` instead of reusing `HistoricalBuildWorker` with arbitrary max query cap.

Why:
- Refresh behavior should map to incremental refresh semantics, not truncated historical build behavior.

Impact:
- UI refresh action now follows intended backend pipeline and emits live progress events.

### 7) CORE source enablement parity

Files:
- `src/soyscope/cli.py`
- `src/soyscope/gui/workers/build_worker.py`

- CORE source initialization now depends only on `enabled`, not API key presence.

Why:
- Config comments and prior design intended CORE to run without key when allowed.

Impact:
- CLI and GUI behavior are consistent with intended CORE fallback mode.

### 8) Date/year correctness hardening

Files:
- `src/soyscope/config.py`
- `src/soyscope/collectors/query_generator.py`
- `src/soyscope/collectors/historical_builder.py`
- `src/soyscope/sources/exa_source.py`

- Replaced hardcoded `2026` boundaries with dynamic `_CURRENT_YEAR` in settings and query generation.
- Historical build now passes `settings.time_windows` into full plan generation.
- Exa end date corrected from `YYYY-01-01` to `YYYY-12-31`.

Why:
- Static year edges stale quickly; Exa end-date bug clipped nearly entire end year.

Impact:
- Time window coverage remains current, and Exa includes full end-year data.

### 9) GUI metadata cleanup

File: `src/soyscope/gui/main_window.py`

- About text updated from `8 search APIs` to `14 search APIs`.

Why:
- Prevent visible mismatch with current source set.

Impact:
- UI messaging now reflects actual capability.

### 10) Auditor agent definitions created

Files:
- `.claude/agents/system-auditor.md`
- `.claude/agents/context-effectiveness-auditor.md`

- Added two agent manifests with explicit scope, output format, and skill-file bindings:
  - system-wide audit (`python-testing-pytest` + subprocess-security support)
  - context-fitness audit (`python-performance-optimization`)

Why:
- Requested dual-auditor workflow with distinct concerns.

Impact:
- Reusable agent prompts/constraints now live in repo for repeated runs.

## Validation Run Summary

### Completed

- Syntax compile passed:
  - `python -m py_compile` for all modified/new source files.

### Test validation completed

- Targeted suites (escalated execution):
  - `python -m pytest tests/test_db.py tests/test_multi_source.py tests/test_checkpoints.py tests/test_known_applications.py -q`
  - Result: `80 passed`
- Additional targeted suites:
  - `python -m pytest tests/test_query_generator.py tests/test_enrichment.py tests/test_novelty.py -q`
  - Result: `78 passed`
- Full suite:
  - `python -m pytest -q`
  - Result: `243 passed`

### Earlier blocker (resolved)

- Initial in-sandbox pytest runs hit filesystem permission errors on temp/cache paths.
- Resolution: re-ran validation outside sandbox restrictions; all above suites passed.

## Current Open Items

- Keep temporary `.tmp_*` DB/cache artifacts uncommitted.
- Keep this handoff file refreshed at each session end with new commit hashes and validation updates.
- Working tree currently has only local temp artifacts (`.tmp_*`) untracked; no pending tracked source changes.

## Session-End Update Requirement (Non-Negotiable)

This file must be updated again at session end with:

1. Final `git status --short --branch`
2. Any additional file edits after this snapshot
3. Exact commit hash(es) if committed
4. Final validation command results
5. Remaining blockers for the next agent/user turn

### Session Update Log

- `2026-02-14 17:30:10 -06:00`:
  - Initial comprehensive handoff created with branch data and full change explanation.
- `2026-02-14 17:41:16 -06:00`:
  - Committed code and agent changes as `640b963`.
  - Re-ran targeted and full test suites outside sandbox restrictions: `243 passed` full run.
  - Updated handoff with final validation and commit metadata.
- `2026-02-14 17:43:05 -06:00`:
  - Committed this handoff file as `d5fa2c4`.
  - Confirmed branch head and left only temporary local artifacts untracked.
