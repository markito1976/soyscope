"""Tests for the checkpoint/resume system.

Covers all checkpoint-related Database methods used by the historical builder:
insert_checkpoint_batch, get_pending_checkpoints, complete_checkpoint,
fail_checkpoint, reset_failed_checkpoints, get_checkpoint_progress,
get_last_incomplete_run, interrupt_search_run, and the full resume flow.
"""

from __future__ import annotations

import hashlib

import pytest

from soyscope.db import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Create a temporary database with schema initialised."""
    database = Database(tmp_path / "test_checkpoints.db")
    database.init_schema()
    return database


@pytest.fixture
def run_id(db: Database) -> int:
    """Create a search run and return its id."""
    return db.start_search_run("historical_build")


def _make_checkpoints(n: int = 5) -> list[dict]:
    """Helper: generate *n* checkpoint dicts with unique hashes."""
    return [
        {
            "query_hash": hashlib.sha256(f"query_{i}".encode()).hexdigest()[:16],
            "query_text": f"soy industrial use {i}",
            "query_type": "derivative_sector",
            "derivative": "Soy Oil" if i % 2 == 0 else "Soy Protein",
            "sector": "Adhesives" if i % 2 == 0 else "Coatings",
            "year_start": 2000 + i,
            "year_end": 2005 + i,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInsertCheckpointBatch:
    """insert_checkpoint_batch: seed a batch, verify they exist as pending."""

    def test_insert_batch_returns_count(self, db: Database, run_id: int):
        cps = _make_checkpoints(5)
        inserted = db.insert_checkpoint_batch(run_id, cps)
        assert inserted == 5

    def test_all_inserted_as_pending(self, db: Database, run_id: int):
        cps = _make_checkpoints(3)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        assert len(pending) == 3
        for row in pending:
            assert row["status"] == "pending"
            assert row["run_id"] == run_id
            assert row["new_findings"] == 0
            assert row["updated_findings"] == 0
            assert row["completed_at"] is None

    def test_duplicate_query_hash_skipped(self, db: Database, run_id: int):
        cps = _make_checkpoints(3)
        first = db.insert_checkpoint_batch(run_id, cps)
        second = db.insert_checkpoint_batch(run_id, cps)
        assert first == 3
        assert second == 0
        pending = db.get_pending_checkpoints(run_id)
        assert len(pending) == 3

    def test_optional_fields_stored(self, db: Database, run_id: int):
        cps = _make_checkpoints(1)
        db.insert_checkpoint_batch(run_id, cps)
        rows = db.get_pending_checkpoints(run_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["query_text"] == "soy industrial use 0"
        assert row["query_type"] == "derivative_sector"
        assert row["derivative"] == "Soy Oil"
        assert row["sector"] == "Adhesives"
        assert row["year_start"] == 2000
        assert row["year_end"] == 2005

    def test_minimal_checkpoint_no_optional_fields(self, db: Database, run_id: int):
        """Only the required fields (query_hash, query_text) are supplied."""
        minimal = [{"query_hash": "abc123", "query_text": "soy test"}]
        inserted = db.insert_checkpoint_batch(run_id, minimal)
        assert inserted == 1
        rows = db.get_pending_checkpoints(run_id)
        assert rows[0]["query_type"] is None
        assert rows[0]["derivative"] is None
        assert rows[0]["sector"] is None
        assert rows[0]["year_start"] is None
        assert rows[0]["year_end"] is None

    def test_empty_batch_inserts_nothing(self, db: Database, run_id: int):
        inserted = db.insert_checkpoint_batch(run_id, [])
        assert inserted == 0


class TestGetPendingCheckpoints:
    """get_pending_checkpoints: only returns checkpoints with status=pending."""

    def test_returns_only_pending(self, db: Database, run_id: int):
        cps = _make_checkpoints(5)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        db.complete_checkpoint(pending[0]["id"], new_findings=3, updated_findings=1)
        db.complete_checkpoint(pending[1]["id"], new_findings=0, updated_findings=0)
        remaining = db.get_pending_checkpoints(run_id)
        assert len(remaining) == 3
        completed_ids = {pending[0]["id"], pending[1]["id"]}
        for row in remaining:
            assert row["id"] not in completed_ids
            assert row["status"] == "pending"

    def test_excludes_failed(self, db: Database, run_id: int):
        cps = _make_checkpoints(4)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        db.fail_checkpoint(pending[0]["id"])
        remaining = db.get_pending_checkpoints(run_id)
        assert len(remaining) == 3

    def test_ordered_by_id(self, db: Database, run_id: int):
        cps = _make_checkpoints(5)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        ids = [r["id"] for r in pending]
        assert ids == sorted(ids)

    def test_scoped_to_run_id(self, db: Database):
        """Checkpoints from a different run are not returned."""
        run_a = db.start_search_run("historical_build")
        run_b = db.start_search_run("historical_build")
        db.insert_checkpoint_batch(run_a, [{"query_hash": "aaa1", "query_text": "query A1"}])
        db.insert_checkpoint_batch(run_b, [
            {"query_hash": "bbb1", "query_text": "query B1"},
            {"query_hash": "bbb2", "query_text": "query B2"},
        ])
        assert len(db.get_pending_checkpoints(run_a)) == 1
        assert len(db.get_pending_checkpoints(run_b)) == 2


class TestCompleteCheckpoint:
    """complete_checkpoint: marks a checkpoint as completed with results."""

    def test_status_changes_to_completed(self, db: Database, run_id: int):
        cps = _make_checkpoints(1)
        db.insert_checkpoint_batch(run_id, cps)
        cp = db.get_pending_checkpoints(run_id)[0]
        db.complete_checkpoint(cp["id"], new_findings=7, updated_findings=2)
        assert len(db.get_pending_checkpoints(run_id)) == 0
        progress = db.get_checkpoint_progress(run_id)
        assert progress["completed"] == 1
        assert progress["pending"] == 0
        assert progress["new_findings"] == 7
        assert progress["updated_findings"] == 2

    def test_completed_at_is_set(self, db: Database, run_id: int):
        cps = _make_checkpoints(1)
        db.insert_checkpoint_batch(run_id, cps)
        cp = db.get_pending_checkpoints(run_id)[0]
        assert cp["completed_at"] is None
        db.complete_checkpoint(cp["id"], new_findings=0, updated_findings=0)
        with db.connect() as conn:
            row = conn.execute(
                "SELECT completed_at FROM search_checkpoints WHERE id = ?",
                (cp["id"],),
            ).fetchone()
            assert row["completed_at"] is not None

    def test_default_counts_are_zero(self, db: Database, run_id: int):
        cps = _make_checkpoints(1)
        db.insert_checkpoint_batch(run_id, cps)
        cp = db.get_pending_checkpoints(run_id)[0]
        db.complete_checkpoint(cp["id"])
        progress = db.get_checkpoint_progress(run_id)
        assert progress["new_findings"] == 0
        assert progress["updated_findings"] == 0


class TestFailCheckpoint:
    """fail_checkpoint: marks a checkpoint as failed."""

    def test_status_changes_to_failed(self, db: Database, run_id: int):
        cps = _make_checkpoints(2)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        db.fail_checkpoint(pending[0]["id"])
        progress = db.get_checkpoint_progress(run_id)
        assert progress["failed"] == 1
        assert progress["pending"] == 1

    def test_failed_not_in_pending(self, db: Database, run_id: int):
        cps = _make_checkpoints(3)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        failed_id = pending[1]["id"]
        db.fail_checkpoint(failed_id)
        remaining = db.get_pending_checkpoints(run_id)
        assert all(r["id"] != failed_id for r in remaining)
        assert len(remaining) == 2


class TestResetFailedCheckpoints:
    """reset_failed_checkpoints: resets failed back to pending."""

    def test_failed_become_pending(self, db: Database, run_id: int):
        cps = _make_checkpoints(5)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        for i in range(3):
            db.fail_checkpoint(pending[i]["id"])
        assert db.get_checkpoint_progress(run_id)["failed"] == 3
        reset_count = db.reset_failed_checkpoints(run_id)
        assert reset_count == 3
        progress = db.get_checkpoint_progress(run_id)
        assert progress["failed"] == 0
        assert progress["pending"] == 5

    def test_completed_not_affected(self, db: Database, run_id: int):
        cps = _make_checkpoints(4)
        db.insert_checkpoint_batch(run_id, cps)
        pending = db.get_pending_checkpoints(run_id)
        db.complete_checkpoint(pending[0]["id"], new_findings=5, updated_findings=0)
        db.complete_checkpoint(pending[1]["id"], new_findings=3, updated_findings=1)
        db.fail_checkpoint(pending[2]["id"])
        db.fail_checkpoint(pending[3]["id"])
        db.reset_failed_checkpoints(run_id)
        progress = db.get_checkpoint_progress(run_id)
        assert progress["completed"] == 2
        assert progress["failed"] == 0
        assert progress["pending"] == 2
        assert progress["new_findings"] == 8
        assert progress["updated_findings"] == 1

    def test_reset_returns_zero_when_none_failed(self, db: Database, run_id: int):
        db.insert_checkpoint_batch(run_id, _make_checkpoints(2))
        assert db.reset_failed_checkpoints(run_id) == 0

    def test_scoped_to_run_id(self, db: Database):
        """Only failed checkpoints for the given run_id are reset."""
        run_a = db.start_search_run("historical_build")
        run_b = db.start_search_run("historical_build")
        db.insert_checkpoint_batch(run_a, [{"query_hash": "aaa1", "query_text": "q1"}])
        db.insert_checkpoint_batch(run_b, [{"query_hash": "bbb1", "query_text": "q2"}])
        db.fail_checkpoint(db.get_pending_checkpoints(run_a)[0]["id"])
        db.fail_checkpoint(db.get_pending_checkpoints(run_b)[0]["id"])
        db.reset_failed_checkpoints(run_a)
        assert db.get_checkpoint_progress(run_a)["failed"] == 0
        assert db.get_checkpoint_progress(run_a)["pending"] == 1
        assert db.get_checkpoint_progress(run_b)["failed"] == 1
        assert db.get_checkpoint_progress(run_b)["pending"] == 0


class TestGetCheckpointProgress:
    """get_checkpoint_progress: returns accurate counts for all statuses."""

    def test_all_pending_initially(self, db: Database, run_id: int):
        db.insert_checkpoint_batch(run_id, _make_checkpoints(10))
        progress = db.get_checkpoint_progress(run_id)
        assert progress["total"] == 10
        assert progress["completed"] == 0
        assert progress["failed"] == 0
        assert progress["pending"] == 10
        assert progress["new_findings"] == 0
        assert progress["updated_findings"] == 0

    def test_mixed_statuses(self, db: Database, run_id: int):
        db.insert_checkpoint_batch(run_id, _make_checkpoints(10))
        pending = db.get_pending_checkpoints(run_id)
        db.complete_checkpoint(pending[0]["id"], new_findings=10, updated_findings=2)
        db.complete_checkpoint(pending[1]["id"], new_findings=5, updated_findings=3)
        db.complete_checkpoint(pending[2]["id"], new_findings=0, updated_findings=0)
        db.complete_checkpoint(pending[3]["id"], new_findings=8, updated_findings=1)
        db.fail_checkpoint(pending[4]["id"])
        db.fail_checkpoint(pending[5]["id"])
        progress = db.get_checkpoint_progress(run_id)
        assert progress["total"] == 10
        assert progress["completed"] == 4
        assert progress["failed"] == 2
        assert progress["pending"] == 4
        assert progress["new_findings"] == 23
        assert progress["updated_findings"] == 6

    def test_empty_run(self, db: Database, run_id: int):
        """Progress for a run with no checkpoints returns all zeros."""
        progress = db.get_checkpoint_progress(run_id)
        assert progress == {
            "total": 0, "completed": 0, "failed": 0,
            "pending": 0, "new_findings": 0, "updated_findings": 0,
        }


class TestGetLastIncompleteRun:
    """get_last_incomplete_run: finds the most recent running or interrupted run."""

    def test_returns_running_run(self, db: Database):
        run_id = db.start_search_run("historical_build")
        result = db.get_last_incomplete_run("historical_build")
        assert result is not None
        assert result["id"] == run_id
        assert result["status"] == "running"

    def test_returns_interrupted_run(self, db: Database):
        run_id = db.start_search_run("historical_build")
        db.interrupt_search_run(run_id)
        result = db.get_last_incomplete_run("historical_build")
        assert result is not None
        assert result["id"] == run_id
        assert result["status"] == "interrupted"

    def test_ignores_completed_runs(self, db: Database):
        run_id = db.start_search_run("historical_build")
        db.complete_search_run(run_id, queries_executed=10, findings_added=5, findings_updated=0)
        assert db.get_last_incomplete_run("historical_build") is None

    def test_ignores_failed_runs(self, db: Database):
        run_id = db.start_search_run("historical_build")
        db.fail_search_run(run_id)
        assert db.get_last_incomplete_run("historical_build") is None

    def test_returns_most_recent(self, db: Database):
        """When multiple incomplete runs exist, the most recent is returned."""
        run_1 = db.start_search_run("historical_build")
        db.interrupt_search_run(run_1)
        run_2 = db.start_search_run("historical_build")
        db.interrupt_search_run(run_2)
        run_3 = db.start_search_run("historical_build")
        result = db.get_last_incomplete_run("historical_build")
        assert result is not None
        assert result["id"] == run_3

    def test_scoped_to_run_type(self, db: Database):
        """Only returns runs matching the specified run_type."""
        build_id = db.start_search_run("historical_build")
        refresh_id = db.start_search_run("refresh")
        assert db.get_last_incomplete_run("historical_build")["id"] == build_id
        assert db.get_last_incomplete_run("refresh")["id"] == refresh_id

    def test_returns_none_when_no_runs(self, db: Database):
        assert db.get_last_incomplete_run("historical_build") is None


class TestInterruptSearchRun:
    """interrupt_search_run: marks a running search run as interrupted."""

    def test_status_becomes_interrupted(self, db: Database):
        run_id = db.start_search_run("historical_build")
        with db.connect() as conn:
            row = conn.execute("SELECT status FROM search_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "running"
        db.interrupt_search_run(run_id)
        with db.connect() as conn:
            row = conn.execute("SELECT status FROM search_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "interrupted"

    def test_completed_at_is_set(self, db: Database):
        run_id = db.start_search_run("historical_build")
        with db.connect() as conn:
            row = conn.execute("SELECT completed_at FROM search_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["completed_at"] is None
        db.interrupt_search_run(run_id)
        with db.connect() as conn:
            row = conn.execute("SELECT completed_at FROM search_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["completed_at"] is not None

    def test_interrupted_run_is_resumable(self, db: Database):
        """An interrupted run is found by get_last_incomplete_run."""
        run_id = db.start_search_run("historical_build")
        db.interrupt_search_run(run_id)
        result = db.get_last_incomplete_run("historical_build")
        assert result is not None
        assert result["id"] == run_id
        assert result["status"] == "interrupted"


class TestResumeFlow:
    """End-to-end: seed -> complete some -> interrupt -> resume -> finish."""

    def test_full_resume_lifecycle(self, db: Database):
        run_id = db.start_search_run("historical_build")
        db.insert_checkpoint_batch(run_id, _make_checkpoints(8))
        pending = db.get_pending_checkpoints(run_id)
        assert len(pending) == 8
        # Complete 3, fail 1
        db.complete_checkpoint(pending[0]["id"], new_findings=5, updated_findings=1)
        db.complete_checkpoint(pending[1]["id"], new_findings=3, updated_findings=0)
        db.complete_checkpoint(pending[2]["id"], new_findings=2, updated_findings=2)
        db.fail_checkpoint(pending[3]["id"])
        assert db.get_checkpoint_progress(run_id)["completed"] == 3
        # Interrupt
        db.interrupt_search_run(run_id)
        with db.connect() as conn:
            row = conn.execute("SELECT status FROM search_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "interrupted"
        # Resume
        prev = db.get_last_incomplete_run("historical_build")
        assert prev is not None
        assert prev["id"] == run_id
        assert db.reset_failed_checkpoints(run_id) == 1
        remaining = db.get_pending_checkpoints(run_id)
        assert len(remaining) == 5
        # Finish
        for cp in remaining:
            db.complete_checkpoint(cp["id"], new_findings=1, updated_findings=0)
        final = db.get_checkpoint_progress(run_id)
        assert final["total"] == 8
        assert final["completed"] == 8
        assert final["failed"] == 0
        assert final["pending"] == 0
        assert final["new_findings"] == 15  # 5+3+2+1*5
        assert final["updated_findings"] == 3  # 1+0+2+0*5
        assert db.get_pending_checkpoints(run_id) == []
        db.complete_search_run(run_id, queries_executed=8, findings_added=15, findings_updated=3)
        assert db.get_last_incomplete_run("historical_build") is None

    def test_resume_with_no_prior_run_returns_none(self, db: Database):
        assert db.get_last_incomplete_run("historical_build") is None

    def test_resume_does_not_re_seed_existing_checkpoints(self, db: Database):
        """Re-inserting the same checkpoint batch skips duplicates."""
        run_id = db.start_search_run("historical_build")
        cps = _make_checkpoints(5)
        assert db.insert_checkpoint_batch(run_id, cps) == 5
        pending = db.get_pending_checkpoints(run_id)
        db.complete_checkpoint(pending[0]["id"], new_findings=1, updated_findings=0)
        db.complete_checkpoint(pending[1]["id"], new_findings=1, updated_findings=0)
        assert db.insert_checkpoint_batch(run_id, cps) == 0
        assert len(db.get_pending_checkpoints(run_id)) == 3

    def test_multiple_interruptions_and_resumes(self, db: Database):
        """Build can be interrupted and resumed multiple times."""
        run_id = db.start_search_run("historical_build")
        db.insert_checkpoint_batch(run_id, _make_checkpoints(6))
        # Round 1: complete 2, interrupt
        pending = db.get_pending_checkpoints(run_id)
        db.complete_checkpoint(pending[0]["id"], new_findings=1, updated_findings=0)
        db.complete_checkpoint(pending[1]["id"], new_findings=1, updated_findings=0)
        db.interrupt_search_run(run_id)
        assert db.get_last_incomplete_run("historical_build")["id"] == run_id
        # Round 2: complete 2 more, fail 1, interrupt
        db.reset_failed_checkpoints(run_id)
        pending = db.get_pending_checkpoints(run_id)
        assert len(pending) == 4
        db.complete_checkpoint(pending[0]["id"], new_findings=1, updated_findings=0)
        db.complete_checkpoint(pending[1]["id"], new_findings=1, updated_findings=0)
        db.fail_checkpoint(pending[2]["id"])
        db.interrupt_search_run(run_id)
        progress = db.get_checkpoint_progress(run_id)
        assert progress["completed"] == 4
        assert progress["failed"] == 1
        assert progress["pending"] == 1
        # Round 3: finish everything
        db.reset_failed_checkpoints(run_id)
        pending = db.get_pending_checkpoints(run_id)
        assert len(pending) == 2
        for cp in pending:
            db.complete_checkpoint(cp["id"], new_findings=1, updated_findings=0)
        final = db.get_checkpoint_progress(run_id)
        assert final["total"] == 6
        assert final["completed"] == 6
        assert final["failed"] == 0
        assert final["pending"] == 0
