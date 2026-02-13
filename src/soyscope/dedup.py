"""DOI-first + fuzzy title deduplication."""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from .models import Paper


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI for comparison."""
    if not doi:
        return None
    doi = doi.strip().lower()
    # Remove common URL prefixes
    for prefix in ["https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)  # Remove punctuation
    t = re.sub(r"\s+", " ", t)     # Collapse whitespace
    return t


def is_duplicate_title(title_a: str, title_b: str, threshold: float = 90.0) -> bool:
    """Check if two titles are duplicates using fuzzy matching."""
    na = normalize_title(title_a)
    nb = normalize_title(title_b)
    return fuzz.ratio(na, nb) >= threshold


class Deduplicator:
    """Deduplicates papers using DOI-first, then fuzzy title matching."""

    def __init__(self, title_threshold: float = 90.0) -> None:
        self.title_threshold = title_threshold
        self._seen_dois: set[str] = set()
        self._doi_to_id: dict[str, int | None] = {}
        self._seen_titles: list[tuple[int | None, str]] = []

    def load_existing(self, dois: set[str], titles: list[tuple[int, str]],
                      doi_to_id: dict[str, int] | None = None) -> None:
        """Load existing DOIs and titles from the database."""
        self._seen_dois = {normalize_doi(d) for d in dois if d} - {None}
        self._seen_titles = [(tid, normalize_title(t)) for tid, t in titles if t]
        if doi_to_id:
            for doi, fid in doi_to_id.items():
                nd = normalize_doi(doi)
                if nd:
                    self._doi_to_id[nd] = fid

    def is_duplicate(self, paper: Paper) -> tuple[bool, int | None]:
        """Check if a paper is a duplicate.

        Returns (is_dup, existing_id).
        existing_id is set if we matched an existing DB record.
        """
        # 1. DOI match (exact)
        ndoi = normalize_doi(paper.doi)
        if ndoi and ndoi in self._seen_dois:
            return True, self._doi_to_id.get(ndoi)

        # 2. Fuzzy title match
        if paper.title:
            nt = normalize_title(paper.title)
            for existing_id, existing_title in self._seen_titles:
                if fuzz.ratio(nt, existing_title) >= self.title_threshold:
                    return True, existing_id

        return False, None

    def register(self, paper: Paper, db_id: int | None = None) -> None:
        """Register a paper as seen."""
        ndoi = normalize_doi(paper.doi)
        if ndoi:
            self._seen_dois.add(ndoi)
            self._doi_to_id[ndoi] = db_id
        if paper.title:
            self._seen_titles.append((db_id, normalize_title(paper.title)))


def deduplicate_papers(papers: list[Paper], existing_dois: set[str] | None = None,
                       existing_titles: list[tuple[int, str]] | None = None,
                       title_threshold: float = 90.0) -> list[Paper]:
    """Deduplicate a list of papers.

    Returns only the unique papers (not seen in existing or in the batch).
    """
    dedup = Deduplicator(title_threshold=title_threshold)
    if existing_dois:
        dedup.load_existing(existing_dois, existing_titles or [])

    unique: list[Paper] = []
    for paper in papers:
        is_dup, _ = dedup.is_duplicate(paper)
        if not is_dup:
            dedup.register(paper)
            unique.append(paper)

    return unique
