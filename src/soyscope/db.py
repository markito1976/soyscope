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
    Paper,
    SearchQuery,
    SearchRun,
    Sector,
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
    finding_id INTEGER UNIQUE REFERENCES findings(id),
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

CREATE INDEX IF NOT EXISTS idx_findings_doi ON findings(doi);
CREATE INDEX IF NOT EXISTS idx_findings_year ON findings(year);
CREATE INDEX IF NOT EXISTS idx_findings_source_api ON findings(source_api);
CREATE INDEX IF NOT EXISTS idx_findings_title ON findings(title);
CREATE INDEX IF NOT EXISTS idx_enrichments_finding_id ON enrichments(finding_id);
CREATE INDEX IF NOT EXISTS idx_enrichments_novelty ON enrichments(novelty_score);
CREATE INDEX IF NOT EXISTS idx_search_queries_run_id ON search_queries(run_id);
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
                return cur.lastrowid
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

    # ── Enrichments ──

    def insert_enrichment(self, enrichment: Enrichment) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT OR REPLACE INTO enrichments
                   (finding_id, tier, trl_estimate, commercialization_status, novelty_score,
                    ai_summary, key_metrics, key_players, soy_advantage, barriers, model_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    enrichment.finding_id,
                    enrichment.tier.value if hasattr(enrichment.tier, "value") else enrichment.tier,
                    enrichment.trl_estimate,
                    enrichment.commercialization_status.value if enrichment.commercialization_status and hasattr(enrichment.commercialization_status, "value") else enrichment.commercialization_status,
                    enrichment.novelty_score,
                    enrichment.ai_summary,
                    json.dumps(enrichment.key_metrics),
                    json.dumps(enrichment.key_players),
                    enrichment.soy_advantage,
                    enrichment.barriers,
                    enrichment.model_used,
                ),
            )
            return cur.lastrowid

    def get_enrichment(self, finding_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM enrichments WHERE finding_id = ?", (finding_id,)).fetchone()
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
                       (year, title, category, keywords, lead_pi, institution, funding,
                        summary, objectives, url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
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

    def get_checkoff_count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]

    # ── Statistics ──

    def get_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            stats = {}
            stats["total_findings"] = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            stats["total_sectors"] = conn.execute("SELECT COUNT(*) FROM sectors").fetchone()[0]
            stats["total_derivatives"] = conn.execute("SELECT COUNT(*) FROM derivatives").fetchone()[0]
            stats["total_enriched"] = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
            stats["total_checkoff"] = conn.execute("SELECT COUNT(*) FROM checkoff_projects").fetchone()[0]
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

            return stats
