"""Tests for query generator with synonym expansion, semantic queries, and Tier 1 routing."""

import pytest
from collections import Counter

from soyscope.collectors.query_generator import (
    SOY_SYNONYMS,
    SEMANTIC_QUERIES,
    _ACADEMIC_APIS_TIER1,
    _GOVT_REPORT_APIS,
    _PATENT_APIS,
    _SEMANTIC_APIS,
    _WEB_APIS,
    QueryPlan,
    expand_soy_synonyms,
    generate_academic_queries,
    generate_full_query_plan,
    generate_govt_queries,
    generate_patent_queries,
    generate_refresh_queries,
    generate_semantic_queries,
    generate_web_queries,
)


# ---------------------------------------------------------------------------
# SOY_SYNONYMS
# ---------------------------------------------------------------------------

class TestSoySynonyms:
    def test_synonyms_exist(self):
        assert len(SOY_SYNONYMS) >= 5

    def test_synonyms_content(self):
        assert "soy" in SOY_SYNONYMS
        assert "soybean" in SOY_SYNONYMS
        assert "soy bean" in SOY_SYNONYMS
        assert "soya" in SOY_SYNONYMS
        assert "soja" in SOY_SYNONYMS


# ---------------------------------------------------------------------------
# expand_soy_synonyms
# ---------------------------------------------------------------------------

class TestExpandSoySynonyms:
    def test_basic_expansion(self):
        result = expand_soy_synonyms("{soy} industrial adhesive")
        assert len(result) == len(SOY_SYNONYMS)
        assert result[0] == "soy industrial adhesive"
        assert result[1] == "soybean industrial adhesive"
        assert result[2] == "soy bean industrial adhesive"
        assert result[3] == "soya industrial adhesive"
        assert result[4] == "soja industrial adhesive"

    def test_no_placeholder_passthrough(self):
        result = expand_soy_synonyms("plain query without placeholder")
        assert len(result) == 1
        assert result[0] == "plain query without placeholder"

    def test_multiple_placeholders(self):
        result = expand_soy_synonyms("{soy} oil and {soy} protein")
        assert len(result) == len(SOY_SYNONYMS)
        assert result[0] == "soy oil and soy protein"
        assert result[1] == "soybean oil and soybean protein"

    def test_empty_string(self):
        result = expand_soy_synonyms("")
        assert len(result) == 1
        assert result[0] == ""

    def test_placeholder_only(self):
        result = expand_soy_synonyms("{soy}")
        assert result == SOY_SYNONYMS


# ---------------------------------------------------------------------------
# SEMANTIC_QUERIES
# ---------------------------------------------------------------------------

class TestSemanticQueries:
    def test_minimum_count(self):
        assert len(SEMANTIC_QUERIES) >= 20

    def test_no_soy_keyword(self):
        # These queries should NOT contain soy/soybean
        soy_words = {"soy", "soybean", "soy bean", "soya", "soja"}
        for q in SEMANTIC_QUERIES:
            words = set(q.lower().split())
            assert not words.intersection(soy_words), (
                f"Semantic query should not mention soy directly: {q}"
            )

    def test_all_strings(self):
        for q in SEMANTIC_QUERIES:
            assert isinstance(q, str)
            assert len(q) > 10

    def test_covers_key_domains(self):
        all_text = " ".join(SEMANTIC_QUERIES).lower()
        assert "polyurethane" in all_text or "foam" in all_text
        assert "adhesive" in all_text
        assert "biodiesel" in all_text or "renewable diesel" in all_text
        assert "composite" in all_text
        assert "lubricant" in all_text or "bio-lubricant" in all_text
        assert "coating" in all_text or "epoxy" in all_text


# ---------------------------------------------------------------------------
# generate_academic_queries
# ---------------------------------------------------------------------------

