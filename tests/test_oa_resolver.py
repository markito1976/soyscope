"""Tests for OA resolver."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from soyscope.db import Database
from soyscope.models import OAStatus, Paper, SourceType


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


class TestOAResolver:
    def test_get_unresolved_dois(self, db):
        """Should return findings with DOIs but no pdf_url."""
        from soyscope.collectors.oa_resolver import OAResolver

        paper = Paper(
            title="Test paper",
            doi="10.1234/test",
            source_api="test",
        )
        db.insert_finding(paper)

        resolver = OAResolver(db=db, email="test@example.com")
        pairs = resolver.get_unresolved_dois()
        assert len(pairs) == 1
        assert pairs[0][1] == "10.1234/test"

    def test_skips_already_resolved(self, db):
        """Should not return findings that already have pdf_url."""
        from soyscope.collectors.oa_resolver import OAResolver

        paper = Paper(
            title="Test paper",
            doi="10.1234/test",
            pdf_url="https://example.com/test.pdf",
            source_api="test",
        )
        db.insert_finding(paper)

        resolver = OAResolver(db=db, email="test@example.com")
        pairs = resolver.get_unresolved_dois()
        assert len(pairs) == 0

    def test_limit_parameter(self, db):
        """Should respect limit parameter."""
        from soyscope.collectors.oa_resolver import OAResolver

        for i in range(5):
            paper = Paper(
                title=f"Test paper {i}",
                doi=f"10.1234/test{i}",
                source_api="test",
            )
            db.insert_finding(paper)

        resolver = OAResolver(db=db, email="test@example.com")
        pairs = resolver.get_unresolved_dois(limit=3)
        assert len(pairs) == 3

    def test_resolve_all_empty(self, db):
        """Should return 0 when no DOIs need resolving."""
        from soyscope.collectors.oa_resolver import OAResolver

        resolver = OAResolver(db=db, email="test@example.com")
        count = asyncio.run(resolver.resolve_all())
        assert count == 0

    def test_resolve_all_with_mock(self, db):
        """Should resolve DOIs via Unpaywall mock."""
        from soyscope.collectors.oa_resolver import OAResolver

        paper = Paper(
            title="Test paper",
            doi="10.1234/test",
            source_api="test",
        )
        db.insert_finding(paper)

        resolver = OAResolver(db=db, email="test@example.com", rate_delay=0)

        mock_result = Paper(
            title="Test paper",
            doi="10.1234/test",
            pdf_url="https://example.com/paper.pdf",
            open_access_status=OAStatus.GOLD,
            source_api="unpaywall",
        )

        with patch.object(resolver._unpaywall, "get_by_doi", new_callable=AsyncMock, return_value=mock_result):
            count = asyncio.run(resolver.resolve_all())

        assert count == 1

        # Verify the finding was updated
        finding = db.get_finding_by_doi("10.1234/test")
        assert finding["pdf_url"] == "https://example.com/paper.pdf"
        assert finding["open_access_status"] == "gold"

    def test_progress_callback(self, db):
        """Should call progress_callback during resolution."""
        from soyscope.collectors.oa_resolver import OAResolver

        paper = Paper(
            title="Test paper",
            doi="10.1234/test",
            source_api="test",
        )
        db.insert_finding(paper)

        progress_calls = []

        def _cb(current, total, msg):
            progress_calls.append((current, total, msg))

        resolver = OAResolver(db=db, email="test@example.com", rate_delay=0, progress_callback=_cb)

        mock_result = Paper(
            title="Test paper",
            doi="10.1234/test",
            pdf_url="https://example.com/paper.pdf",
            open_access_status=OAStatus.GOLD,
            source_api="unpaywall",
        )

        with patch.object(resolver._unpaywall, "get_by_doi", new_callable=AsyncMock, return_value=mock_result):
            asyncio.run(resolver.resolve_all())

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == 1  # current
        assert progress_calls[0][1] == 1  # total
