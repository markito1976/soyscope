"""Tests for novelty detection module."""

import pytest

from soyscope.novelty import (
    NoveltyResult,
    _fuzzy_similarity,
    _keyword_overlap,
    _normalize,
    get_novel_findings,
    score_finding_novelty,
    score_findings_batch,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello WORLD") == "hello world"

    def test_strip_punctuation(self):
        assert _normalize("hello, world!") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize("hello   world") == "hello world"

    def test_empty_string(self):
        assert _normalize("") == ""


class TestFuzzySimilarity:
    def test_identical(self):
        assert _fuzzy_similarity("PureBond", "PureBond") == 1.0

    def test_similar(self):
        sim = _fuzzy_similarity("PureBond adhesive", "PureBond soy adhesive")
        assert sim > 0.7

    def test_different(self):
        sim = _fuzzy_similarity("quantum dots photovoltaic", "plywood adhesive wood")
        assert sim < 0.3

    def test_empty(self):
        assert _fuzzy_similarity("", "anything") == 0.0
        assert _fuzzy_similarity("anything", "") == 0.0


class TestKeywordOverlap:
    def test_full_overlap(self):
        frac, matched = _keyword_overlap("adhesive sealant glue", ["adhesive", "sealant", "glue"])
        assert frac == 1.0
        assert len(matched) == 3

    def test_partial_overlap(self):
        frac, matched = _keyword_overlap("adhesive and bonding", ["adhesive", "sealant", "glue"])
        assert 0 < frac < 1.0
        assert "adhesive" in matched

    def test_no_overlap(self):
        frac, matched = _keyword_overlap("quantum physics laser", ["adhesive", "sealant"])
        assert frac == 0.0
        assert matched == []

    def test_empty_text(self):
        frac, matched = _keyword_overlap("", ["adhesive"])
        assert frac == 0.0

    def test_empty_keywords(self):
        frac, matched = _keyword_overlap("adhesive", [])
        assert frac == 0.0


# ---------------------------------------------------------------------------
# Known applications fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def known_apps():
    return [
        {
            "product_name": "PureBond",
            "manufacturer": "Columbia Forest Products",
            "sector": "Adhesives & Sealants",
            "derivative": "Soy Protein",
            "category": "Wood adhesives",
            "description": "Formaldehyde-free soy protein adhesive for hardwood plywood",
        },
        {
            "product_name": "Envirotemp FR3",
            "manufacturer": "Cargill",
            "sector": "Lubricants & Metalworking Fluids",
            "derivative": "Soy Oil",
            "category": "Dielectric fluids",
            "description": "Soy-based natural ester dielectric fluid for power transformers",
        },
        {
            "product_name": "BiOH",
            "manufacturer": "Cargill",
            "sector": "Plastics & Bioplastics",
            "derivative": "Soy-based Polyols",
            "category": "Polyols & foams",
            "description": "Soy-based polyols for flexible and rigid polyurethane foams",
        },
        {
            "product_name": "NatureWax C-3",
            "manufacturer": "Cargill",
            "sector": "Candles & Home Products",
            "derivative": "Soy Wax",
            "category": "Candle wax",
            "description": "Container blend soy wax dominates natural candle wax market",
        },
        {
            "product_name": "Intralipid",
            "manufacturer": "Fresenius Kabi",
            "sector": "Pharmaceuticals & Medical",
            "derivative": "Soy Oil",
            "category": "Parenteral nutrition",
            "description": "Soy oil-based IV fat emulsion for parenteral nutrition",
        },
    ]


# ---------------------------------------------------------------------------
# score_finding_novelty
# ---------------------------------------------------------------------------

class TestScoreFindingNovelty:
    def test_known_product_low_novelty(self, known_apps):
        finding = {
            "id": 1,
            "title": "PureBond soy protein adhesive for hardwood plywood",
            "abstract": "Columbia Forest Products formaldehyde-free wood adhesive system",
        }
        result = score_finding_novelty(finding, known_apps)
        assert isinstance(result, NoveltyResult)
        assert result.novelty_score < 30, f"Known product scored {result.novelty_score}"
        assert result.finding_id == 1

    def test_novel_finding_high_novelty(self, known_apps):
        finding = {
            "id": 2,
            "title": "Novel quantum dot synthesis from soybean waste for photovoltaic applications",
            "abstract": "We demonstrate green chemistry synthesis of CdSe quantum dots using soybean hull extract",
        }
        result = score_finding_novelty(finding, known_apps)
        assert result.novelty_score > 60, f"Novel finding scored only {result.novelty_score}"

    def test_related_but_different(self, known_apps):
        finding = {
            "id": 3,
            "title": "Soy protein-based 3D printing filament for biomedical scaffolds",
            "abstract": "Extrusion-based additive manufacturing using soy protein isolate composite",
        }
        result = score_finding_novelty(finding, known_apps)
        # Should be moderately novel — soy protein is known but 3D printing is not
        assert result.novelty_score > 40

    def test_no_title(self, known_apps):
        finding = {"id": 4, "title": ""}
        result = score_finding_novelty(finding, known_apps)
        assert result.novelty_score == 50.0

    def test_no_abstract(self, known_apps):
        finding = {
            "id": 5,
            "title": "PureBond formaldehyde-free plywood adhesive development",
        }
        result = score_finding_novelty(finding, known_apps)
        # Should still detect known product from title alone
        assert result.novelty_score < 40

    def test_exact_product_mention(self, known_apps):
        finding = {
            "id": 6,
            "title": "Performance evaluation of Envirotemp FR3 natural ester fluid",
            "abstract": "Cargill FR3 dielectric fluid testing in distribution transformers",
        }
        result = score_finding_novelty(finding, known_apps)
        assert result.novelty_score < 25

    def test_result_has_explanation(self, known_apps):
        finding = {"id": 7, "title": "Soy wax candle market analysis"}
        result = score_finding_novelty(finding, known_apps)
        assert result.explanation
        assert len(result.explanation) > 10

    def test_result_has_best_match(self, known_apps):
        finding = {
            "id": 8,
            "title": "Intralipid IV emulsion for neonatal nutrition",
            "abstract": "Fresenius Kabi parenteral nutrition",
        }
        result = score_finding_novelty(finding, known_apps)
        assert result.best_match_product is not None
        assert result.best_match_sector is not None
        assert result.best_match_similarity > 0

    def test_with_sector_keywords(self, known_apps):
        sector_keywords = {
            "Adhesives & Sealants": ["adhesive", "sealant", "glue", "binder", "bonding"],
            "Energy & Biofuels": ["biodiesel", "renewable diesel", "bioenergy"],
        }
        finding = {
            "id": 9,
            "title": "Novel soy-based adhesive system for automotive composite bonding",
        }
        result = score_finding_novelty(finding, known_apps, sector_keywords)
        # Sector keywords should help detect relevance
        assert result.novelty_score < 80


# ---------------------------------------------------------------------------
# score_findings_batch
# ---------------------------------------------------------------------------

class TestScoreFindingsBatch:
    def test_batch_scoring(self, known_apps):
        findings = [
            {"id": 1, "title": "PureBond soy adhesive for plywood"},
            {"id": 2, "title": "Novel quantum dot from soybean waste"},
            {"id": 3, "title": "Soy wax candle market trends"},
        ]
        results = score_findings_batch(findings, known_apps)
        assert len(results) == 3
        assert all(isinstance(r, NoveltyResult) for r in results)

    def test_empty_batch(self, known_apps):
        results = score_findings_batch([], known_apps)
        assert results == []


# ---------------------------------------------------------------------------
# get_novel_findings
# ---------------------------------------------------------------------------

class TestGetNovelFindings:
    def test_filters_by_threshold(self, known_apps):
        findings = [
            {"id": 1, "title": "PureBond soy adhesive for plywood"},
            {"id": 2, "title": "Completely novel quantum nanoparticle soybean waste application for space exploration"},
        ]
        novel = get_novel_findings(findings, known_apps, threshold=70.0)
        # Only truly novel ones should pass threshold
        for r in novel:
            assert r.novelty_score >= 70.0

    def test_sorted_descending(self, known_apps):
        findings = [
            {"id": 1, "title": "Known soy oil biodiesel production"},
            {"id": 2, "title": "Novel soy nanofiber quantum computing substrate"},
            {"id": 3, "title": "Soy protein concrete reinforcement pilot study"},
        ]
        novel = get_novel_findings(findings, known_apps, threshold=0.0)
        for i in range(len(novel) - 1):
            assert novel[i].novelty_score >= novel[i + 1].novelty_score

    def test_empty_known_apps(self):
        findings = [{"id": 1, "title": "Anything"}]
        novel = get_novel_findings(findings, [], threshold=0.0)
        assert len(novel) == 1
        # With no known apps, everything should be novel
        assert novel[0].novelty_score >= 50.0
