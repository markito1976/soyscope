"""Tests for enrichment modules."""

import pytest

from soyscope.enrichment.novelty_scorer import batch_score_novelty, score_novelty


class TestNoveltyScorer:
    def test_basic_score(self):
        score = score_novelty(title="Soy-based adhesive for construction")
        assert 0.0 <= score <= 1.0

    def test_novel_keywords_boost(self):
        novel_score = score_novelty(
            title="Novel breakthrough soy-based PFAS replacement for firefighting foam"
        )
        basic_score = score_novelty(
            title="Soy protein adhesive review"
        )
        assert novel_score > basic_score

    def test_maturity_keywords_reduce(self):
        mature_score = score_novelty(
            title="Established commercial soybean biodiesel production"
        )
        novel_score = score_novelty(
            title="Novel soybean-based quantum dot semiconductor"
        )
        assert mature_score < novel_score

    def test_recency_boost(self):
        recent = score_novelty(title="Soy material", year=2025)
        old = score_novelty(title="Soy material", year=2005)
        assert recent >= old

    def test_patent_boost(self):
        patent = score_novelty(title="Soy foam method", source_type="patent")
        paper = score_novelty(title="Soy foam method", source_type="paper")
        assert patent > paper

    def test_high_value_keywords(self):
        score = score_novelty(
            title="Soy-based nanotechnology for 3D printing carbon capture application"
        )
        assert score > 0.6

    def test_score_bounds(self):
        # Even extreme cases should be bounded
        high = score_novelty(
            title="Novel breakthrough pioneering innovative revolutionary first PFAS nanotechnology",
            year=2025,
            source_type="patent",
        )
        assert high <= 1.0

        low = score_novelty(
            title="Established conventional standard traditional mature commodity",
            year=2002,
            citation_count=0,
        )
        assert low >= 0.0

    def test_batch_scoring(self):
        findings = [
            {"id": 1, "title": "Novel soy PFAS replacement", "year": 2024},
            {"id": 2, "title": "Standard soy biodiesel production", "year": 2010},
            {"id": 3, "title": "Soy protein 3D printing nanotechnology", "year": 2025},
        ]
        results = batch_score_novelty(findings)
        assert len(results) == 3
        assert all(0.0 <= score <= 1.0 for _, score in results)
        # Novel finding should score higher
        scores = {fid: s for fid, s in results}
        assert scores[1] > scores[2] or scores[3] > scores[2]
