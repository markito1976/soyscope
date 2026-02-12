"""Reciprocal Rank Fusion merging of results from multiple APIs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .dedup import normalize_doi, normalize_title
from .models import Paper


def reciprocal_rank_fusion(
    ranked_lists: list[list[Paper]],
    k: int = 60,
) -> list[Paper]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion (RRF).

    Each paper gets a score of sum(1 / (k + rank_i)) across all lists.
    Higher scores = more consistently ranked across sources.

    Args:
        ranked_lists: List of ranked result lists (one per API source).
        k: RRF constant (default 60, per original paper).

    Returns:
        Merged list sorted by RRF score descending.
    """
    # Score accumulator: key -> (rrf_score, best_paper)
    scores: dict[str, float] = defaultdict(float)
    papers: dict[str, Paper] = {}

    for result_list in ranked_lists:
        for rank, paper in enumerate(result_list):
            key = _paper_key(paper)
            rrf_score = 1.0 / (k + rank + 1)
            scores[key] += rrf_score

            # Keep the version with the most metadata
            if key not in papers or _richness(paper) > _richness(papers[key]):
                papers[key] = paper

    # Sort by RRF score
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [papers[k] for k in sorted_keys]


def _paper_key(paper: Paper) -> str:
    """Generate a deduplication key for a paper."""
    ndoi = normalize_doi(paper.doi)
    if ndoi:
        return f"doi:{ndoi}"
    return f"title:{normalize_title(paper.title)}"


def _richness(paper: Paper) -> int:
    """Score how much metadata a paper has (more = richer)."""
    score = 0
    if paper.abstract:
        score += 3
    if paper.doi:
        score += 2
    if paper.year:
        score += 1
    if paper.authors:
        score += 1
    if paper.venue:
        score += 1
    if paper.pdf_url:
        score += 1
    if paper.citation_count is not None:
        score += 1
    if paper.url:
        score += 1
    return score
