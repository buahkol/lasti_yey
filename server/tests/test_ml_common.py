"""Threshold/metric helpers (no torch needed)."""

from __future__ import annotations

import math

from ml.common import auroc, confusion, pick_threshold
from server.app.services import compute_inspection_status


def test_auroc_perfect_and_random():
    assert auroc([0.1, 0.2, 0.8, 0.9], [False, False, True, True]) == 1.0
    assert auroc([0.5, 0.5, 0.5, 0.5], [False, True, False, True]) == 0.5


def test_pick_threshold_meets_recall_with_best_specificity():
    ok = [0.05, 0.10, 0.20, 0.30, 0.55]
    ng = [0.40, 0.60, 0.70, 0.80, 0.90, 0.95, 0.97, 0.98, 0.99, 1.00]
    scores, labels = ok + ng, [False] * len(ok) + [True] * len(ng)
    thr = pick_threshold(scores, labels, 0.90)
    cm = confusion(scores, labels, thr)
    assert cm["recall"] >= 0.90
    # 9 of 10 NG needed -> threshold just below 0.60, so only the 0.55 OK... stays OK too
    assert 0.55 < thr < 0.60 and cm["specificity"] == 1.0


def test_pick_threshold_full_recall():
    thr = pick_threshold([0.1, 0.2, 0.3], [False, True, True], 1.0)
    assert 0.1 < thr < 0.2


def test_confusion_counts():
    cm = confusion([0.1, 0.9, 0.6, 0.4], [False, True, False, True], 0.5)
    assert (cm["tp"], cm["fn"], cm["tn"], cm["fp"]) == (1, 1, 1, 1)
    assert math.isclose(cm["recall"], 0.5)


def test_inspection_status_rule():
    assert compute_inspection_status("BERJALAN", 100, 0, 0.05) == "HOLD"
    assert compute_inspection_status("DITUTUP", 100, 5, 0.05) == "PASSED"
    assert compute_inspection_status("DITUTUP", 100, 6, 0.05) == "HOLD"
    assert compute_inspection_status("DITUTUP", 0, 0, 0.05) == "HOLD"
