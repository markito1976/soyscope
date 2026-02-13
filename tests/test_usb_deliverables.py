"""Tests for USB deliverables importer."""

import csv
import tempfile
from pathlib import Path

import pytest

from soyscope.db import Database
from soyscope.models import SourceType, USBDeliverable
from soyscope.collectors.usb_deliverables_importer import (
    USBDeliverablesImporter,
    _clean_no_match,
    _extract_doi,
    _map_source_type,
)


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


@pytest.fixture
def importer(db):
    return USBDeliverablesImporter(db=db, unpaywall_email=None)


@pytest.fixture
def sample_csv(tmp_path):
    """Create a small fixture CSV file."""
    csv_path = tmp_path / "test_deliverables.csv"
    rows = [
        {
            "Title": "Soy Protein Adhesive for Plywood",
            "DOI Link": "https://doi.org/10.1234/soy.2023.001",
            "Type": "Primary Research",
            "Submitted Year": "",
            "Published Year": "2023",
            "Month": "Jun",
            "Journal Name": "Journal of Adhesion",
            "Authors": "Smith, J., Doe, J.",
            "Combined Authors": "",
            "Funders": "United Soybean Board",
            "Award Numbers": "",
            "Smithbucklin Project Number": "",
            "USB Project Number Lookup": "#NO MATCH",
            "USB #": "2340-101-0001",
            "Project Number": "2340-101-0001",
            "Target Area": "",
            "Fiscal Year": "",
            "Investment Category": "Industrial",
            "Action Team": "",
            "Program Name": "",
            "Sub-Program Name": "",
            "Key Categories": "Adhesives",
            "Keywords": "soy protein,adhesive,plywood",
            "PI Name": "John Smith",
            "PI Email": "jsmith@example.com",
            "Organization": "Iowa State University",
            "Program Manager": "",
            "Program Manager Email": "",
            "Project Manager Email": "",
            "Date of Last Change": "",
            "Quarter": "",
            "Date of Last PI Update": "",
            "Status": "",
            "Targeted Journal(s)": "",
            "Submitted by Name": "",
            "Priority Area": "New Uses",
            "Submitted By Email": "",
            "Current Program Manager": "",
            "Do you need funds for publishing open access?": "",
            "Project Manager": "",
            "Created": "",
            "Send Approval Notification": "",
            "Re-email PM": "",
            "Send Notification Email": "",
            "Smartsheet Admin Email": "",
            "Additional Project Numbers": "",
            "Journal Response": "",
        },
        {
            "Title": "Soybean Oil in Biodiesel Production",
            "DOI Link": "https://patents.google.com/patent/US12345",
            "Type": "Patent",
            "Submitted Year": "2022",
            "Published Year": "",
            "Month": "",
            "Journal Name": "",
            "Authors": "Doe, J.",
            "Combined Authors": "Jane Doe",
            "Funders": "United Soybean Board",
            "Award Numbers": "",
            "Smithbucklin Project Number": "",
            "USB Project Number Lookup": "2240-200-0100",
            "USB #": "2240-200-0100",
            "Project Number": "",
            "Target Area": "",
            "Fiscal Year": "",
            "Investment Category": "Feed",
            "Action Team": "",
            "Program Name": "",
            "Sub-Program Name": "",
            "Key Categories": "#NO MATCH",
            "Keywords": "biodiesel;soybean oil",
            "PI Name": "",
            "PI Email": "",
            "Organization": "",
            "Program Manager": "",
            "Program Manager Email": "",
            "Project Manager Email": "",
            "Date of Last Change": "",
            "Quarter": "",
            "Date of Last PI Update": "",
            "Status": "",
            "Targeted Journal(s)": "",
            "Submitted by Name": "",
            "Priority Area": "#NO MATCH",
            "Submitted By Email": "",
            "Current Program Manager": "",
            "Do you need funds for publishing open access?": "",
            "Project Manager": "",
            "Created": "",
            "Send Approval Notification": "",
            "Re-email PM": "",
            "Send Notification Email": "",
            "Smartsheet Admin Email": "",
            "Additional Project Numbers": "",
            "Journal Response": "",
        },
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


class TestCleanNoMatch:
    def test_no_match(self):
        assert _clean_no_match("#NO MATCH") is None

    def test_no_match_lowercase(self):
        assert _clean_no_match("#no match") is None

    def test_empty(self):
        assert _clean_no_match("") is None

    def test_none(self):
        assert _clean_no_match(None) is None

    def test_valid(self):
        assert _clean_no_match("Industrial") == "Industrial"


class TestExtractDoi:
    def test_standard_url(self):
        assert _extract_doi("https://doi.org/10.1234/test.2023.001") == "10.1234/test.2023.001"

    def test_embedded_doi(self):
        assert _extract_doi("Some text 10.5678/abc.123 more text") == "10.5678/abc.123"

    def test_patent_url_returns_none(self):
        assert _extract_doi("https://patents.google.com/patent/US12345") is None

    def test_none_input(self):
        assert _extract_doi(None) is None

    def test_empty_string(self):
        assert _extract_doi("") is None

    def test_no_doi_link(self):
        assert _extract_doi("https://example.com/some-page") is None

    def test_bare_doi(self):
        assert _extract_doi("10.1093/jas/skaf349") == "10.1093/jas/skaf349"

    def test_trailing_punctuation_stripped(self):
        assert _extract_doi("https://doi.org/10.1234/test.001.") == "10.1234/test.001"


class TestTypeMapping:
    def test_primary_research(self):
        assert _map_source_type("Primary Research") == SourceType.PAPER

    def test_review(self):
        assert _map_source_type("Review") == SourceType.PAPER

    def test_meta_analysis(self):
        assert _map_source_type("Meta Analysis") == SourceType.PAPER

    def test_modeling(self):
        assert _map_source_type("Modeling") == SourceType.PAPER

    def test_methodology(self):
        assert _map_source_type("Methodology") == SourceType.PAPER

    def test_response_commentary(self):
        assert _map_source_type("Response/Commentary") == SourceType.PAPER

    def test_book_chapter(self):
        assert _map_source_type("Book Chapter") == SourceType.PAPER

    def test_proceedings(self):
        assert _map_source_type("Proceedings Article") == SourceType.CONFERENCE

    def test_patent(self):
        assert _map_source_type("Patent") == SourceType.PATENT

    def test_survey(self):
        assert _map_source_type("Survey") == SourceType.REPORT

    def test_strategic_plan(self):
        assert _map_source_type("Strategic Plan") == SourceType.REPORT

    def test_unknown_defaults_paper(self):
        assert _map_source_type("Something New") == SourceType.PAPER

    def test_none_defaults_paper(self):
        assert _map_source_type(None) == SourceType.PAPER


class TestParseRow:
    def test_standard_row(self, importer):
        row = {
            "Title": "Test Paper Title",
            "DOI Link": "https://doi.org/10.1234/test",
            "Type": "Primary Research",
            "Submitted Year": "",
            "Published Year": "2023",
            "Month": "Jun",
            "Journal Name": "Test Journal",
            "Authors": "Smith, J.",
            "Combined Authors": "",
            "Funders": "USB",
            "USB Project Number Lookup": "#NO MATCH",
            "USB #": "2340-101-0001",
            "Project Number": "2340-101-0001",
            "Investment Category": "Industrial",
            "Key Categories": "Adhesives",
            "Keywords": "soy,adhesive",
            "PI Name": "John Smith",
            "PI Email": "js@test.com",
            "Organization": "ISU",
            "Priority Area": "#NO MATCH",
        }
        d = importer._parse_row(row)
        assert d.title == "Test Paper Title"
        assert d.published_year == 2023
        assert d.usb_project_number == "2340-101-0001"
        assert d.keywords == ["soy", "adhesive"]
        assert d.priority_area is None  # cleaned #NO MATCH
        assert d.investment_category == "Industrial"

    def test_no_match_cleaning(self, importer):
        row = {
            "Title": "Test",
            "DOI Link": "",
            "Type": "",
            "Submitted Year": "",
            "Published Year": "",
            "Month": "",
            "Journal Name": "",
            "Authors": "",
            "Combined Authors": "",
            "Funders": "",
            "USB Project Number Lookup": "#NO MATCH",
            "USB #": "#NO MATCH",
            "Project Number": "",
            "Investment Category": "#NO MATCH",
            "Key Categories": "#NO MATCH",
            "Keywords": "",
            "PI Name": "",
            "PI Email": "",
            "Organization": "",
            "Priority Area": "#NO MATCH",
        }
        d = importer._parse_row(row)
        assert d.usb_project_number is None
        assert d.investment_category is None
        assert d.key_categories is None
        assert d.priority_area is None


class TestCreatePaperFromDeliverable:
    def test_standard(self, importer):
        d = USBDeliverable(
            title="Test Paper",
            doi_link="https://doi.org/10.1234/test",
            deliverable_type="Primary Research",
            published_year=2023,
            journal_name="Test Journal",
            authors="Smith, J., Doe, J.",
            keywords=["soy", "adhesive"],
        )
        paper = importer._create_paper_from_deliverable(d)
        assert paper.title == "Test Paper"
        assert paper.doi == "10.1234/test"
        assert paper.year == 2023
        assert paper.source_api == "usb_deliverables"
        assert paper.source_type == SourceType.PAPER
        assert paper.venue == "Test Journal"

    def test_patent_no_doi(self, importer):
        d = USBDeliverable(
            title="Soy Patent",
            doi_link="https://patents.google.com/patent/US12345",
            deliverable_type="Patent",
            submitted_year=2022,
        )
        paper = importer._create_paper_from_deliverable(d)
        assert paper.doi is None
        assert paper.source_type == SourceType.PATENT
        assert paper.year == 2022  # falls back to submitted_year

    def test_combined_authors_preferred(self, importer):
        d = USBDeliverable(
            title="Test",
            combined_authors="John Smith, Jane Doe",
            authors="Smith J, Doe J",
        )
        paper = importer._create_paper_from_deliverable(d)
        assert paper.authors == ["John Smith", "Jane Doe"]


class TestDbInsertDeliverable:
    def test_insert(self, db):
        d = USBDeliverable(
            title="Test Deliverable",
            doi_link="https://doi.org/10.1234/test",
            deliverable_type="Primary Research",
            published_year=2023,
            keywords=["soy"],
        )
        result = db.insert_usb_deliverable(d)
        assert result is not None
        assert result > 0

    def test_duplicate_handling(self, db):
        d = USBDeliverable(
            title="Test Deliverable",
            doi_link="https://doi.org/10.1234/test",
        )
        id1 = db.insert_usb_deliverable(d)
        id2 = db.insert_usb_deliverable(d)
        assert id1 is not None
        assert id2 is None  # duplicate

    def test_count(self, db):
        d = USBDeliverable(title="Test 1", doi_link="https://doi.org/10.1234/a")
        db.insert_usb_deliverable(d)
        d2 = USBDeliverable(title="Test 2", doi_link="https://doi.org/10.1234/b")
        db.insert_usb_deliverable(d2)
        assert db.get_usb_deliverables_count() == 2

    def test_update_finding_oa(self, db):
        from soyscope.models import Paper, SourceType
        paper = Paper(
            title="OA Test Paper",
            doi="10.9999/oa.test",
            source_api="test",
            source_type=SourceType.PAPER,
        )
        fid = db.insert_finding(paper)
        db.update_finding_oa(fid, "https://example.com/paper.pdf", "gold")
        found = db.get_finding_by_id(fid)
        assert found["pdf_url"] == "https://example.com/paper.pdf"
        assert found["open_access_status"] == "gold"


class TestImportFromCsv:
    @pytest.mark.asyncio
    async def test_import_basic(self, db, sample_csv):
        importer = USBDeliverablesImporter(db=db, unpaywall_email=None)
        result = await importer.import_from_csv(sample_csv, resolve_oa=False)
        assert result["total_rows"] == 2
        assert result["raw_imported"] == 2
        assert result["findings_added"] >= 1  # at least the DOI one
        assert db.get_usb_deliverables_count() == 2

    @pytest.mark.asyncio
    async def test_idempotent_reimport(self, db, sample_csv):
        importer = USBDeliverablesImporter(db=db, unpaywall_email=None)
        r1 = await importer.import_from_csv(sample_csv, resolve_oa=False)
        r2 = await importer.import_from_csv(sample_csv, resolve_oa=False)
        # Second run should skip all raw records as duplicates
        assert r2["raw_skipped"] == 2
        # Total in DB should still be 2
        assert db.get_usb_deliverables_count() == 2

    @pytest.mark.asyncio
    async def test_stats_include_deliverables(self, db, sample_csv):
        importer = USBDeliverablesImporter(db=db, unpaywall_email=None)
        await importer.import_from_csv(sample_csv, resolve_oa=False)
        stats = db.get_stats()
        assert stats["total_usb_deliverables"] == 2
        assert "usb_deliverables" in stats["by_source"]

    @pytest.mark.asyncio
    async def test_file_not_found(self, db):
        importer = USBDeliverablesImporter(db=db, unpaywall_email=None)
        with pytest.raises(FileNotFoundError):
            await importer.import_from_csv(Path("/nonexistent/file.csv"), resolve_oa=False)

    @pytest.mark.asyncio
    async def test_keywords_tagged(self, db, sample_csv):
        importer = USBDeliverablesImporter(db=db, unpaywall_email=None)
        await importer.import_from_csv(sample_csv, resolve_oa=False)
        stats = db.get_stats()
        assert stats["total_tags"] > 0
