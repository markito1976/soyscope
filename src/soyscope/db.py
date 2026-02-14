"""SQLite schema creation and CRUD operations."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from .models import (
    CheckoffProject,
    Derivative,
    Enrichment,
    Finding,
    KnownApplication,
    Paper,
    SearchQuery,
    SearchRun,
    Sector,
    USBDeliverable,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    abstract TEXT,
    year INTEGER,
    doi TEXT UNIQUE,
    url TEXT,
    pdf_url TEXT,
    authors TEXT,
    venue TEXT,
    source_api TEXT,
    source_type TEXT,
    citation_count INTEGER,
    open_access_status TEXT,
    raw_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES sectors(id),
    description TEXT,
    is_ai_discovered BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS derivatives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES derivatives(id),
    description TEXT,
    is_ai_discovered BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS finding_sectors (
    finding_id INTEGER REFERENCES findings(id),
    sector_id INTEGER REFERENCES sectors(id),
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (finding_id, sector_id)
);

CREATE TABLE IF NOT EXISTS finding_derivatives (
    finding_id INTEGER REFERENCES findings(id),
    derivative_id INTEGER REFERENCES derivatives(id),
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (finding_id, derivative_id)
);

CREATE TABLE IF NOT EXISTS enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings(id),
    tier TEXT NOT NULL,
    trl_estimate INTEGER,
    commercialization_status TEXT,
    novelty_score REAL,
    ai_summary TEXT,
    key_metrics TEXT,
    key_players TEXT,
    soy_advantage TEXT,
    barriers TEXT,
    enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS finding_tags (
    finding_id INTEGER REFERENCES findings(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (finding_id, tag_id)
);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    queries_executed INTEGER,
    findings_added INTEGER,
    findings_updated INTEGER,
    api_costs_json TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES search_runs(id),
    query_text TEXT,
    api_source TEXT,
    results_returned INTEGER,
    new_findings INTEGER,
    executed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkoff_projects (
    id INTEGER PRIMARY KEY,
    year TEXT,
    title TEXT,
    category TEXT,
    keywords TEXT,
    lead_pi TEXT,
    institution TEXT,
    funding REAL,
    summary TEXT,
    objectives TEXT,
    url TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usb_deliverables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    doi_link TEXT,
    deliverable_type TEXT,
    submitted_year INTEGER,
    published_year INTEGER,
    month TEXT,
    journal_name TEXT,
    authors TEXT,
    combined_authors TEXT,
    funders TEXT,
    usb_project_number TEXT,
    investment_category TEXT,
    key_categories TEXT,
    keywords TEXT,
    pi_name TEXT,
    pi_email TEXT,
    organization TEXT,
    priority_area TEXT,
    raw_csv_row TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(title, doi_link)
);

CREATE INDEX IF NOT EXISTS idx_usb_deliverables_title ON usb_deliverables(title);
CREATE INDEX IF NOT EXISTS idx_usb_deliverables_doi ON usb_deliverables(doi_link);

CREATE TABLE IF NOT EXISTS finding_sources (
    finding_id INTEGER REFERENCES findings(id),
    source_api TEXT NOT NULL,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (finding_id, source_api)
);

CREATE INDEX IF NOT EXISTS idx_finding_sources_finding ON finding_sources(finding_id);
CREATE INDEX IF NOT EXISTS idx_finding_sources_source ON finding_sources(source_api);

CREATE TABLE IF NOT EXISTS search_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES search_runs(id),
    query_hash TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_type TEXT,
    derivative TEXT,
    sector TEXT,
    year_start INTEGER,
    year_end INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    new_findings INTEGER DEFAULT 0,
    updated_findings INTEGER DEFAULT 0,
    completed_at TIMESTAMP,
    UNIQUE(run_id, query_hash)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_run ON search_checkpoints(run_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON search_checkpoints(run_id, status);

CREATE INDEX IF NOT EXISTS idx_findings_doi ON findings(doi);
CREATE INDEX IF NOT EXISTS idx_findings_year ON findings(year);
CREATE INDEX IF NOT EXISTS idx_findings_source_api ON findings(source_api);
CREATE INDEX IF NOT EXISTS idx_findings_title ON findings(title);
CREATE INDEX IF NOT EXISTS idx_enrichments_finding_id ON enrichments(finding_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enrichments_finding_tier ON enrichments(finding_id, tier);
CREATE INDEX IF NOT EXISTS idx_enrichments_novelty ON enrichments(novelty_score);
CREATE INDEX IF NOT EXISTS idx_search_queries_run_id ON search_queries(run_id);

CREATE TABLE IF NOT EXISTS known_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    manufacturer TEXT,
    sector TEXT NOT NULL,
    derivative TEXT,
    category TEXT NOT NULL,
    market_size TEXT,
    description TEXT,
    year_introduced INTEGER,
    is_commercialized BOOLEAN DEFAULT 1,
    source_doc TEXT DEFAULT 'soy-uses.md'
);

CREATE INDEX IF NOT EXISTS idx_known_apps_sector ON known_applications(sector);
CREATE INDEX IF NOT EXISTS idx_known_apps_derivative ON known_applications(derivative);
CREATE INDEX IF NOT EXISTS idx_known_apps_product ON known_applications(product_name);
"""


