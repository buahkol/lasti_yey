"""Calibrate score normalisation and threshold on the validation split (AI-02).

* raw_min / raw_max = min / max raw score on the validation set -> scores become 0..1
* threshold = highest normalised threshold with recall >= target (default 0.90, K2),
  which maximises specificity (K3) at that recall.

uv run python -m ml.calibrate_threshold --manifest dataset/manifests/DEMO-CAN.csv \
    --data-root ~/goodsad --sku DEMO-CAN
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ml.common import ROOT, auroc, confusion, pick_threshold, read_manifest, score_rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=None,
                    help="folder the manifest paths are relative to (the one given to split_dataset)")
    ap.add_argument("--sku", required=True)
    ap.add_argument("--version", default="", help="default: latest version (calibrated or not)")
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models")
    ap.add_argument("--target-recall", type=float, default=0.90)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()

    from server.app.ml import patchcore as pc

    version = a.version or pc.latest_version(a.model_dir, a.sku, calibrated_only=False)
    if not version:
        raise SystemExit(f"No model for {a.sku} in {a.model_dir}")
    meta = pc.load_meta(a.model_dir, a.sku, version)
    extractor = pc.FeatureExtractor(meta.backbone, meta.feature_dim).to(pc.pick_device(a.device))
    model = pc.PatchCore.load(a.model_dir, a.sku, version, extractor)

    rows = [r for r in read_manifest(a.manifest, a.data_root) if r.split == "val"]
    labels = [r.is_ng for r in rows]
    if not any(labels) or all(labels):
        raise SystemExit("Validation split needs both OK and NG images")
    raws, _ = score_rows(model, rows)

    raw_min, raw_max = min(raws), max(raws)
    span = max(raw_max - raw_min, 1e-12)
    norm = [(s - raw_min) / span for s in raws]
    thr = pick_threshold(norm, labels, a.target_recall)
    cm = confusion(norm, labels, thr)
    auc = auroc(norm, labels)

    meta.raw_min, meta.raw_max, meta.threshold = raw_min, raw_max, round(thr, 6)
    meta.calibration = {
        "split": "val", "n_ok": labels.count(False), "n_ng": labels.count(True),
        "target_recall": a.target_recall, "auroc": round(auc, 4),
        "recall": round(cm["recall"], 4), "specificity": round(cm["specificity"], 4),
        "manifest": str(a.manifest),
    }
    pc.save_meta(a.model_dir, meta)
    print(f"{a.sku} {version}: raw range [{raw_min:.4f}, {raw_max:.4f}]  threshold={thr:.4f}")
    print(f"val n_ok={labels.count(False)} n_ng={labels.count(True)}  AUROC={auc:.4f}  "
          f"recall={cm['recall']:.3f}  specificity={cm['specificity']:.3f}  "
          f"(tp={cm['tp']} fn={cm['fn']} tn={cm['tn']} fp={cm['fp']})")


if __name__ == "__main__":
    main()
