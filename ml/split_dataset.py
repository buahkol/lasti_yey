"""Build a train/val/test manifest (AI-07: splits never share a physical can).

Two sources:

* ``raw`` (our photo box, collected via POST /dev/capture):
      <raw>/<label>/<canId>_<anything>.jpg     label in {ok, ng}
  OK cans are split by can id into train/val/test; NG cans into val/test.

* ``goodsad`` (pipeline dry run on the GoodsAD dataset, MVTec-style layout):
      <root>/<category>/train/good/*.jpg, <root>/<category>/test/<type>/*.jpg
  train/good -> train; test/* split into val/test, grouped by filename prefix.

Image paths in the manifest are relative to ``--raw`` / ``--root``; give the
same folder as ``--data-root`` to build_memory_bank, calibrate_threshold,
evaluate and tools/fake_device.py.

Examples
--------
uv run python -m ml.split_dataset raw --raw dataset/raw/SRD-TOMAT-155G \
    --out dataset/manifests/SRD-TOMAT-155G.csv
uv run python -m ml.split_dataset goodsad --root ~/lasti/data/goodsad --category drink_can \
    --out dataset/manifests/DEMO-CAN.csv
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from ml.common import Row, write_manifest

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def _images(d: Path) -> list[Path]:
    return sorted(p for p in d.glob("*") if p.suffix.lower() in IMG_EXT)


def _rel(p: Path, root: Path) -> str:
    """Path relative to the source folder, POSIX style, so manifests are portable."""
    return p.relative_to(root).as_posix()


def _group_of(p: Path) -> str:
    return p.stem.split("_")[0]


def _split_groups(groups: list[str], fractions: list[float], rng: random.Random) -> list[list[str]]:
    groups = sorted(set(groups))
    rng.shuffle(groups)
    out, start = [], 0
    for i, f in enumerate(fractions):
        end = len(groups) if i == len(fractions) - 1 else start + round(f * len(groups))
        out.append(groups[start:end])
        start = end
    return out


def from_raw(raw: Path, seed: int, ok_frac: tuple[float, float, float], ng_val: float) -> list[Row]:
    rng = random.Random(seed)
    rows: list[Row] = []
    ok = _images(raw / "ok")
    ng = _images(raw / "ng")
    if not ok:
        raise SystemExit(f"No OK images in {raw / 'ok'}")
    # A can photographed as both ok and ng (e.g. before/after denting) must stay in one split.
    ng_groups = {_group_of(p) for p in ng}
    ok_only = [g for g in {_group_of(p) for p in ok} if g not in ng_groups]
    train_g, val_g, test_g = _split_groups(ok_only, list(ok_frac), rng)
    ngv_g, ngt_g = _split_groups(list(ng_groups), [ng_val, 1 - ng_val], rng)
    split_of = {**{g: "train" for g in train_g}, **{g: "val" for g in val_g},
                **{g: "test" for g in test_g}, **{g: "val" for g in ngv_g}, **{g: "test" for g in ngt_g}}
    for p in ok:
        rows.append(Row(_rel(p, raw), split_of[_group_of(p)], "ok", _group_of(p)))
    for p in ng:
        rows.append(Row(_rel(p, raw), split_of[_group_of(p)], "ng", _group_of(p)))
    return rows


def from_goodsad(root: Path, category: str, seed: int, val_frac: float) -> list[Row]:
    rng = random.Random(seed)
    cat = root / category
    rows = [Row(_rel(p, root), "train", "ok", f"train-{_group_of(p)}") for p in _images(cat / "train" / "good")]
    by_group: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for tdir in sorted(d for d in (cat / "test").iterdir() if d.is_dir()):
        for p in _images(tdir):
            by_group[f"test-{_group_of(p)}"].append((p, tdir.name))
    val_g, _ = _split_groups(list(by_group), [val_frac, 1 - val_frac], rng)
    val_set = set(val_g)
    for g, items in by_group.items():
        for p, kind in items:
            label = "ok" if kind == "good" else "ng"
            rows.append(Row(_rel(p, root), "val" if g in val_set else "test", label, g,
                            "" if label == "ok" else kind))
    return rows


def summary(rows: list[Row]) -> str:
    c: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        c[(r.split, r.label)] += 1
    lines = ["split   ok    ng"]
    for s in ("train", "val", "test"):
        lines.append(f"{s:<6} {c[(s, 'ok')]:>4}  {c[(s, 'ng')]:>4}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="source", required=True)
    r = sub.add_parser("raw")
    r.add_argument("--raw", type=Path, required=True)
    r.add_argument("--ok-split", default="0.6,0.15,0.25", help="train,val,test fractions for OK cans")
    r.add_argument("--ng-val", type=float, default=0.4, help="fraction of NG cans for validation")
    g = sub.add_parser("goodsad")
    g.add_argument("--root", type=Path, required=True)
    g.add_argument("--category", default="drink_can")
    g.add_argument("--val-frac", type=float, default=0.4)
    for p in (r, g):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    if a.source == "raw":
        fr = tuple(float(x) for x in a.ok_split.split(","))
        rows = from_raw(a.raw.expanduser(), a.seed, fr, a.ng_val)
    else:
        rows = from_goodsad(a.root.expanduser(), a.category, a.seed, a.val_frac)
    write_manifest(a.out, rows)
    root = a.raw if a.source == "raw" else a.root
    print(f"Wrote {a.out} ({len(rows)} images, paths relative to {root}; "
          f"pass --data-root {root} to the other scripts)\n{summary(rows)}")


if __name__ == "__main__":
    main()
