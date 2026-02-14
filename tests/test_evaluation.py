"""Tests for relevance benchmark evaluation utilities."""

from soyscope.evaluation import evaluate_labeled_findings, normalize_novelty_score


def test_normalize_novelty_score_handles_both_scales():
    assert normalize_novelty_score(0.82) == 0.82
    assert normalize_novelty_score(82) == 0.82
    assert normalize_novelty_score(None) is None


def test_evaluate_labeled_findings_metrics():
    rows = [
        {"label": "relevant", "novelty_score": 0.90},   # TP
        {"label": "irrelevant", "novelty_score": 0.90}, # FP
        {"label": "relevant", "novelty_score": 0.20},   # FN
        {"label": "irrelevant", "novelty_score": 0.20}, # TN
    ]
    metrics = evaluate_labeled_findings(rows, threshold=0.7)
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["tn"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["accuracy"] == 0.5


def test_evaluate_labeled_findings_coverage():
    rows = [
        {"label": "relevant", "novelty_score": None},
        {"label": "irrelevant", "novelty_score": 50},  # 0.50 after normalization
    ]
    metrics = evaluate_labeled_findings(rows, threshold=0.7)
    assert metrics["evaluated_rows"] == 2
    assert metrics["rows_with_novelty"] == 1
    assert metrics["novelty_coverage"] == 0.5
