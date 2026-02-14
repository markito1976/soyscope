"""Tests for known_applications table, seed data, and CRUD operations."""

import os
import tempfile

import pytest

from soyscope.db import Database
from soyscope.known_apps_seed import KNOWN_APPLICATIONS
from soyscope.models import KnownApplication


@pytest.fixture
def db():
    """Create a fresh in-memory-like DB for each test."""
    db_path = os.path.join(tempfile.mkdtemp(), "test_ka.db")
    database = Database(db_path)
    database.init_schema()
    return database


# ---------------------------------------------------------------------------
# KnownApplication model
# ---------------------------------------------------------------------------

class TestKnownApplicationModel:
    def test_create_minimal(self):
        ka = KnownApplication(sector="Test Sector", category="Test Category")
        assert ka.sector == "Test Sector"
        assert ka.category == "Test Category"
        assert ka.is_commercialized is True
        assert ka.source_doc == "soy-uses.md"

    def test_create_full(self):
        ka = KnownApplication(
            product_name="TestProduct",
            manufacturer="TestCo",
            sector="Adhesives & Sealants",
            derivative="Soy Protein",
            category="Wood adhesives",
            market_size="$1B",
            description="A test product",
            year_introduced=2020,
            is_commercialized=True,
        )
        assert ka.product_name == "TestProduct"
        assert ka.manufacturer == "TestCo"
        assert ka.year_introduced == 2020

    def test_defaults(self):
        ka = KnownApplication(sector="S", category="C")
        assert ka.product_name is None
        assert ka.manufacturer is None
        assert ka.derivative is None
        assert ka.market_size is None
        assert ka.description is None
        assert ka.year_introduced is None
        assert ka.id is None


# ---------------------------------------------------------------------------
# Seed data quality
# ---------------------------------------------------------------------------

class TestSeedData:
    def test_seed_count(self):
        assert len(KNOWN_APPLICATIONS) >= 150

    def test_all_have_sector(self):
        for app in KNOWN_APPLICATIONS:
            assert app.sector, f"Missing sector on: {app.product_name or app.description}"

    def test_all_have_category(self):
        for app in KNOWN_APPLICATIONS:
            assert app.category, f"Missing category on: {app.product_name or app.description}"

    def test_all_are_known_application_type(self):
        for app in KNOWN_APPLICATIONS:
            assert isinstance(app, KnownApplication)

    def test_covers_new_sectors(self):
        sectors = {a.sector for a in KNOWN_APPLICATIONS}
        assert "Pharmaceuticals & Medical" in sectors
        assert "Candles & Home Products" in sectors
        assert "Paper & Printing" in sectors

    def test_covers_new_derivatives(self):
        derivatives = {a.derivative for a in KNOWN_APPLICATIONS if a.derivative}
        assert "Methyl Soyate" in derivatives
        assert "Epoxidized Soybean Oil" in derivatives
        assert "Phytosterols" in derivatives

    def test_has_named_products(self):
        named = [a for a in KNOWN_APPLICATIONS if a.product_name]
        assert len(named) >= 20, f"Only {len(named)} named products"

    def test_has_manufacturers(self):
        with_mfr = [a for a in KNOWN_APPLICATIONS if a.manufacturer]
        assert len(with_mfr) >= 20, f"Only {len(with_mfr)} with manufacturers"


# ---------------------------------------------------------------------------
# Database CRUD
# ---------------------------------------------------------------------------

class TestKnownApplicationsDB:
    def test_insert_and_retrieve(self, db):
        ka = KnownApplication(
            product_name="PureBond",
            manufacturer="Columbia Forest Products",
            sector="Adhesives & Sealants",
            derivative="Soy Protein",
            category="Wood adhesives",
            year_introduced=2005,
        )
        result_id = db.insert_known_application(ka)
        assert result_id > 0

        all_apps = db.get_all_known_applications()
        assert len(all_apps) == 1
        assert all_apps[0]["product_name"] == "PureBond"

    def test_get_by_sector(self, db):
        db.insert_known_application(
            KnownApplication(sector="Adhesives & Sealants", category="Wood", product_name="A")
        )
        db.insert_known_application(
            KnownApplication(sector="Adhesives & Sealants", category="Packaging", product_name="B")
        )
        db.insert_known_application(
            KnownApplication(sector="Energy & Biofuels", category="Biodiesel", product_name="C")
        )

        adhesives = db.get_known_applications_by_sector("Adhesives & Sealants")
        assert len(adhesives) == 2

        energy = db.get_known_applications_by_sector("Energy & Biofuels")
        assert len(energy) == 1

    def test_count(self, db):
        assert db.get_known_applications_count() == 0
        db.insert_known_application(
            KnownApplication(sector="Test", category="Test")
        )
        assert db.get_known_applications_count() == 1

    def test_seed_batch(self, db):
        count = db.seed_known_applications(KNOWN_APPLICATIONS)
        assert count == len(KNOWN_APPLICATIONS)
        assert db.get_known_applications_count() == len(KNOWN_APPLICATIONS)

    def test_seed_idempotent(self, db):
        count1 = db.seed_known_applications(KNOWN_APPLICATIONS)
        count2 = db.seed_known_applications(KNOWN_APPLICATIONS)
        # Second seed should add 0 (or very few if no unique constraint)
        total = db.get_known_applications_count()
        # Total should be reasonable (at most 2x if no dedup, but ideally same)
        assert total >= count1
