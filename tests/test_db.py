"""Tests for database operations."""

import tempfile
from pathlib import Path

import pytest

from soyscope.db import Database
from soyscope.models import CheckoffProject, Enrichment, EnrichmentTier, Paper, SourceType


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


@pytest.fixture
def sample_paper():
    return Paper(
        title="Soy-based adhesive for plywood manufacturing",
        abstract="This study investigates a novel soy protein-based adhesive for plywood.",
        year=2022,
        doi="10.1234/test.2022.001",
        url="https://example.com/paper1",
        authors=["John Smith", "Jane Doe"],
        venue="Journal of Adhesion Science",
        source_api="openalex",
        source_type=SourceType.PAPER,
        citation_count=15,
    )


class TestDatabase:
    def test_init_schema(self, db):
        """Schema creation should work without errors."""
        # Already initialized in fixture
        stats = db.get_stats()
        assert stats["total_findings"] == 0
        assert stats["total_sectors"] == 0

    def test_insert_finding(self, db, sample_paper):
        result_id = db.insert_finding(sample_paper)
        assert result_id is not None
        assert result_id > 0

    def test_duplicate_doi_handling(self, db, sample_paper):
        """Inserting a paper with the same DOI should update instead of error."""
        id1 = db.insert_finding(sample_paper)
        id2 = db.insert_finding(sample_paper)
        assert id1 is not None
        assert id2 is None  # Duplicate returns None

    def test_get_finding_by_doi(self, db, sample_paper):
        db.insert_finding(sample_paper)
        found = db.get_finding_by_doi("10.1234/test.2022.001")
        assert found is not None
        assert found["title"] == sample_paper.title

    def test_search_findings(self, db, sample_paper):
        db.insert_finding(sample_paper)
        results = db.search_findings("soy-based adhesive")
        assert len(results) == 1
        assert "adhesive" in results[0]["title"].lower()

    def test_sectors(self, db):
        sid = db.insert_sector("Construction & Building Materials", description="Test sector")
        assert sid > 0
        sectors = db.get_all_sectors()
        assert len(sectors) == 1
        assert sectors[0]["name"] == "Construction & Building Materials"

    def test_duplicate_sector(self, db):
        id1 = db.insert_sector("Construction")
        id2 = db.insert_sector("Construction")
        assert id1 == id2

    def test_derivatives(self, db):
        did = db.insert_derivative("Soy Oil", description="Test derivative")
        assert did > 0
        derivatives = db.get_all_derivatives()
        assert len(derivatives) == 1

    def test_finding_sector_link(self, db, sample_paper):
        fid = db.insert_finding(sample_paper)
        sid = db.insert_sector("Adhesives & Sealants")
        db.link_finding_sector(fid, sid, confidence=0.9)
        sectors = db.get_finding_sectors(fid)
        assert len(sectors) == 1
        assert sectors[0]["name"] == "Adhesives & Sealants"

    def test_finding_derivative_link(self, db, sample_paper):
        fid = db.insert_finding(sample_paper)
        did = db.insert_derivative("Soy Protein")
        db.link_finding_derivative(fid, did)
        derivatives = db.get_finding_derivatives(fid)
        assert len(derivatives) == 1
        assert derivatives[0]["name"] == "Soy Protein"

    def test_tags(self, db, sample_paper):
        fid = db.insert_finding(sample_paper)
        tid = db.insert_tag("bio-based")
        db.link_finding_tag(fid, tid)
        # Verify no errors

    def test_enrichment(self, db, sample_paper):
        fid = db.insert_finding(sample_paper)
        enrichment = Enrichment(
            finding_id=fid,
            tier=EnrichmentTier.CATALOG,
            novelty_score=0.75,
            trl_estimate=4,
        )
        db.insert_enrichment(enrichment)
        result = db.get_enrichment(fid)
        assert result is not None
        assert result["novelty_score"] == 0.75
        assert result["trl_estimate"] == 4

    def test_search_run(self, db):
        run_id = db.start_search_run("test")
        assert run_id > 0
        db.log_search_query(run_id, "soy adhesive", "openalex", 10, 5)
        db.complete_search_run(run_id, queries_executed=1, findings_added=5, findings_updated=0)
        last = db.get_last_search_run()
        assert last is not None
        assert last["status"] == "completed"

    def test_checkoff_project(self, db):
        project = CheckoffProject(
            year="2023",
            title="Soy-based foam insulation",
            category="Industrial Uses",
            keywords=["foam", "insulation", "construction"],
            lead_pi="Dr. Smith",
            institution="Iowa State University",
            funding=250000.0,
            summary="Development of soy-based spray foam insulation.",
        )
        result = db.insert_checkoff_project(project)
        assert result is not None
        assert db.get_checkoff_count() == 1

    def test_existing_dois(self, db, sample_paper):
        db.insert_finding(sample_paper)
        dois = db.get_existing_dois()
        assert "10.1234/test.2022.001" in dois

    def test_unenriched_findings(self, db, sample_paper):
        db.insert_finding(sample_paper)
        unenriched = db.get_unenriched_findings(tier="catalog")
        assert len(unenriched) == 1

    def test_stats(self, db, sample_paper):
        db.insert_finding(sample_paper)
        db.insert_sector("Test Sector")
        db.insert_derivative("Test Derivative")
        stats = db.get_stats()
        assert stats["total_findings"] == 1
        assert stats["total_sectors"] == 1
        assert stats["total_derivatives"] == 1
