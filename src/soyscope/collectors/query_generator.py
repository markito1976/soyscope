"""Systematic query generation (derivative x sector x year).

Supports synonym expansion, semantic/conceptual queries for implicit
industrial relevance, and Tier 1 source routing (patents -> patentsview/lens,
government -> osti/sbir/usda_ers, academic -> agris/lens alongside originals).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Soy synonym expansion
# ---------------------------------------------------------------------------

SOY_SYNONYMS: list[str] = ["soy", "soybean", "soy bean", "soya", "soja"]
"""Every search that mentions soy should automatically produce variants
using each of these synonyms so we catch all spellings worldwide."""


def expand_soy_synonyms(template: str) -> list[str]:
    """Expand a query template containing ``{soy}`` into N queries.

    The placeholder ``{soy}`` in *template* is replaced with each entry
    in :data:`SOY_SYNONYMS`.

    If the template does not contain the placeholder, it is returned
    unchanged (as a single-element list).
    """
    if "{soy}" not in template:
        return [template]
    return [template.replace("{soy}", syn) for syn in SOY_SYNONYMS]


# ---------------------------------------------------------------------------
# Default seed taxonomy
# ---------------------------------------------------------------------------

DEFAULT_DERIVATIVES = [
    "Soy Oil",
    "Soy Protein",
    "Soy Meal",
    "Soy Lecithin",
    "Soy Fiber",
    "Soy Wax",
    "Soy Hulls",
    "Soy-based Polyols",
    "Soy Isoflavones",
    "Soy Fatty Acids",
    "Glycerol soy-derived",
    "Soy-based Resins",
    "Whole Soybean",
    "Methyl Soyate",
    "Epoxidized Soybean Oil",
    "Phytosterols",
    "Azelaic Acid",
    "Dimer Fatty Acids",
    "Soy Molasses",
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
    "Pharmaceuticals & Medical",
    "Candles & Home Products",
    "Paper & Printing",
]

# Sector-specific keywords for more targeted queries
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Construction & Building Materials": [
        "adhesive", "insulation", "composite", "concrete", "plywood", "particleboard",
        "oriented strand board", "OSB", "structural panel", "spray foam", "rigid foam",
        "PoreShield", "asphalt rejuvenator", "recycled asphalt pavement", "dust suppressant",
        "concrete sealant", "SME-PS", "wood panel", "structural adhesive", "subfloor adhesive",
        "foundation coating", "roof insulation", "building envelope",
    ],
    "Automotive & Transportation": [
        "lubricant", "tire", "foam", "composite", "seat cushion", "polyurethane",
        "engine oil", "biodiesel fleet", "soy foam headliner", "door panel", "armrest",
        "trunk liner", "instrument panel", "seating foam", "headrest", "steering wheel",
        "gasket", "underbody coating", "rust prevention", "cargo bed liner",
    ],
    "Packaging & Containers": [
        "film", "coating", "foam peanut", "biodegradable packaging", "container",
        "loose-fill", "molded packaging", "food packaging", "barrier film",
        "compostable tray", "cushioning", "void fill", "protective packaging",
        "paper cup coating", "takeout container", "clamshell", "blister pack",
    ],
    "Textiles & Fibers": [
        "fiber", "fabric", "textile", "yarn", "nonwoven", "spinning",
        "SPF fiber", "soy silk", "cellulose blend", "knit fabric", "woven textile",
        "antimicrobial fiber", "moisture wicking", "sustainable textile", "regenerated fiber",
        "natural fiber composite", "biofiber", "fiber reinforcement",
    ],
    "Coatings, Paints & Inks": [
        "alkyd resin", "printing ink", "paint", "varnish", "protective coating",
        "soy ink", "SoySeal", "lithographic ink", "flexographic ink", "wood finish",
        "floor coating", "industrial coating", "architectural coating", "primer",
        "stain", "sealant coating", "two-component coating", "UV-curable coating",
        "waterborne coating", "acrylated epoxidized soybean oil", "AESO",
    ],
    "Adhesives & Sealants": [
        "adhesive", "sealant", "glue", "binder", "bonding agent",
        "PureBond", "formaldehyde-free", "PAE crosslinker", "Soyad",
        "wood panel adhesive", "plywood adhesive", "laminating adhesive",
        "hot melt adhesive", "pressure sensitive adhesive", "construction adhesive",
        "structural adhesive", "wood glue", "bio-adhesive", "protein adhesive",
    ],
    "Plastics & Bioplastics": [
        "PLA", "polyurethane", "bioplastic", "biodegradable plastic", "polymer",
        "injection molding", "thermoset", "thermoplastic", "BiOH polyol",
        "flexible foam", "rigid foam", "reaction injection molding", "RIM",
        "soy polyol", "bio-polyol", "green polyurethane", "biobased content",
        "USDA BioPreferred", "compostable plastic", "soy-filled composite",
    ],
    "Lubricants & Metalworking Fluids": [
        "lubricant", "hydraulic fluid", "metalworking", "grease", "cutting fluid",
        "FR3", "Envirotemp", "natural ester", "dielectric fluid", "transformer fluid",
        "estolide", "chainsaw bar oil", "rail flange lubricant", "gear oil",
        "compressor oil", "two-cycle engine oil", "penetrating oil", "mold release",
        "quenchant", "slideway lubricant", "total loss lubricant",
    ],
    "Energy & Biofuels": [
        "biodiesel", "bio-jet fuel", "renewable diesel", "bioenergy", "transesterification",
        "FAME", "B20", "B100", "sustainable aviation fuel", "SAF", "HEFA",
        "biomass-based diesel", "RFS", "renewable identification number", "RIN",
        "co-processing", "hydrotreating", "glycerin byproduct", "biorefinery",
        "drop-in fuel", "blending mandate",
    ],
    "Chemicals & Solvents": [
        "green chemistry", "solvent", "surfactant", "chemical intermediate", "oleochemical",
        "methyl soyate", "soy methyl ester", "d-limonene alternative", "paint stripper",
        "parts washer", "degreaser", "asphalt release agent", "ink cleanser",
        "VOC-free solvent", "bio-solvent", "fatty acid derivative", "diacid",
        "platform chemical", "succinic acid", "azelaic acid",
    ],
    "Personal Care & Cosmetics": [
        "moisturizer", "emollient", "cosmetic", "skin care", "hair care",
        "lip balm", "body lotion", "shampoo", "conditioner", "tocopherol",
        "vitamin E", "squalane", "anti-aging", "barrier repair", "sun care",
        "soap base", "cleansing oil", "makeup remover", "nail polish remover",
    ],
    "Cleaning Products & Surfactants": [
        "detergent", "cleaner", "surfactant", "soap", "degreaser",
        "laundry detergent", "dish soap", "all-purpose cleaner", "industrial cleaner",
        "floor cleaner", "hand cleaner", "waterless hand cleaner", "emulsifier",
        "wetting agent", "methyl ester sulfonate", "MES", "alkyl polyglucoside",
    ],
    "Agriculture": [
        "biopesticide", "seed coating", "adjuvant", "soil amendment", "crop protection",
        "spray adjuvant", "drift retardant", "crop oil concentrate", "COC",
        "methylated seed oil", "MSO", "surfactant adjuvant", "anti-foam",
        "dust control", "livestock feed supplement", "aquaculture feed",
        "greenhouse film", "mulch film", "controlled release fertilizer",
    ],
    "Electronics": [
        "circuit board", "dielectric fluid", "electronic", "transformer oil", "PCB",
        "semiconductor", "Envirotemp FR3", "natural ester transformer", "capacitor fluid",
        "conformal coating", "potting compound", "encapsulant", "flexible circuit",
        "bio-based PCB", "solder flux", "thermal interface material",
    ],
    "Firefighting Foam": [
        "PFAS replacement", "AFFF alternative", "firefighting", "fire suppression", "fluorine-free",
        "foam concentrate", "Class B foam", "protein foam", "AR-AFFF", "film-forming foam",
        "aqueous film", "foam blanket", "crash rescue", "military specification",
        "MIL-PRF", "environmental remediation", "PFAS-free",
    ],
    "Rubber & Elastomers": [
        "rubber", "elastomer", "tire compound", "vulcanization", "bio-rubber",
        "soy tire", "processing oil replacement", "silica-reinforced",
        "glass transition", "abrasion resistance", "rolling resistance",
        "wet traction", "tread compound", "sidewall compound", "TDAE replacement",
        "aromatic oil alternative", "Goodyear Assurance", "bio-based rubber",
    ],
    "Pharmaceuticals & Medical": [
        "parenteral nutrition", "IV emulsion", "liposome", "drug delivery", "phytosterol",
        "steroid synthesis", "excipient", "Intralipid", "phospholipid", "nanoparticle drug",
        "lipid nanoparticle", "soy lecithin injection", "nutraceutical", "dietary supplement",
        "hormone precursor", "progesterone", "cortisone", "vitamin carrier",
        "wound dressing", "tissue engineering",
    ],
    "Candles & Home Products": [
        "candle", "soy wax candle", "wax melt", "home fragrance", "NatureWax",
        "container candle", "pillar candle", "wax coating", "candle wax",
        "scented candle", "votive", "tealight", "aromatherapy",
        "reed diffuser", "wax tart", "candle making", "fragrance oil",
    ],
    "Paper & Printing": [
        "paper coating", "printing ink", "soy ink", "SoySeal", "wet-strength",
        "barrier coating", "de-inking", "corrugated board", "paper binder",
        "sizing agent", "paper laminate", "newsprint ink", "offset ink",
        "heatset ink", "vegetable oil ink", "paper surface treatment",
    ],
}

_CURRENT_YEAR = datetime.now().year
TIME_WINDOWS = [(2000, 2004), (2005, 2009), (2010, 2014), (2015, 2019), (2020, _CURRENT_YEAR)]

# ---------------------------------------------------------------------------
# Semantic / conceptual queries for *implicit* industrial relevance
# ---------------------------------------------------------------------------

SEMANTIC_QUERIES: list[str] = [
    # Foams & polyols
    "polyurethane foam plant-derived polyol",
    "vegetable oil polyol rigid foam insulation",
    "bio-polyol synthesis from triglyceride epoxidation",
    # Adhesives
    "bio-based adhesive oilseed protein wood composite",
    "protein-based wood adhesive formaldehyde replacement",
    # Fuels
    "biodiesel feedstock oil extraction transesterification",
    "renewable diesel hydrotreating vegetable oil",
    # Composites
    "natural fiber reinforced composite mechanical properties",
    "plant fiber thermoplastic composite injection molding",
    # Protein & functional materials
    "plant protein isolate functional properties film formation",
    "oilseed protein hydrogel biomedical scaffold",
    # Coatings & resins
    "vegetable oil epoxidation coating corrosion protection",
    "alkyd resin renewable drying oil formulation",
    "bio-based epoxy curing agent amine fatty acid",
    # Lubricants
    "bio-lubricant renewable base stock oxidative stability",
    "vegetable oil hydraulic fluid tribological performance",
    # Plastics & bioplastics
    "thermoplastic starch protein blend biodegradable packaging",
    "polylactic acid oilseed plasticizer flexibility",
    # Surfactants & chemicals
    "fatty acid methyl ester green solvent cleaning",
    "lecithin phospholipid emulsifier industrial application",
    # Rubber
    "bio-based rubber processing oil silica reinforcement",
    "epoxidized vegetable oil plasticizer PVC replacement",
    # Emerging / novel
    "nanocellulose oilseed residue composite barrier film",
    "carbon dot synthesis from agricultural waste biomass",
    "fermentation platform chemical succinic acid oilseed meal",
]
"""Queries designed to discover papers about soy applications that never
mention soy or soybean explicitly -- they target the technology
and chemistry rather than the crop name."""

# ---------------------------------------------------------------------------
# Target API routing helpers
# ---------------------------------------------------------------------------

# Core academic sources (original 8 minus Unpaywall which is a resolver)
_ACADEMIC_APIS = ["openalex", "semantic_scholar", "pubmed", "crossref"]
_ACADEMIC_APIS_TIER1 = ["openalex", "semantic_scholar", "pubmed", "crossref", "agris"]
_ACADEMIC_APIS_WITH_LENS = ["openalex", "semantic_scholar", "pubmed", "crossref", "agris", "lens"]

_SEMANTIC_APIS = ["exa"]

_WEB_APIS = ["tavily"]

_PATENT_APIS = ["patentsview", "lens"]
_PATENT_APIS_FALLBACK = ["exa", "tavily"]  # when dedicated patent APIs unavailable

_GOVT_REPORT_APIS = ["osti", "sbir", "usda_ers"]


# ---------------------------------------------------------------------------
# Query plan data structure
# ---------------------------------------------------------------------------

@dataclass
class QueryPlan:
    """A planned search query."""
    query: str
    derivative: str | None = None
    sector: str | None = None
    year_start: int | None = None
    year_end: int | None = None
    query_type: str = "academic"  # academic, semantic, web, patent, govt, implicit_semantic
    target_apis: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Taxonomy loader
# ---------------------------------------------------------------------------

def load_taxonomy(taxonomy_path: Path | None = None) -> tuple[list[str], list[str]]:
    """Load derivatives and sectors from taxonomy.json or use defaults."""
    if taxonomy_path and taxonomy_path.exists():
        with open(taxonomy_path) as f:
            data = json.load(f)
        return data.get("derivatives", DEFAULT_DERIVATIVES), data.get("sectors", DEFAULT_SECTORS)
    return DEFAULT_DERIVATIVES, DEFAULT_SECTORS


# ---------------------------------------------------------------------------
# Query generators (per type)
# ---------------------------------------------------------------------------

def generate_academic_queries(derivative: str, sector: str) -> list[str]:
    """Generate academic search queries for a derivative-sector pair.

    Every query forces soy relevance by including the derivative name
    (which contains a soy term) paired with sector **keywords** rather
    than full sector names (which can match journal titles in Crossref).
    """
    keywords = SECTOR_KEYWORDS.get(sector, [])
    if not keywords:
        # Fallback: use first word of sector as keyword
        keywords = [sector.split(" & ")[0].split(",")[0].lower()]

    queries: list[str] = []

    # Query 1: derivative + first 2 keywords (most targeted)
    kw_pair = " OR ".join(f'"{k}"' for k in keywords[:2])
    queries.append(f'"{derivative}" AND ({kw_pair})')

    # Query 2: derivative + next 2 keywords (broader coverage)
    if len(keywords) > 2:
        kw_pair2 = " OR ".join(f'"{k}"' for k in keywords[2:4])
        queries.append(f'"{derivative}" AND ({kw_pair2})')

    # Query 3: synonym expansion with keywords (catches soy/soybean/soja variants)
    kw_first = keywords[0]
    for syn in SOY_SYNONYMS[:3]:  # soy, soybean, soy bean
        queries.append(f'"{syn}" AND "{derivative.split()[-1].lower()}" AND "{kw_first}"')

    return queries


def generate_semantic_queries(derivative: str, sector: str) -> list[str]:
    """Generate EXA-style semantic/conceptual queries."""
    keywords = SECTOR_KEYWORDS.get(sector, [])
    kw = keywords[0] if keywords else sector.split(" & ")[0].split(",")[0].lower()
    queries: list[str] = []
    for syn in SOY_SYNONYMS[:2]:
        queries.append(f"{syn} {derivative.lower()} used as alternative {kw}")
        queries.append(f"bio-based {kw} product from {syn} replacing petroleum")
    return queries


def generate_web_queries(derivative: str, sector: str) -> list[str]:
    """Generate web/industry search queries for Tavily."""
    keywords = SECTOR_KEYWORDS.get(sector, [])
    kw = keywords[0] if keywords else sector.split(" & ")[0].split(",")[0].lower()
    queries: list[str] = []
    for syn in SOY_SYNONYMS[:2]:
        queries.append(f"{syn}-based {kw} product commercial market")
        queries.append(f"{syn} {derivative.lower()} industrial application report")
    return queries


def _derivative_synonyms(derivative: str) -> list[str]:
    """Generate synonym variants of a derivative name.

    E.g. "Soy Oil" -> ["Soy Oil", "Soybean Oil", "Soy Bean Oil"]
    """
    variants = [derivative]
    lower = derivative.lower()
    if lower.startswith("soy "):
        variants.append("Soybean " + derivative[4:])
        variants.append("Soy Bean " + derivative[4:])
    elif lower.startswith("soy-"):
        variants.append("Soybean-" + derivative[4:])
        variants.append("Soy Bean-" + derivative[4:])
    return variants


def generate_patent_queries(derivative: str, sector: str) -> list[str]:
    """Generate patent-focused queries for PatentsView and Lens."""
    keywords = SECTOR_KEYWORDS.get(sector, [])
    kw = keywords[0] if keywords else sector.split(" & ")[0].split(",")[0].lower()
    queries: list[str] = []
    for dv in _derivative_synonyms(derivative):
        queries.append(f"{dv.lower()} {kw}")
    return queries


def generate_govt_queries(derivative: str, sector: str) -> list[str]:
    """Generate government report / grant queries for OSTI, SBIR, USDA ERS."""
    keywords = SECTOR_KEYWORDS.get(sector, [])
    kw = keywords[0] if keywords else sector.split(" & ")[0].split(",")[0].lower()
    queries: list[str] = []
    for syn in SOY_SYNONYMS[:2]:  # soy, soybean
        queries.append(f"{syn} {derivative.split()[-1].lower()} {kw} research")
        queries.append(f"{syn} {kw} biobased")
    return queries


# ---------------------------------------------------------------------------
# Full plan builders
# ---------------------------------------------------------------------------

def generate_full_query_plan(
    taxonomy_path: Path | None = None,
    time_windows: list[tuple[int, int]] | None = None,
) -> list[QueryPlan]:
    """Generate the complete query plan for historical build.

    Produces queries across all derivative x sector x time-window
    combinations, with synonym expansion and Tier 1 source routing.
    """
    derivatives, sectors = load_taxonomy(taxonomy_path)
    windows = time_windows or TIME_WINDOWS
    plans: list[QueryPlan] = []

    for derivative in derivatives:
        for sector in sectors:
            for year_start, year_end in windows:
                # Academic queries (original + AGRIS)
                for q in generate_academic_queries(derivative, sector):
                    plans.append(QueryPlan(
                        query=q,
                        derivative=derivative,
                        sector=sector,
                        year_start=year_start,
                        year_end=year_end,
                        query_type="academic",
                        target_apis=_ACADEMIC_APIS_TIER1[:],
                    ))

                # Government report queries (OSTI, SBIR, USDA ERS)
                for q in generate_govt_queries(derivative, sector):
                    plans.append(QueryPlan(
                        query=q,
                        derivative=derivative,
                        sector=sector,
                        year_start=year_start,
                        year_end=year_end,
                        query_type="govt",
                        target_apis=_GOVT_REPORT_APIS[:],
                    ))

            # Semantic queries (EXA) - one per combo, no time split needed
            for q in generate_semantic_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="semantic",
                    target_apis=_SEMANTIC_APIS[:],
                ))

            # Web queries (Tavily) - one per combo
            for q in generate_web_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="web",
                    target_apis=_WEB_APIS[:],
                ))

            # Patent queries (PatentsView + Lens) - one per combo
            for q in generate_patent_queries(derivative, sector):
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    query_type="patent",
                    target_apis=_PATENT_APIS[:],
                ))

    # -- Implicit semantic queries (cross-cutting, no derivative/sector) --
    for q in SEMANTIC_QUERIES:
        plans.append(QueryPlan(
            query=q,
            derivative=None,
            sector=None,
            query_type="implicit_semantic",
            target_apis=["exa", "openalex", "semantic_scholar"],
        ))

    logger.info(
        f"Generated {len(plans)} queries for "
        f"{len(derivatives)} derivatives x {len(sectors)} sectors "
        f"(+{len(SEMANTIC_QUERIES)} implicit semantic queries)"
    )
    return plans


def generate_refresh_queries(
    since_year: int,
    taxonomy_path: Path | None = None,
) -> list[QueryPlan]:
    """Generate queries for incremental refresh since a given year.

    Uses a lighter query set than the full build (fewer synonym variants)
    but still routes to Tier 1 sources.
    """
    derivatives, sectors = load_taxonomy(taxonomy_path)
    plans: list[QueryPlan] = []
    current_year = _CURRENT_YEAR

    for derivative in derivatives:
        for sector in sectors:
            # Academic -- first 4 queries only to keep refresh light
            for q in generate_academic_queries(derivative, sector)[:4]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="academic",
                    target_apis=_ACADEMIC_APIS_TIER1[:],
                ))

            # Web -- first 2
            for q in generate_web_queries(derivative, sector)[:2]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="web",
                    target_apis=_WEB_APIS[:],
                ))

            # Patent -- first 2
            for q in generate_patent_queries(derivative, sector)[:2]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="patent",
                    target_apis=_PATENT_APIS[:],
                ))

            # Government -- first 2
            for q in generate_govt_queries(derivative, sector)[:2]:
                plans.append(QueryPlan(
                    query=q,
                    derivative=derivative,
                    sector=sector,
                    year_start=since_year,
                    year_end=current_year,
                    query_type="govt",
                    target_apis=_GOVT_REPORT_APIS[:],
                ))

    # Implicit semantic queries (always included in refresh)
    for q in SEMANTIC_QUERIES:
        plans.append(QueryPlan(
            query=q,
            derivative=None,
            sector=None,
            year_start=since_year,
            year_end=current_year,
            query_type="implicit_semantic",
            target_apis=["exa", "openalex", "semantic_scholar"],
        ))

    logger.info(f"Generated {len(plans)} refresh queries since {since_year}")
    return plans
