"""Threshold/metric helpers (no torch needed)."""

from __future__ import annotations

import math
from pathlib import Path

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


def test_manifest_paths_are_relative_and_resolve(tmp_path):
    from ml.common import read_manifest, write_manifest
    from ml.split_dataset import from_raw

    raw = tmp_path / "raw" / "SKU"
    for label, cans in (("ok", ["c001", "c002", "c003", "c004", "c005"]), ("ng", ["c101", "c102"])):
        (raw / label).mkdir(parents=True)
        for c in cans:
            (raw / label / f"{c}_1.jpg").write_bytes(b"")
    rows = from_raw(raw, 42, (0.6, 0.2, 0.2), 0.5)
    assert all(not r.path.startswith("/") and "\\" not in r.path for r in rows)
    assert {r.path.split("/")[0] for r in rows} == {"ok", "ng"}

    m = tmp_path / "m.csv"
    write_manifest(m, rows)
    moved = tmp_path / "elsewhere"
    raw.rename(moved)  # same manifest, data in a different place
    resolved = read_manifest(m, moved)
    # compare as Paths: the manifest always uses "/", the OS separator may differ (Windows uses "\")
    assert [Path(r.path) for r in resolved] == [moved / r.path for r in rows]
    assert all(Path(r.path).exists() for r in resolved)

    import pytest
    with pytest.raises(SystemExit):
        read_manifest(m)  # relative paths need --data-root


def test_absolute_manifest_paths_still_work(tmp_path):
    from ml.common import Row, read_manifest, write_manifest

    m = tmp_path / "m.csv"
    absolute = str(tmp_path / "abs" / "a.jpg")  # a real absolute path on this OS ("/abs" has no drive on Windows)
    write_manifest(m, [Row(absolute, "train", "ok", "g1")])
    assert read_manifest(m)[0].path == absolute