class TestGenerateAcademicQueries:
    def test_returns_list(self):
        result = generate_academic_queries("Soy Oil", "Adhesives & Sealants")
        assert isinstance(result, list)
        assert all(isinstance(q, str) for q in result)

    def test_includes_derivative_with_keywords(self):
        result = generate_academic_queries("Soy Oil", "Adhesives & Sealants")
        # Should have derivative paired with sector keywords, not sector name
        assert any("Soy Oil" in q and "adhesive" in q for q in result)

    def test_includes_synonym_expansion(self):
        result = generate_academic_queries("Soy Oil", "Adhesives & Sealants")
        has_soybean = any("soybean" in q.lower() for q in result)
        has_soy_bean = any("soy bean" in q.lower() for q in result)
        assert has_soybean, "Missing soybean synonym variant"
        assert has_soy_bean, "Missing 'soy bean' synonym variant"

    def test_query_count_with_keywords(self):
        # Adhesives has 19 keywords: 2 keyword-pair queries + 3 synonym-expanded = 5
        result = generate_academic_queries("Soy Oil", "Adhesives & Sealants")
        assert len(result) == 5

    def test_query_count_without_keywords(self):
        # Unknown sector: 1 fallback keyword-pair + 3 synonym-expanded = 4
        result = generate_academic_queries("Soy Oil", "Unknown Sector")
        assert len(result) == 4

    def test_includes_keyword_query(self):
        result = generate_academic_queries("Soy Oil", "Adhesives & Sealants")
        has_keyword = any("adhesive" in q.lower() for q in result)
        assert has_keyword


# ---------------------------------------------------------------------------
# generate_semantic_queries / generate_web_queries / generate_patent_queries / generate_govt_queries
# ---------------------------------------------------------------------------

class TestGenerateSemanticQueries:
    def test_returns_queries(self):
        result = generate_semantic_queries("Soy Oil", "Construction & Building Materials")
        assert len(result) == 4  # 2 templates x 2 synonyms

    def test_contains_derivative(self):
        result = generate_semantic_queries("Soy Oil", "Construction & Building Materials")
        assert any("soy oil" in q.lower() for q in result)

    def test_uses_two_synonyms(self):
        result = generate_semantic_queries("Soy Oil", "Construction & Building Materials")
        has_soy = any(q.startswith("soy ") or " soy " in q for q in result)
        has_soybean = any("soybean" in q for q in result)
        assert has_soy
        assert has_soybean


class TestGenerateWebQueries:
    def test_returns_queries(self):
        result = generate_web_queries("Soy Oil", "Construction & Building Materials")
        assert len(result) == 4  # 2 templates x 2 synonyms

    def test_contains_market_language(self):
        result = generate_web_queries("Soy Oil", "Construction & Building Materials")
        has_commercial = any("commercial" in q or "market" in q for q in result)
        assert has_commercial


class TestGeneratePatentQueries:
    def test_returns_queries(self):
        result = generate_patent_queries("Soy Oil", "Construction & Building Materials")
        assert len(result) == 3  # 3 derivative synonyms (Soy Oil, Soybean Oil, Soy Bean Oil)

    def test_derivative_synonym_expansion(self):
        result = generate_patent_queries("Soy Oil", "Construction & Building Materials")
        assert any("soybean oil" in q for q in result)
        assert any("soy bean oil" in q for q in result)
        assert any("adhesive" in q for q in result)  # uses sector keyword


class TestGenerateGovtQueries:
    def test_returns_queries(self):
        result = generate_govt_queries("Soy Oil", "Construction & Building Materials")
        assert len(result) == 4  # 2 templates x 2 synonyms

    def test_contains_research_keyword(self):
        result = generate_govt_queries("Soy Oil", "Construction & Building Materials")
        has_research = any("research" in q for q in result)
        has_biobased = any("biobased" in q for q in result)
        assert has_research
        assert has_biobased


# ---------------------------------------------------------------------------
# generate_full_query_plan
# ---------------------------------------------------------------------------

