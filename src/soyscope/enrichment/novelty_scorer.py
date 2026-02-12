"""Novelty/impact scoring for findings."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Keywords that suggest novelty/innovation
NOVELTY_KEYWORDS = [
    "novel", "new", "first", "innovative", "breakthrough", "patent",
    "emerging", "promising", "unprecedented", "unique", "pioneering",
    "next-generation", "advanced", "revolutionary", "cutting-edge",
    "proof of concept", "prototype", "pilot", "demonstration",
]

# Keywords that suggest commercial maturity (lower novelty)
MATURITY_KEYWORDS = [
    "established", "commercial", "widely used", "conventional",
    "traditional", "standard", "mature", "commodity", "well-known",
    "mainstream", "common", "routine",
]

# High-value application keywords (boost score)
HIGH_VALUE_KEYWORDS = [
    "PFAS replacement", "PFAS alternative", "fluorine-free",
    "carbon capture", "carbon sequestration", "carbon negative",
    "circular economy", "zero waste", "cradle to cradle",
    "3D printing", "additive manufacturing",
    "nanotechnology", "nanocomposite", "nanocellulose",
    "quantum dot", "semiconductor",
    "battery", "energy storage", "supercapacitor",
    "medical device", "biomedical", "tissue engineering",
    "aerospace", "space", "defense",
]

# Sectors considered more novel for soy applications
NOVEL_SECTORS = {
    "Electronics", "Firefighting Foam", "Aerospace",
    "3D Printing", "Energy Storage", "Medical Devices",
}


def score_novelty(
    title: str,
    abstract: str | None = None,
    year: int | None = None,
    citation_count: int | None = None,
    sectors: list[str] | None = None,
    source_type: str | None = None,
) -> float:
    """Score the novelty of a finding from 0.0 to 1.0.

    Uses a heuristic scoring approach based on:
    - Keyword analysis (novelty vs maturity terms)
    - Recency (newer = potentially more novel)
    - Citation impact
    - Sector novelty
    - Source type

    Args:
        title: Finding title.
        abstract: Finding abstract/summary.
        year: Publication year.
        citation_count: Number of citations.
        sectors: Associated sector names.
        source_type: Type of source (paper, patent, etc.).

    Returns:
        Novelty score between 0.0 and 1.0.
    """
    text = f"{title} {abstract or ''}".lower()
    score = 0.5  # Base score

    # Keyword analysis
    novelty_hits = sum(1 for kw in NOVELTY_KEYWORDS if kw.lower() in text)
    maturity_hits = sum(1 for kw in MATURITY_KEYWORDS if kw.lower() in text)
    high_value_hits = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw.lower() in text)

    score += min(novelty_hits * 0.05, 0.2)
    score -= min(maturity_hits * 0.05, 0.2)
    score += min(high_value_hits * 0.08, 0.25)

    # Recency boost
    if year:
        if year >= 2023:
            score += 0.1
        elif year >= 2020:
            score += 0.05
        elif year < 2010:
            score -= 0.05

    # Citation impact (high citations = validated but not necessarily novel)
    if citation_count is not None:
        if citation_count > 100:
            score += 0.05  # Well-cited = impactful
        elif citation_count == 0 and year and year < 2023:
            score -= 0.05  # Old and uncited = likely less impactful

    # Sector novelty
    if sectors:
        novel_sector_count = sum(1 for s in sectors if s in NOVEL_SECTORS)
        score += min(novel_sector_count * 0.1, 0.15)

    # Patents tend to be more novel
    if source_type == "patent":
        score += 0.1

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, round(score, 3)))


def batch_score_novelty(findings: list[dict[str, Any]]) -> list[tuple[int, float]]:
    """Score novelty for a batch of findings.

    Args:
        findings: List of finding dicts (must have 'id', 'title', optional 'abstract', 'year', etc.)

    Returns:
        List of (finding_id, novelty_score) tuples.
    """
    results = []
    for f in findings:
        score = score_novelty(
            title=f.get("title", ""),
            abstract=f.get("abstract"),
            year=f.get("year"),
            citation_count=f.get("citation_count"),
            source_type=f.get("source_type"),
        )
        results.append((f["id"], score))
    return results
