"""Relevance benchmark utilities for labeled findings."""

from __future__ import annotations

from typing import Any


def normalize_novelty_score(raw_score: Any) -> float | None:
    """Normalize novelty to 0.0-1.0 from either 0-1 or 0-100 scales."""
    if raw_score is None:
        return None

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None

    if score > 1.0:
        score = score / 100.0

    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def predict_relevant_from_novelty(raw_score: Any, threshold: float = 0.7) -> bool:
    """Predict relevance using novelty thresholding."""
    normalized = normalize_novelty_score(raw_score)
    return normalized is not None and normalized >= threshold


def evaluate_labeled_findings(
    rows: list[dict[str, Any]],
    threshold: float = 0.7,
) -> dict[str, float | int]:
    """Evaluate labeled findings against novelty-threshold predictions."""
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")

    tp = fp = fn = tn = 0
    with_novelty = 0
    skipped_labels = 0

    for row in rows:
        label = str(row.get("label", "")).strip().lower()
        if label not in {"relevant", "irrelevant"}:
            skipped_labels += 1
            continue

        truth_relevant = label == "relevant"
        normalized = normalize_novelty_score(row.get("novelty_score"))
        if normalized is not None:
            with_novelty += 1
        pred_relevant = normalized is not None and normalized >= threshold

        if truth_relevant and pred_relevant:
            tp += 1
        elif not truth_relevant and pred_relevant:
            fp += 1
        elif truth_relevant and not pred_relevant:
            fn += 1
        else:
            tn += 1

    evaluated = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / evaluated if evaluated else 0.0
    novelty_coverage = with_novelty / evaluated if evaluated else 0.0

    return {
        "threshold": threshold,
        "total_rows": len(rows),
        "evaluated_rows": evaluated,
        "skipped_labels": skipped_labels,
        "rows_with_novelty": with_novelty,
        "novelty_coverage": novelty_coverage,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }
