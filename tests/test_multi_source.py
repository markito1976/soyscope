"""Tests for multi-source tracking."""

import pytest

from soyscope.db import Database
from soyscope.dedup import Deduplicator, normalize_doi
from soyscope.models import Paper, SourceType


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


@pytest.fixture
def sample_paper():
    return Paper(
        title="Soy-based adhesive for plywood manufacturing",
        abstract="This study investigates a novel soy protein-based adhesive.",
        year=2022,
        doi="10.1234/test.2022.001",
        url="https://example.com/paper1",
        authors=["John Smith", "Jane Doe"],
        venue="Journal of Adhesion Science",
        source_api="openalex",
        source_type=SourceType.PAPER,
        citation_count=15,
    )


class TestFindingSources:
    def test_insert_auto_tracks_source(self, db, sample_paper):
        """insert_finding should auto-insert into finding_sources."""
        fid = db.insert_finding(sample_paper)
        sources = db.get_finding_sources(fid)
        assert "openalex" in sources

    def test_add_second_source(self, db, sample_paper):
        """Adding another source should be tracked."""
        fid = db.insert_finding(sample_paper)
        db.add_finding_source(fid, "semantic_scholar")
        sources = db.get_finding_sources(fid)
        assert len(sources) == 2
        assert "openalex" in sources
        assert "semantic_scholar" in sources

    def test_duplicate_source_ignored(self, db, sample_paper):
        """Adding the same source twice should be silently ignored."""
        fid = db.insert_finding(sample_paper)
        db.add_finding_source(fid, "openalex")
        sources = db.get_finding_sources(fid)
        assert len(sources) == 1

    def test_backfill_finding_sources(self, db, sample_paper):
        """Backfill should seed from existing source_api column."""
        db.insert_finding(sample_paper)
        # Clear finding_sources to simulate pre-migration state
        with db.connect() as conn:
            conn.execute("DELETE FROM finding_sources")

        count = db.backfill_finding_sources()
        assert count == 1
        sources = db.get_finding_sources(1)
        assert "openalex" in sources

    def test_get_all_finding_sources_map(self, db, sample_paper):
        """Bulk source map should return all sources per finding."""
        fid = db.insert_finding(sample_paper)
        db.add_finding_source(fid, "pubmed")
        smap = db.get_all_finding_sources_map()
        assert fid in smap
        assert len(smap[fid]) == 2

    def test_get_doi_to_id_map(self, db, sample_paper):
        """DOI-to-ID map should return correct mapping."""
        fid = db.insert_finding(sample_paper)
        doi_map = db.get_doi_to_id_map()
        assert doi_map["10.1234/test.2022.001"] == fid

    def test_stats_multi_source(self, db, sample_paper):
        """Stats should include multi-source counts."""
        fid = db.insert_finding(sample_paper)
        db.add_finding_source(fid, "pubmed")
        stats = db.get_stats()
        assert stats["findings_with_multiple_sources"] == 1
        assert stats["avg_sources_per_finding"] > 1.0

    def test_batch_insert_tracks_sources(self, db):
        """insert_findings_batch should also track sources."""
        papers = [
            Paper(title=f"Paper {i}", doi=f"10.1234/batch{i}",
                  source_api="crossref", source_type=SourceType.PAPER)
            for i in range(3)
        ]
        count = db.insert_findings_batch(papers)
        assert count == 3

        smap = db.get_all_finding_sources_map()
        assert len(smap) == 3
        for sources in smap.values():
            assert "crossref" in sources


class TestDedupDOITracking:
    def test_doi_dedup_returns_existing_id(self):
        """When duplicate detected by DOI, existing_id should be returned."""
        dedup = Deduplicator()
        dedup.load_existing(
            dois={"10.1234/a"},
            titles=[],
            doi_to_id={"10.1234/a": 42},
        )

        p = Paper(title="Some paper", doi="10.1234/a", source_api="pubmed")
        is_dup, existing_id = dedup.is_duplicate(p)
        assert is_dup
        assert existing_id == 42

    def test_doi_dedup_without_id_map(self):
        """Without doi_to_id, DOI dedup should still work but return None for id."""
        dedup = Deduplicator()
        dedup.load_existing(dois={"10.1234/a"}, titles=[])

        p = Paper(title="Some paper", doi="10.1234/a", source_api="pubmed")
        is_dup, existing_id = dedup.is_duplicate(p)
        assert is_dup
        assert existing_id is None

    def test_register_tracks_id(self):
        """register() should store DOI-to-ID mapping for later lookups."""
        dedup = Deduplicator()
        p1 = Paper(title="Paper 1", doi="10.1234/x", source_api="openalex")
        dedup.register(p1, db_id=99)

        p2 = Paper(title="Paper 2", doi="10.1234/x", source_api="pubmed")
        is_dup, existing_id = dedup.is_duplicate(p2)
        assert is_dup
        assert existing_id == 99
