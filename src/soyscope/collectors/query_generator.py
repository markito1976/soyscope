"""Systematic query generation (derivative x sector x year)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default seed taxonomy
DEFAULT_DERIVATIVES = [
    "Soy Oil",
    "Soy Protein",
    "Soy Meal",
    "Soy Lecithin",
    "Soy Fiber",
    "Soy Wax",
    "Soy Hulls",
    "Soybean Hulls",
    "Soy-based Polyols",
    "Soy Isoflavones",
    "Soy Fatty Acids",
    "Glycerol soy-derived",
    "Soy-based Resins",
    "Whole Soybean",
]

DEFAULT_SECTORS = [
    "Construction & Building Materials",
    "Automotive & Transportation",
    "Packaging & Containers",
    "Textiles & Fibers",
    "Coatings, Paints & Inks",
    "Adhesives & Sealants",
    "Plastics & Bioplastics",
    "Lubricants & Metalworking Fluids",
    "Energy & Biofuels",
    "Chemicals & Solvents",
    "Personal Care & Cosmetics",
    "Cleaning Products & Surfactants",
    "Agriculture",
    "Electronics",
    "Firefighting Foam",
    "Rubber & Elastomers",
]

# Sector-specific keywords for more targeted queries
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Construction & Building Materials": ["adhesive", "insulation", "composite", "concrete", "plywood", "particleboard"],
    "Automotive & Transportation": ["lubricant", "tire", "foam", "composite", "seat cushion", "polyurethane"],
    "Packaging & Containers": ["film", "coating", "foam peanut", "biodegradable packaging", "container"],
    "Textiles & Fibers": ["fiber", "fabric", "textile", "yarn", "nonwoven"],
    "Coatings, Paints & Inks": ["alkyd resin", "printing ink", "paint", "varnish", "protective coating"],
    "Adhesives & Sealants": ["adhesive", "sealant", "glue", "binder", "bonding agent"],
    "Plastics & Bioplastics": ["PLA", "polyurethane", "bioplastic", "biodegradable plastic", "polymer"],
    "Lubricants & Metalworking Fluids": ["lubricant", "hydraulic fluid", "metalworking", "grease", "cutting fluid"],
    "Energy & Biofuels": ["biodiesel", "bio-jet fuel", "renewable diesel", "bioenergy", "transesterification"],
    "Chemicals & Solvents": ["green chemistry", "solvent", "surfactant", "chemical intermediate", "oleochemical"],
    "Personal Care & Cosmetics": ["moisturizer", "emollient", "cosmetic", "skin care", "hair care"],
    "Cleaning Products & Surfactants": ["detergent", "cleaner", "surfactant", "soap", "degreaser"],
    "Agriculture": ["biopesticide", "seed coating", "adjuvant", "soil amendment", "crop protection"],
    "Electronics": ["circuit board", "dielectric fluid", "electronic", "transformer oil", "PCB"],
    "Firefighting Foam": ["PFAS replacement", "AFFF alternative", "firefighting", "fire suppression", "fluorine-free"],
    "Rubber & Elastomers": ["rubber", "elastomer", "tire compound", "vulcanization", "bio-rubber"],
}

TIME_WINDOWS = [(2000, 2004), (2005, 2009), (2010, 2014), (2015, 2019), (2020, 2026)]


@dataclass
class QueryPlan:
    """A planned search query."""
    query: str
    derivative: str | None = None
    sector: str | None = None
    year_start: int | None = None
    year_end: int | None = None
    query_type: str = "academic"  # academic, semantic, web, patent
    target_apis: list[str] = field(default_factory=list)


def load_taxonomy(taxonomy_path: Path | None = None) -> tuple[list[str], list[str]]:
    """Load derivatives and sectors from taxonomy.json or use defaults."""
    if taxonomy_path and taxonomy_path.exists():
        with open(taxonomy_path) as f:
            data = json.load(f)
        return data.get("derivatives", DEFAULT_DERIVATIVES), data.get("sectors", DEFAULT_SECTORS)
    return DEFAULT_DERIVATIVES, DEFAULT_SECTORS


def generate_academic_queries(derivative: str, sector: str) -> list[str]:
    """Generate academic search queries for a derivative-sector pair."""
    queries = [
        f'"{derivative}" AND "{sector}"',
        f'"soy-based" AND "{sector}"',
        f'"soybean" AND "{sector.split(" & ")[0].split(",")[0].lower()}"',
    ]
    # Add keyword-specific queries
    keywords = SECTOR_KEYWORDS.get(sector, [])
    if keywords:
        queries.append(f'"{derivative}" AND ("{keywords[0]}" OR "{keywords[1] if len(keywords) > 1 else keywords[0]}")')
    return queries


def generate_semantic_queries(derivative: str, sector: str) -> list[str]:
    """Generate EXA-style semantic/conceptual queries."""
    sector_short = sector.split(" & ")[0].split(",")[0]
    return [
        f"soybean {derivative.lower()} used as alternative in {sector_short.lower()}",
        f"bio-based {sector_short.lower()} product from soy replacing petroleum",
    ]


def generate_web_queries(derivative: str, sector: str) -> list[str]:
    """Generate web/industry search queries for Tavily."""
    sector_short = sector.split(" & ")[0].split(",")[0]
    return [
        f"soy-based {sector_short.lower()} product commercial market",
        f"soybean {derivative.lower()} industrial application report",
    ]


def generate_patent_queries(derivative: str, sector: str) -> list[str]:
    """Generate patent-focused queries."""
    sector_short = sector.split(" & ")[0].split(",")[0]
    return [
        f'patent soybean {derivative.lower()} {sector_short.lower()}',
    ]


def generate_full_query_plan(
    taxonomy_path: Path | None = None,
    time_windows: list[tuple[int, int]] | None = None,
) -> list[QueryPlan]:
    """Generate the complete query plan for historical build.

    Returns ~4,400 queries across all derivative x sector x time window combinations.
    """
    derivatives, sectors = load_taxonomy(taxonomy_path)
    windows = time_windows or TIME_WINDOWS
    plans: list[QueryPlan] = []

    for derivative in derivatives:
        for sector in sectors:
            for year_start, year_end in windows:
                # Academic queries (OpenAlex, Semantic Scholar, PubMed, Crossref)
                for q in generate_academic_queries(derivative, sector):
                    plans.append(QueryPlan(
                        query=q,
                        derivative=derivative,
                        sector=sector,
                        year_start=year_start,
                        year_end=year_end,
                        query_type="academic",
                        target_apis=["openalex", "semantic_scholar", "pubmed", "crossref"],
                    ))

            # Semantic queries (EXA) - one per combo, no time split needed
            for q in generate_semantic_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="semantic",
                    target_apis=["exa"],
                ))

            # Web queries (Tavily) - one per combo
            for q in generate_web_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="web",
                    target_apis=["tavily"],
                ))

            # Patent queries (EXA + Tavily) - one per combo
            for q in generate_patent_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="patent",
                    target_apis=["exa", "tavily"],
                ))

    logger.info(f"Generated {len(plans)} queries for {len(derivatives)} derivatives x {len(sectors)} sectors")
    return plans


def generate_refresh_queries(
    since_year: int,
    taxonomy_path: Path | None = None,
) -> list[QueryPlan]:
    """Generate queries for incremental refresh since a given year."""
    derivatives, sectors = load_taxonomy(taxonomy_path)
    plans: list[QueryPlan] = []
    current_year = 2026

    for derivative in derivatives:
        for sector in sectors:
            for q in generate_academic_queries(derivative, sector)[:2]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="academic",
                    target_apis=["openalex", "semantic_scholar"],
                ))

            for q in generate_web_queries(derivative, sector)[:1]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="web",
                    target_apis=["tavily"],
                ))

    logger.info(f"Generated {len(plans)} refresh queries since {since_year}")
    return plans