class Database:
    """SQLite database manager for SoyScope."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

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

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_enrichments_schema(conn)

    def _migrate_enrichments_schema(self, conn: sqlite3.Connection) -> None:
        """Migrate enrichments from old per-finding uniqueness to per-tier uniqueness."""
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'enrichments'"
        ).fetchone()
        if not row or not row[0]:
            return

        table_sql = str(row[0]).lower()
        if "finding_id integer unique" not in table_sql:
            return

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS enrichments_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id INTEGER REFERENCES findings(id),
                tier TEXT NOT NULL,
                trl_estimate INTEGER,
                commercialization_status TEXT,
                novelty_score REAL,
                ai_summary TEXT,
                key_metrics TEXT,
                key_players TEXT,
                soy_advantage TEXT,
                barriers TEXT,
                enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model_used TEXT
            );

            INSERT INTO enrichments_new
                (id, finding_id, tier, trl_estimate, commercialization_status, novelty_score,
                 ai_summary, key_metrics, key_players, soy_advantage, barriers, enriched_at, model_used)
            SELECT
                id, finding_id, tier, trl_estimate, commercialization_status, novelty_score,
                ai_summary, key_metrics, key_players, soy_advantage, barriers, enriched_at, model_used
            FROM enrichments;

            DROP TABLE enrichments;
            ALTER TABLE enrichments_new RENAME TO enrichments;

            CREATE INDEX IF NOT EXISTS idx_enrichments_finding_id ON enrichments(finding_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_enrichments_finding_tier ON enrichments(finding_id, tier);
            CREATE INDEX IF NOT EXISTS idx_enrichments_novelty ON enrichments(novelty_score);
            """
        )

    # ── Findings CRUD ──

    def insert_finding(self, paper: Paper) -> int | None:
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """INSERT INTO findings
                       (title, abstract, year, doi, url, pdf_url, authors, venue,
                        source_api, source_type, citation_count, open_access_status, raw_metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        paper.title,
                        paper.abstract,
                        paper.year,
                        paper.doi,
                        paper.url,
                        paper.pdf_url,
                        paper.authors_json,
                        paper.venue,
                        paper.source_api,
                        paper.source_type.value if hasattr(paper.source_type, "value") else paper.source_type,
                        paper.citation_count,
                        paper.open_access_status.value if paper.open_access_status and hasattr(paper.open_access_status, "value") else paper.open_access_status,
                        paper.raw_metadata_json,
                    ),
                )
                finding_id = cur.lastrowid
                if finding_id and paper.source_api:
                    conn.execute(
                        "INSERT OR IGNORE INTO finding_sources (finding_id, source_api) VALUES (?, ?)",
                        (finding_id, paper.source_api),
                    )
                return finding_id
            except sqlite3.IntegrityError:
                # Duplicate DOI - update instead
                if paper.doi:
                    conn.execute(
                        """UPDATE findings SET citation_count = ?, updated_at = CURRENT_TIMESTAMP
                           WHERE doi = ?""",
                        (paper.citation_count, paper.doi),
                    )
                return None

    def get_finding_by_doi(self, doi: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM findings WHERE doi = ?", (doi,)).fetchone()
            return dict(row) if row else None

    def get_finding_by_id(self, finding_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
            return dict(row) if row else None

    def get_all_findings(self, limit: int = 0, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as conn:
            q = "SELECT * FROM findings ORDER BY year DESC, id DESC"
            if limit > 0:
                q += f" LIMIT {limit} OFFSET {offset}"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def get_unenriched_findings(self, tier: str = "summary", limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """SELECT f.* FROM findings f
                       LEFT JOIN enrichments e ON f.id = e.finding_id AND e.tier = ?
                       WHERE e.id IS NULL
                       ORDER BY f.id
                       LIMIT ?""",
                    (tier, limit),
                ).fetchall()
            ]

    def get_findings_count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]

    def search_findings(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """SELECT * FROM findings
                       WHERE title LIKE ? OR abstract LIKE ?
                       ORDER BY year DESC
                       LIMIT ?""",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            ]

    def get_existing_dois(self) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT doi FROM findings WHERE doi IS NOT NULL").fetchall()
            return {r[0] for r in rows}

    def get_existing_titles(self) -> list[tuple[int, str]]:
        with self.connect() as conn:
            return [
                (r[0], r[1])
                for r in conn.execute("SELECT id, title FROM findings").fetchall()
            ]

    # ── Sectors CRUD ──

    def insert_sector(self, name: str, parent_id: int | None = None,
                      description: str | None = None, is_ai_discovered: bool = False) -> int:
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO sectors (name, parent_id, description, is_ai_discovered) VALUES (?, ?, ?, ?)",
                    (name, parent_id, description, int(is_ai_discovered)),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT id FROM sectors WHERE name = ?", (name,)).fetchone()
                return row[0]

    def get_all_sectors(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM sectors ORDER BY name").fetchall()]

    def get_sector_by_name(self, name: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sectors WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    # ── Derivatives CRUD ──

    def insert_derivative(self, name: str, parent_id: int | None = None,
                          description: str | None = None, is_ai_discovered: bool = False) -> int:
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO derivatives (name, parent_id, description, is_ai_discovered) VALUES (?, ?, ?, ?)",
                    (name, parent_id, description, int(is_ai_discovered)),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT id FROM derivatives WHERE name = ?", (name,)).fetchone()
                return row[0]

    def get_all_derivatives(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM derivatives ORDER BY name").fetchall()]

    def get_derivative_by_name(self, name: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM derivatives WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    # ── Junction tables ──

    def link_finding_sector(self, finding_id: int, sector_id: int, confidence: float = 1.0) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO finding_sectors (finding_id, sector_id, confidence) VALUES (?, ?, ?)",
                (finding_id, sector_id, confidence),
            )

    def link_finding_derivative(self, finding_id: int, derivative_id: int, confidence: float = 1.0) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO finding_derivatives (finding_id, derivative_id, confidence) VALUES (?, ?, ?)",
                (finding_id, derivative_id, confidence),
            )

    def get_finding_sectors(self, finding_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """SELECT s.*, fs.confidence FROM sectors s
                       JOIN finding_sectors fs ON s.id = fs.sector_id
                       WHERE fs.finding_id = ?""",
                    (finding_id,),
                ).fetchall()
            ]

    def get_finding_derivatives(self, finding_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    """SELECT d.*, fd.confidence FROM derivatives d
                       JOIN finding_derivatives fd ON d.id = fd.derivative_id
                       WHERE fd.finding_id = ?""",
                    (finding_id,),
                ).fetchall()
            ]

    # ── Tags ──

    def insert_tag(self, name: str) -> int:
        with self.connect() as conn:
            try:
                cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
                return cur.lastrowid
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
                return row[0]

    def link_finding_tag(self, finding_id: int, tag_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO finding_tags (finding_id, tag_id) VALUES (?, ?)",
                (finding_id, tag_id),
            )

    # ── Finding Sources (multi-source tracking) ──

    def add_finding_source(self, finding_id: int, source_api: str) -> None:
        """Record that a finding was discovered in a particular API source."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO finding_sources (finding_id, source_api) VALUES (?, ?)",
                (finding_id, source_api),
            )

    def get_finding_sources(self, finding_id: int) -> list[str]:
        """Return all source_api values for a finding."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_api FROM finding_sources WHERE finding_id = ? ORDER BY discovered_at",
                (finding_id,),
            ).fetchall()
            return [r[0] for r in rows]

    def get_all_finding_sources_map(self) -> dict[int, list[str]]:
        """Return a mapping of finding_id -> [source_api, ...] for all findings."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT finding_id, source_api FROM finding_sources ORDER BY finding_id, discovered_at"
            ).fetchall()

        result: dict[int, list[str]] = {}
        for fid, src in rows:
            result.setdefault(fid, []).append(src)
        return result

    def get_doi_to_id_map(self) -> dict[str, int]:
        """Return a mapping of DOI -> finding_id for all findings with DOIs."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT doi, id FROM findings WHERE doi IS NOT NULL"
            ).fetchall()
            return {r[0]: r[1] for r in rows}

    def backfill_finding_sources(self) -> int:
        """Seed finding_sources from existing findings.source_api column.

        Returns the number of rows inserted.
        """
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO finding_sources (finding_id, source_api)
                   SELECT id, source_api FROM findings
                   WHERE source_api IS NOT NULL AND source_api != ''"""
            )
            return cur.rowcount

    # ── Enrichments ──

    def insert_enrichment(self, enrichment: Enrichment) -> int:
        tier_value = enrichment.tier.value if hasattr(enrichment.tier, "value") else enrichment.tier
        status_value = (
            enrichment.commercialization_status.value
            if enrichment.commercialization_status and hasattr(enrichment.commercialization_status, "value")
            else enrichment.commercialization_status
        )
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO enrichments
                   (finding_id, tier, trl_estimate, commercialization_status, novelty_score,
                    ai_summary, key_metrics, key_players, soy_advantage, barriers, model_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(finding_id, tier) DO UPDATE SET
                       trl_estimate = excluded.trl_estimate,
                       commercialization_status = excluded.commercialization_status,
                       novelty_score = excluded.novelty_score,
                       ai_summary = excluded.ai_summary,
                       key_metrics = excluded.key_metrics,
                       key_players = excluded.key_players,
                       soy_advantage = excluded.soy_advantage,
                       barriers = excluded.barriers,
                       model_used = excluded.model_used,
                       enriched_at = CURRENT_TIMESTAMP""",
                (
                    enrichment.finding_id,
                    tier_value,
                    enrichment.trl_estimate,
                    status_value,
                    enrichment.novelty_score,
                    enrichment.ai_summary,
                    json.dumps(enrichment.key_metrics),
                    json.dumps(enrichment.key_players),
                    enrichment.soy_advantage,
                    enrichment.barriers,
                    enrichment.model_used,
                ),
            )
            row = conn.execute(
                "SELECT id FROM enrichments WHERE finding_id = ? AND tier = ?",
                (enrichment.finding_id, tier_value),
            ).fetchone()
            return row[0] if row else 0

    def get_enrichment(self, finding_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT * FROM enrichments
                   WHERE finding_id = ?
                   ORDER BY
                       CASE tier
                           WHEN 'deep' THEN 3
                           WHEN 'summary' THEN 2
                           WHEN 'catalog' THEN 1
                           ELSE 0
                       END DESC,
                       enriched_at DESC,
                       id DESC
                   LIMIT 1""",
                (finding_id,),
            ).fetchone()
            return dict(row) if row else None

    # ── Search Runs ──

    def start_search_run(self, run_type: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO search_runs (run_type, started_at, status) VALUES (?, ?, 'running')",
                (run_type, datetime.now().isoformat()),
            )
            return cur.lastrowid

    def complete_search_run(self, run_id: int, queries_executed: int,
                            findings_added: int, findings_updated: int,
                            api_costs: dict[str, float] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE search_runs
                   SET completed_at = ?, queries_executed = ?, findings_added = ?,
                       findings_updated = ?, api_costs_json = ?, status = 'completed'
                   WHERE id = ?""",
                (
                    datetime.now().isoformat(),
                    queries_executed,
                    findings_added,
                    findings_updated,
                    json.dumps(api_costs or {}),
                    run_id,
                ),
            )

    def fail_search_run(self, run_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE search_runs SET completed_at = ?, status = 'failed' WHERE id = ?",
                (datetime.now().isoformat(), run_id),
            )

    def get_last_search_run(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM search_runs WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def log_search_query(self, run_id: int, query_text: str, api_source: str,
                         results_returned: int, new_findings: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO search_queries
                   (run_id, query_text, api_source, results_returned, new_findings, executed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, query_text, api_source, results_returned, new_findings, datetime.now().isoformat()),
            )

    # ── Checkoff Projects ──

    def insert_checkoff_project(self, project: CheckoffProject) -> int | None:
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """INSERT INTO checkoff_projects
                       (id, year, title, category, keywords, lead_pi, institution, funding,
                        summary, objectives, url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        project.id,
                        project.year,
                        project.title,
                        project.category,
                        json.dumps(project.keywords),
                        project.lead_pi,
                        project.institution,
                        project.funding,
                        project.summary,
                        project.objectives,
                        project.url,
                    ),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None

    def insert_checkoff_projects_batch(self, projects: list[CheckoffProject]) -> tuple[int, int]:
        """Insert multiple checkoff projects in a single transaction.

        Uses INSERT OR IGNORE with executemany for maximum throughput.
        Returns (inserted, skipped) tuple.
        """
        if not projects:
            return (0, 0)

        rows = [
            (
                p.id,
                p.year,
                p.title,
                p.category,
                json.dumps(p.keywords),
                p.lead_pi,
                p.institution,
                p.funding,
                p.summary,
                p.objectives,
                p.url,
            )
            for p in projects
        ]

        with self.connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]
            conn.executemany(
                """INSERT OR IGNORE INTO checkoff_projects
                   (id, year, title, category, keywords, lead_pi, institution, funding,
                    summary, objectives, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            after = conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]
            inserted = after - before
        skipped = len(projects) - inserted
        return (inserted, skipped)

    def insert_findings_batch(self, papers: list[Paper]) -> tuple[int, int]:
        """Insert multiple findings in a single transaction.

        Uses executemany for the main insert, then handles finding_sources
        tracking in a second pass. Checkoff papers typically have no DOIs,
        so duplicates are rare; any DOI-based duplicates are silently skipped.

        Returns (inserted, skipped) tuple.
        """
        if not papers:
            return (0, 0)

        rows = [
            (
                paper.title,
                paper.abstract,
                paper.year,
                paper.doi,
                paper.url,
                paper.pdf_url,
                paper.authors_json,
                paper.venue,
                paper.source_api,
                paper.source_type.value if hasattr(paper.source_type, "value") else paper.source_type,
                paper.citation_count,
                paper.open_access_status.value if paper.open_access_status and hasattr(paper.open_access_status, "value") else paper.open_access_status,
                paper.raw_metadata_json,
            )
            for paper in papers
        ]

        with self.connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            conn.executemany(
                """INSERT OR IGNORE INTO findings
                   (title, abstract, year, doi, url, pdf_url, authors, venue,
                    source_api, source_type, citation_count, open_access_status, raw_metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            after = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            inserted = after - before

            # Batch-insert finding_sources for all newly-inserted findings
            source_apis = {p.source_api for p in papers if p.source_api}
            for source_api in source_apis:
                conn.execute(
                    """INSERT OR IGNORE INTO finding_sources (finding_id, source_api)
                       SELECT id, source_api FROM findings
                       WHERE source_api = ? AND id > ?""",
                    (source_api, before),
                )

        skipped = len(papers) - inserted
        return (inserted, skipped)

    def get_checkoff_count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]

    # ── USB Deliverables ──

    def insert_usb_deliverable(self, deliverable: USBDeliverable) -> int | None:
        with self.connect() as conn:
            try:
                cur = conn.execute(
                    """INSERT INTO usb_deliverables
                       (title, doi_link, deliverable_type, submitted_year, published_year,
                        month, journal_name, authors, combined_authors, funders,
                        usb_project_number, investment_category, key_categories, keywords,
                        pi_name, pi_email, organization, priority_area, raw_csv_row)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        deliverable.title,
                        deliverable.doi_link,
                        deliverable.deliverable_type,
                        deliverable.submitted_year,
                        deliverable.published_year,
                        deliverable.month,
                        deliverable.journal_name,
                        deliverable.authors,
                        deliverable.combined_authors,
                        deliverable.funders,
                        deliverable.usb_project_number,
                        deliverable.investment_category,
                        deliverable.key_categories,
                        json.dumps(deliverable.keywords),
                        deliverable.pi_name,
                        deliverable.pi_email,
                        deliverable.organization,
                        deliverable.priority_area,
                        json.dumps(deliverable.raw_csv_row),
                    ),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return None

    def get_usb_deliverables_count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM usb_deliverables").fetchone()[0]

    def update_finding_oa(self, finding_id: int, pdf_url: str | None, open_access_status: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE findings SET pdf_url = ?, open_access_status = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (pdf_url, open_access_status, finding_id),
            )

    # ── Statistics ──

    def get_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            stats = {}
            stats["total_findings"] = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            stats["total_sectors"] = conn.execute("SELECT COUNT(*) FROM sectors").fetchone()[0]
            stats["total_derivatives"] = conn.execute("SELECT COUNT(*) FROM derivatives").fetchone()[0]
            stats["total_enriched"] = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
            stats["total_checkoff"] = conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]
            stats["total_usb_deliverables"] = conn.execute("SELECT COUNT(*) FROM usb_deliverables").fetchone()[0]
            stats["total_tags"] = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
            stats["total_runs"] = conn.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]

            # By source API
            rows = conn.execute(
                "SELECT source_api, COUNT(*) as cnt FROM findings GROUP BY source_api ORDER BY cnt DESC"
            ).fetchall()
            stats["by_source"] = {r[0]: r[1] for r in rows}

            # By year
            rows = conn.execute(
                "SELECT year, COUNT(*) as cnt FROM findings WHERE year IS NOT NULL GROUP BY year ORDER BY year"
            ).fetchall()
            stats["by_year"] = {r[0]: r[1] for r in rows}

            # By source type
            rows = conn.execute(
                "SELECT source_type, COUNT(*) as cnt FROM findings GROUP BY source_type ORDER BY cnt DESC"
            ).fetchall()
            stats["by_type"] = {r[0]: r[1] for r in rows}

            # Enrichment coverage
            stats["enrichment_catalog"] = conn.execute(
                "SELECT COUNT(*) FROM enrichments WHERE tier = 'catalog'"
            ).fetchone()[0]
            stats["enrichment_summary"] = conn.execute(
                "SELECT COUNT(*) FROM enrichments WHERE tier = 'summary'"
            ).fetchone()[0]
            stats["enrichment_deep"] = conn.execute(
                "SELECT COUNT(*) FROM enrichments WHERE tier = 'deep'"
            ).fetchone()[0]

            # Sector matrix
            rows = conn.execute(
                """SELECT s.name as sector, d.name as derivative, COUNT(*) as cnt
                   FROM finding_sectors fs
                   JOIN sectors s ON fs.sector_id = s.id
                   JOIN finding_derivatives fd ON fs.finding_id = fd.finding_id
                   JOIN derivatives d ON fd.derivative_id = d.id
                   GROUP BY s.name, d.name
                   ORDER BY cnt DESC"""
            ).fetchall()
            stats["sector_derivative_matrix"] = [
                {"sector": r[0], "derivative": r[1], "count": r[2]} for r in rows
            ]

            # Multi-source tracking stats
            try:
                stats["findings_with_multiple_sources"] = conn.execute(
                    """SELECT COUNT(*) FROM (
                        SELECT finding_id FROM finding_sources
                        GROUP BY finding_id HAVING COUNT(*) > 1
                    )"""
                ).fetchone()[0]

                rows = conn.execute(
                    """SELECT source_api, COUNT(*) as cnt
                       FROM finding_sources GROUP BY source_api ORDER BY cnt DESC"""
                ).fetchall()
                stats["by_source_tracked"] = {r[0]: r[1] for r in rows}

                stats["avg_sources_per_finding"] = conn.execute(
                    """SELECT AVG(cnt) FROM (
                        SELECT COUNT(*) as cnt FROM finding_sources GROUP BY finding_id
                    )"""
                ).fetchone()[0] or 0.0
            except Exception:
                stats["findings_with_multiple_sources"] = 0
                stats["by_source_tracked"] = {}
                stats["avg_sources_per_finding"] = 0.0

            return stats

    # ── Search Checkpoints (resume-safe ingestion) ──

    def insert_checkpoint_batch(self, run_id: int,
                                checkpoints: list[dict[str, Any]]) -> int:
        """Insert a batch of checkpoint records for a query plan.

        Each dict must have: query_hash, query_text.
        Optional: query_type, derivative, sector, year_start, year_end.
        Returns number inserted (skips existing via UNIQUE constraint).
        """
        inserted = 0
        with self.connect() as conn:
            for cp in checkpoints:
                try:
                    conn.execute(
                        """INSERT INTO search_checkpoints
                           (run_id, query_hash, query_text, query_type,
                            derivative, sector, year_start, year_end, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                        (
                            run_id,
                            cp["query_hash"],
                            cp["query_text"],
                            cp.get("query_type"),
                            cp.get("derivative"),
                            cp.get("sector"),
                            cp.get("year_start"),
                            cp.get("year_end"),
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass  # already exists
        return inserted

    def get_pending_checkpoints(self, run_id: int) -> list[dict[str, Any]]:
        """Return all checkpoints that haven't completed yet for a run."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM search_checkpoints
                   WHERE run_id = ? AND status = 'pending'
                   ORDER BY id""",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def complete_checkpoint(self, checkpoint_id: int,
                            new_findings: int = 0,
                            updated_findings: int = 0) -> None:
        """Mark a checkpoint as completed."""
        with self.connect() as conn:
            conn.execute(
                """UPDATE search_checkpoints
                   SET status = 'completed', new_findings = ?,
                       updated_findings = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_findings, updated_findings, checkpoint_id),
            )

    def fail_checkpoint(self, checkpoint_id: int) -> None:
        """Mark a checkpoint as failed (will be retried on resume)."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE search_checkpoints SET status = 'failed' WHERE id = ?",
                (checkpoint_id,),
            )

    def reset_failed_checkpoints(self, run_id: int) -> int:
        """Reset failed checkpoints back to pending for retry."""
        with self.connect() as conn:
            cur = conn.execute(
                """UPDATE search_checkpoints SET status = 'pending'
                   WHERE run_id = ? AND status = 'failed'""",
                (run_id,),
            )
            return cur.rowcount

    def get_checkpoint_progress(self, run_id: int) -> dict[str, int]:
        """Return checkpoint progress summary for a run."""
        with self.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM search_checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM search_checkpoints WHERE run_id = ? AND status = 'completed'",
                (run_id,),
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM search_checkpoints WHERE run_id = ? AND status = 'failed'",
                (run_id,),
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM search_checkpoints WHERE run_id = ? AND status = 'pending'",
                (run_id,),
            ).fetchone()[0]
            new_total = conn.execute(
                "SELECT COALESCE(SUM(new_findings), 0) FROM search_checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            updated_total = conn.execute(
                "SELECT COALESCE(SUM(updated_findings), 0) FROM search_checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "new_findings": new_total,
                "updated_findings": updated_total,
            }

    def get_last_incomplete_run(self, run_type: str) -> dict[str, Any] | None:
        """Find the most recent run of a given type that wasn't completed."""
        with self.connect() as conn:
            row = conn.execute(
                """SELECT * FROM search_runs
                   WHERE run_type = ? AND status IN ('running', 'interrupted')
                   ORDER BY started_at DESC LIMIT 1""",
                (run_type,),
            ).fetchone()
            return dict(row) if row else None

    def interrupt_search_run(self, run_id: int) -> None:
        """Mark a search run as interrupted (resumable)."""
        with self.connect() as conn:
            conn.execute(
                """UPDATE search_runs SET status = 'interrupted',
                   completed_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (run_id,),
            )

    # ── Known Applications ──

    def insert_known_application(self, app: KnownApplication) -> int:
        """Insert a known application entry."""
        with self.connect() as conn:
            if self._known_application_exists(conn, app):
                return -1
            try:
                cur = conn.execute(
                    """INSERT INTO known_applications
                       (product_name, manufacturer, sector, derivative, category,
                        market_size, description, year_introduced, is_commercialized, source_doc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        app.product_name,
                        app.manufacturer,
                        app.sector,
                        app.derivative,
                        app.category,
                        app.market_size,
                        app.description,
                        app.year_introduced,
                        int(app.is_commercialized),
                        app.source_doc,
                    ),
                )
                return cur.lastrowid
            except sqlite3.IntegrityError:
                return -1

    def get_all_known_applications(self) -> list[dict[str, Any]]:
        """Return all known application entries."""
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM known_applications ORDER BY sector, category"
            ).fetchall()]

    def get_known_applications_by_sector(self, sector: str) -> list[dict[str, Any]]:
        """Return known applications for a given sector."""
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM known_applications WHERE sector = ? ORDER BY category",
                (sector,),
            ).fetchall()]

    def get_known_applications_count(self) -> int:
        """Return total count of known applications."""
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM known_applications").fetchone()[0]

    @staticmethod
    def _known_application_exists(conn: sqlite3.Connection, app: KnownApplication) -> bool:
        """Return True if an equivalent known application row already exists."""
        row = conn.execute(
            """SELECT 1 FROM known_applications
               WHERE COALESCE(product_name, '') = COALESCE(?, '')
                 AND COALESCE(manufacturer, '') = COALESCE(?, '')
                 AND sector = ?
                 AND COALESCE(derivative, '') = COALESCE(?, '')
                 AND category = ?
                 AND COALESCE(description, '') = COALESCE(?, '')
               LIMIT 1""",
            (
                app.product_name,
                app.manufacturer,
                app.sector,
                app.derivative,
                app.category,
                app.description,
            ),
        ).fetchone()
        return row is not None

    def seed_known_applications(self, apps: list[KnownApplication]) -> int:
        """Seed known applications table from a list, skipping existing entries.

        Returns number inserted.
        """
        inserted = 0
        with self.connect() as conn:
            for app in apps:
                if self._known_application_exists(conn, app):
                    continue
                try:
                    conn.execute(
                        """INSERT INTO known_applications
                           (product_name, manufacturer, sector, derivative, category,
                            market_size, description, year_introduced, is_commercialized, source_doc)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            app.product_name,
                            app.manufacturer,
                            app.sector,
                            app.derivative,
                            app.category,
                            app.market_size,
                            app.description,
                            app.year_introduced,
                            int(app.is_commercialized),
                            app.source_doc,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
        return inserted
