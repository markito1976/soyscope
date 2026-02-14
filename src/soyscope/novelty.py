"""Novelty detection — score findings against known commercial soy applications.

A novelty score of 0 means the finding clearly describes a known, commercialized
application.  A score of 100 means no match to any known sector × derivative
combination was found — this is a potentially novel discovery.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NoveltyResult:
    """Result of novelty scoring for a single finding."""
    finding_id: int
    novelty_score: float  # 0-100
    best_match_product: str | None = None
    best_match_sector: str | None = None
    best_match_similarity: float = 0.0
    matched_keywords: list[str] | None = None
    explanation: str = ""


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fuzzy_similarity(a: str, b: str) -> float:
    """Return 0-1 similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _keyword_overlap(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Check how many keywords appear in text. Returns (fraction, matched_list)."""
    if not keywords or not text:
        return 0.0, []
    text_lower = _normalize(text)
    matched = [kw for kw in keywords if kw.lower() in text_lower]
    return len(matched) / len(keywords), matched


def score_finding_novelty(
    finding: dict[str, Any],
    known_apps: list[dict[str, Any]],
    sector_keywords: dict[str, list[str]] | None = None,
) -> NoveltyResult:
    """Score a single finding's novelty against known applications.

    Parameters
    ----------
    finding : dict
        Must have at least 'id', 'title'. May have 'abstract'.
    known_apps : list[dict]
        Rows from the known_applications table.
    sector_keywords : dict, optional
        SECTOR_KEYWORDS from query_generator for additional matching.

    Returns
    -------
    NoveltyResult with score 0 (known) to 100 (novel).
    """
    finding_id = finding.get("id", 0)
    title = finding.get("title", "")
    abstract = finding.get("abstract", "") or ""
    combined_text = f"{title} {abstract}"

    if not title:
        return NoveltyResult(
            finding_id=finding_id,
            novelty_score=50.0,
            explanation="No title available for novelty scoring",
        )

    best_score = 0.0
    best_product = None
    best_sector = None
    all_matched_keywords: list[str] = []

    for app in known_apps:
        app_product = app.get("product_name", "") or ""
        app_manufacturer = app.get("manufacturer", "") or ""
        app_description = app.get("description", "") or ""
        app_sector = app.get("sector", "") or ""
        app_category = app.get("category", "") or ""

        # --- Product name matching (highest weight) ---
        product_sim = 0.0
        if app_product:
            # Check if product name appears directly in text
            if app_product.lower() in combined_text.lower():
                product_sim = 1.0
            else:
                product_sim = _fuzzy_similarity(app_product, title) * 0.7

        # --- Manufacturer matching ---
        mfr_sim = 0.0
        if app_manufacturer:
            if app_manufacturer.lower() in combined_text.lower():
                mfr_sim = 0.5
            else:
                mfr_sim = _fuzzy_similarity(app_manufacturer, combined_text) * 0.3

        # --- Description similarity ---
        desc_sim = _fuzzy_similarity(app_description, title) * 0.6
        if abstract:
            desc_sim = max(desc_sim, _fuzzy_similarity(app_description, abstract) * 0.5)

        # --- Category keyword matching ---
        cat_words = app_category.lower().split()
        cat_overlap = sum(1 for w in cat_words if w in combined_text.lower()) / max(len(cat_words), 1)
        cat_sim = cat_overlap * 0.4

        # Composite similarity for this known app
        app_similarity = max(product_sim, desc_sim) + mfr_sim + cat_sim
        # Normalize to 0-1 range (max possible is ~2.0)
        app_similarity = min(app_similarity / 2.0, 1.0)

        if app_similarity > best_score:
            best_score = app_similarity
            best_product = app_product or app_description[:50]
            best_sector = app_sector

    # --- Sector keyword matching (cross-check) ---
    sector_match_score = 0.0
    if sector_keywords:
        for sector_name, keywords in sector_keywords.items():
            overlap_frac, matched = _keyword_overlap(combined_text, keywords)
            if overlap_frac > sector_match_score:
                sector_match_score = overlap_frac
                all_matched_keywords = matched

        # Sector keyword match contributes up to 0.3 to best_score
        best_score = max(best_score, best_score * 0.7 + sector_match_score * 0.3)

    # Convert similarity to novelty: high similarity = low novelty
    novelty_score = round((1.0 - best_score) * 100, 1)
    novelty_score = max(0.0, min(100.0, novelty_score))

    # Generate explanation
    if novelty_score < 20:
        explanation = f"Strong match to known application: {best_product}"
    elif novelty_score < 40:
        explanation = f"Moderate match to known application in {best_sector}"
    elif novelty_score < 60:
        explanation = f"Weak match to {best_sector or 'known sectors'} — may be a variant"
    elif novelty_score < 80:
        explanation = "Low similarity to known applications — potentially novel"
    else:
        explanation = "No significant match to any known application — high novelty"

    return NoveltyResult(
        finding_id=finding_id,
        novelty_score=novelty_score,
        best_match_product=best_product,
        best_match_sector=best_sector,
        best_match_similarity=round(best_score, 3),
        matched_keywords=all_matched_keywords if all_matched_keywords else None,
        explanation=explanation,
    )


def score_findings_batch(
    findings: list[dict[str, Any]],
    known_apps: list[dict[str, Any]],
    sector_keywords: dict[str, list[str]] | None = None,
) -> list[NoveltyResult]:
    """Score novelty for a batch of findings.

    Parameters
    ----------
    findings : list[dict]
        List of finding dicts from the database.
    known_apps : list[dict]
        All rows from known_applications table.
    sector_keywords : dict, optional
        SECTOR_KEYWORDS dict for additional matching.

    Returns
    -------
    List of NoveltyResult, one per finding.
    """
    results = []
    for finding in findings:
        result = score_finding_novelty(finding, known_apps, sector_keywords)
        results.append(result)

    # Log summary
    if results:
        avg_score = sum(r.novelty_score for r in results) / len(results)
        high_novelty = sum(1 for r in results if r.novelty_score >= 70)
        logger.info(
            f"Novelty scoring: {len(results)} findings, "
            f"avg score {avg_score:.1f}, "
            f"{high_novelty} high-novelty (≥70)"
        )

    return results


def get_novel_findings(
    findings: list[dict[str, Any]],
    known_apps: list[dict[str, Any]],
    threshold: float = 70.0,
    sector_keywords: dict[str, list[str]] | None = None,
) -> list[NoveltyResult]:
    """Return only findings above the novelty threshold.

    Parameters
    ----------
    threshold : float
        Minimum novelty score to include (default 70).

    Returns
    -------
    List of NoveltyResult sorted by novelty_score descending.
    """
    all_results = score_findings_batch(findings, known_apps, sector_keywords)
    novel = [r for r in all_results if r.novelty_score >= threshold]
    novel.sort(key=lambda r: r.novelty_score, reverse=True)
    return novel
