"""Tests for deduplication logic."""

import pytest

from soyscope.dedup import (
    Deduplicator,
    deduplicate_papers,
    is_duplicate_title,
    normalize_doi,
    normalize_title,
)
from soyscope.models import Paper, SourceType


class TestNormalization:
    def test_normalize_doi_basic(self):
        assert normalize_doi("10.1234/test") == "10.1234/test"

    def test_normalize_doi_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/test") == "10.1234/test"
        assert normalize_doi("http://dx.doi.org/10.1234/test") == "10.1234/test"

    def test_normalize_doi_case(self):
        assert normalize_doi("10.1234/TEST") == "10.1234/test"

    def test_normalize_doi_none(self):
        assert normalize_doi(None) is None
        assert normalize_doi("") is None

    def test_normalize_title(self):
        assert normalize_title("  Hello, World!  ") == "hello world"
        assert normalize_title("Soy-Based Adhesive (2022)") == "soybased adhesive 2022"

    def test_normalize_title_whitespace(self):
        assert normalize_title("a   b\t\nc") == "a b c"


class TestFuzzyDuplication:
    def test_exact_match(self):
        assert is_duplicate_title("Soy adhesive test", "Soy adhesive test")

    def test_case_insensitive(self):
        assert is_duplicate_title("Soy Adhesive Test", "soy adhesive test")

    def test_minor_difference(self):
        assert is_duplicate_title(
            "Soy-based adhesive for plywood manufacturing",
            "Soy based adhesive for plywood manufacturing",
        )

    def test_different_titles(self):
        assert not is_duplicate_title(
            "Soy adhesive for construction",
            "Biodiesel from soybean oil",
        )


class TestDeduplicator:
    def test_doi_dedup(self):
        dedup = Deduplicator()
        p1 = Paper(title="Paper 1", doi="10.1234/a", source_api="openalex")
        p2 = Paper(title="Paper 2", doi="10.1234/a", source_api="semantic_scholar")

        assert not dedup.is_duplicate(p1)[0]
        dedup.register(p1)
        assert dedup.is_duplicate(p2)[0]

    def test_title_dedup(self):
        dedup = Deduplicator()
        p1 = Paper(title="Soy protein adhesive for wood composites", source_api="openalex")
        p2 = Paper(title="Soy protein adhesive for wood composites", source_api="pubmed")

        assert not dedup.is_duplicate(p1)[0]
        dedup.register(p1)
        assert dedup.is_duplicate(p2)[0]

    def test_load_existing(self):
        dedup = Deduplicator()
        dedup.load_existing(
            dois={"10.1234/existing"},
            titles=[(1, "Existing paper title")],
        )
        p = Paper(title="New paper", doi="10.1234/existing", source_api="test")
        assert dedup.is_duplicate(p)[0]

    def test_deduplicate_papers(self):
        papers = [
            Paper(title="Paper A", doi="10.1234/a", source_api="openalex"),
            Paper(title="Paper B", doi="10.1234/b", source_api="openalex"),
            Paper(title="Paper A duplicate", doi="10.1234/a", source_api="pubmed"),
            Paper(title="Paper C", source_api="exa"),
        ]
        unique = deduplicate_papers(papers)
        assert len(unique) == 3  # A, B, C (A duplicate removed)

    def test_deduplicate_with_existing(self):
        papers = [
            Paper(title="New paper", doi="10.1234/new", source_api="openalex"),
            Paper(title="Existing paper", doi="10.1234/existing", source_api="openalex"),
        ]
        unique = deduplicate_papers(papers, existing_dois={"10.1234/existing"})
        assert len(unique) == 1
        assert unique[0].doi == "10.1234/new"