class TestGenerateFullQueryPlan:
    def test_returns_query_plans(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        assert len(plans) > 0
        assert all(isinstance(p, QueryPlan) for p in plans)

    def test_includes_all_query_types(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        types = {p.query_type for p in plans}
        assert "academic" in types
        assert "semantic" in types
        assert "web" in types
        assert "patent" in types
        assert "govt" in types
        assert "implicit_semantic" in types

    def test_academic_routes_to_tier1(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        academic = [p for p in plans if p.query_type == "academic"]
        for p in academic:
            assert "agris" in p.target_apis, "Academic queries must route to agris"
            assert "openalex" in p.target_apis

    def test_patent_routes_to_patentsview_and_lens(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        patent = [p for p in plans if p.query_type == "patent"]
        assert len(patent) > 0
        for p in patent:
            assert "patentsview" in p.target_apis
            assert "lens" in p.target_apis

    def test_govt_routes_to_osti_sbir_usda(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        govt = [p for p in plans if p.query_type == "govt"]
        assert len(govt) > 0
        for p in govt:
            assert "osti" in p.target_apis
            assert "sbir" in p.target_apis
            assert "usda_ers" in p.target_apis

    def test_implicit_semantic_queries_included(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        implicit = [p for p in plans if p.query_type == "implicit_semantic"]
        assert len(implicit) == len(SEMANTIC_QUERIES)
        for p in implicit:
            assert p.derivative is None
            assert p.sector is None
            assert "exa" in p.target_apis

    def test_time_windows_applied(self):
        plans = generate_full_query_plan(time_windows=[(2020, 2026)])
        academic = [p for p in plans if p.query_type == "academic"]
        for p in academic:
            assert p.year_start == 2020
            assert p.year_end == 2026


# ---------------------------------------------------------------------------
# generate_refresh_queries
# ---------------------------------------------------------------------------

class TestGenerateRefreshQueries:
    def test_returns_query_plans(self):
        plans = generate_refresh_queries(since_year=2024)
        assert len(plans) > 0

    def test_includes_all_query_types(self):
        plans = generate_refresh_queries(since_year=2024)
        types = {p.query_type for p in plans}
        assert "academic" in types
        assert "web" in types
        assert "patent" in types
        assert "govt" in types
        assert "implicit_semantic" in types

    def test_year_range_set(self):
        plans = generate_refresh_queries(since_year=2024)
        for p in plans:
            if p.year_start is not None:
                assert p.year_start == 2024
                assert p.year_end == 2026

    def test_lighter_than_full_build(self):
        full = generate_full_query_plan(time_windows=[(2020, 2026)])
        refresh = generate_refresh_queries(since_year=2020)
        assert len(refresh) < len(full), "Refresh should be lighter than full build"

    def test_tier1_routing_in_refresh(self):
        plans = generate_refresh_queries(since_year=2024)
        academic = [p for p in plans if p.query_type == "academic"]
        for p in academic:
            assert "agris" in p.target_apis
        patent = [p for p in plans if p.query_type == "patent"]
        for p in patent:
            assert "patentsview" in p.target_apis


# ---------------------------------------------------------------------------
# API routing constants
# ---------------------------------------------------------------------------

class TestAPIRoutingConstants:
    def test_academic_tier1_includes_agris(self):
        assert "agris" in _ACADEMIC_APIS_TIER1
        assert "openalex" in _ACADEMIC_APIS_TIER1
        assert "semantic_scholar" in _ACADEMIC_APIS_TIER1
        assert "pubmed" in _ACADEMIC_APIS_TIER1
        assert "crossref" in _ACADEMIC_APIS_TIER1

    def test_patent_apis(self):
        assert "patentsview" in _PATENT_APIS
        assert "lens" in _PATENT_APIS

    def test_govt_report_apis(self):
        assert "osti" in _GOVT_REPORT_APIS
        assert "sbir" in _GOVT_REPORT_APIS
        assert "usda_ers" in _GOVT_REPORT_APIS

    def test_semantic_apis(self):
        assert "exa" in _SEMANTIC_APIS

    def test_web_apis(self):
        assert "tavily" in _WEB_APIS

