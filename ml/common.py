"""Shared helpers for the offline ML scripts (manifest I/O, scoring, metrics)."""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MANIFEST_FIELDS = ["path", "split", "label", "group", "detail"]


@dataclass
class Row:
    path: str
    split: str  # train | val | test
    label: str  # ok | ng
    group: str  # physical can id (no group appears in two splits)
    detail: str = ""  # e.g. defect type

    @property
    def is_ng(self) -> bool:
        return self.label == "ng"


def read_manifest(path: Path, data_root: Path | None = None) -> list[Row]:
    """Read a manifest; relative image paths are resolved against ``data_root``.

    Manifests store paths relative to the folder given to ``split_dataset``
    (``--raw`` or ``--root``) so the same CSV works on any machine. Absolute
    paths (older manifests) are used as-is.
    """
    with open(path, newline="") as f:
        rows = [Row(**{k: r.get(k, "") for k in MANIFEST_FIELDS}) for r in csv.DictReader(f)]
    for r in rows:
        p = Path(r.path)
        if p.is_absolute():
            continue
        if data_root is None:
            raise SystemExit(
                f"{path} has relative image paths; pass --data-root (the folder given to split_dataset)"
            )
        r.path = str(Path(data_root).expanduser() / p)
    return rows


def write_manifest(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)


def score_rows(model, rows: list[Row], batch_size: int = 8) -> tuple[list[float], list[float]]:
    """Return (raw scores, per-image latency ms) for each row, batch_size=1 timing."""
    import time

    import torch
    from PIL import Image

    raws, lat = [], []
    cuda = model.device.type == "cuda"
    for r in rows:
        img = Image.open(r.path)
        img.load()
        if cuda:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        raws.append(model.raw_score(img))
        if cuda:
            torch.cuda.synchronize()
        lat.append((time.perf_counter() - t0) * 1000)
    return raws, lat


def auroc(scores: list[float], labels: list[bool]) -> float:
    """Mann-Whitney AUROC; labels True = NG (positive)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    rank_pos = sum(r for r, y in zip(ranks, labels) if y)
    return (rank_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def confusion(scores: list[float], labels: list[bool], threshold: float) -> dict:
    """NG predicted when score > threshold."""
    tp = sum(1 for s, y in zip(scores, labels) if y and s > threshold)
    fn = sum(1 for s, y in zip(scores, labels) if y and s <= threshold)
    tn = sum(1 for s, y in zip(scores, labels) if not y and s <= threshold)
    fp = sum(1 for s, y in zip(scores, labels) if not y and s > threshold)
    recall = tp / (tp + fn) if tp + fn else float("nan")
    spec = tn / (tn + fp) if tn + fp else float("nan")
    acc = (tp + tn) / len(scores) if scores else float("nan")
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "recall": recall, "specificity": spec, "accuracy": acc}


def pick_threshold(scores: list[float], labels: list[bool], target_recall: float) -> float:
    """Highest threshold whose recall >= target (maximises specificity at that recall).

    NG iff score > threshold, so the threshold must sit just below the k-th
    highest NG score, where k = ceil(target * n_ng).
    """
    ng = sorted((s for s, y in zip(scores, labels) if y), reverse=True)
    if not ng:
        raise ValueError("Validation set has no NG images; cannot calibrate threshold")
    k = max(1, math.ceil(target_recall * len(ng)))
    s_k = ng[k - 1]
    below = [s for s in scores if s < s_k]
    if not below:
        return s_k - 1e-6
    return (s_k + max(below)) / 2


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    v = sorted(values)
    idx = min(len(v) - 1, max(0, round(q / 100 * (len(v) - 1))))
    return v[idx]
