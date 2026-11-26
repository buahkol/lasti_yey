"""Evaluate a calibrated model on the held-out test split (K2, K3, AI-04).

Writes doc/model_eval/<sku>_<version>/{metrics.json, scores.csv, confusion.png, scores.png, README.md}

uv run python -m ml.evaluate --manifest dataset/manifests/DEMO-CAN.csv \
    --data-root ~/goodsad --sku DEMO-CAN
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
from pathlib import Path

from ml.common import ROOT, auroc, confusion, percentile, read_manifest, score_rows


def _plots(out: Path, norm: list[float], labels: list[bool], thr: float, cm: dict, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 4))
    grid = [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]
    ax.imshow(grid, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, grid[i][j], ha="center", va="center", fontsize=16)
    ax.set_xticks([0, 1], ["Prediksi OK", "Prediksi NG"])
    ax.set_yticks([0, 1], ["Aktual OK", "Aktual NG"])
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out / "confusion.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist([s for s, y in zip(norm, labels) if not y], bins=30, alpha=0.6, label="OK")
    ax.hist([s for s, y in zip(norm, labels) if y], bins=30, alpha=0.6, label="NG")
    ax.axvline(thr, color="k", linestyle="--", label=f"ambang {thr:.3f}")
    ax.set_xlabel("Skor anomali (ternormalisasi)")
    ax.set_ylabel("Jumlah foto")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "scores.png", dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=None,
                    help="folder the manifest paths are relative to (the one given to split_dataset)")
    ap.add_argument("--sku", required=True)
    ap.add_argument("--version", default="")
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "doc" / "model_eval")
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()

    import torch

    from server.app.ml import patchcore as pc

    version = a.version or pc.latest_version(a.model_dir, a.sku)
    if not version:
        raise SystemExit(f"No calibrated model for {a.sku}")
    device = pc.pick_device(a.device)
    meta = pc.load_meta(a.model_dir, a.sku, version)
    extractor = pc.FeatureExtractor(meta.backbone, meta.feature_dim).to(device)
    model = pc.PatchCore.load(a.model_dir, a.sku, version, extractor)

    rows = [r for r in read_manifest(a.manifest, a.data_root) if r.split == "test"]
    labels = [r.is_ng for r in rows]
    model.raw_score(__import__("PIL.Image", fromlist=["Image"]).new("RGB", (64, 64)))  # warm-up
    raws, lat = score_rows(model, rows)
    norm = [meta.normalise(s) for s in raws]
    thr = float(meta.threshold)
    cm = confusion(norm, labels, thr)
    auc = auroc(raws, labels)

    out = a.out_dir / f"{a.sku}_{version}"
    out.mkdir(parents=True, exist_ok=True)
    metrics = {
        "sku": a.sku, "version": version, "split": "test", "manifest": str(a.manifest),
        "n_ok": labels.count(False), "n_ng": labels.count(True), "threshold": thr,
        "auroc": round(auc, 4), **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in cm.items()},
        "targets": {"K2_recall_min": 0.90, "K3_specificity_min": 0.85, "AI04_latency_ms_max": 500},
        "pass": {"K2": cm["recall"] >= 0.90, "K3": cm["specificity"] >= 0.85,
                 "AI04": percentile(lat, 95) <= 500},
        "latency_ms": {"p50": round(percentile(lat, 50), 1), "p95": round(percentile(lat, 95), 1),
                       "max": round(max(lat), 1)},
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else platform.processor() or "cpu",
        "model": {"backbone": meta.backbone, "image_size": meta.image_size,
                  "coreset_ratio": meta.coreset_ratio, "bank_size": meta.bank_size,
                  "n_train_images": meta.n_train_images, "calibration": meta.calibration},
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    with open(out / "scores.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "label", "detail", "raw_score", "score", "predicted", "latency_ms"])
        for r, raw, s, ms in zip(rows, raws, norm, lat):
            w.writerow([r.path, r.label, r.detail, f"{raw:.5f}", f"{s:.5f}",
                        "ng" if s > thr else "ok", f"{ms:.1f}"])
    _plots(out, norm, labels, thr, cm, f"{a.sku} {version}")

    wrong = [(r, s) for r, s in zip(rows, norm) if (s > thr) != r.is_ng]
    md = [
        f"# Evaluasi model {a.sku} {version}",
        "",
        f"Set uji terpisah: {labels.count(False)} OK, {labels.count(True)} NG (manifest `{a.manifest}`).",
        "",
        "| Ukuran | Nilai | Target | Status |",
        "|---|---|---|---|",
        f"| Recall NG (K2) | {cm['recall']:.1%} | ≥ 90% | {'Lulus' if metrics['pass']['K2'] else 'Belum'} |",
        f"| Specificity (K3) | {cm['specificity']:.1%} | ≥ 85% | {'Lulus' if metrics['pass']['K3'] else 'Belum'} |",
        f"| Latensi inferensi p95 (AI-04) | {metrics['latency_ms']['p95']} ms | ≤ 500 ms | "
        f"{'Lulus' if metrics['pass']['AI04'] else 'Belum'} |",
        f"| AUROC | {auc:.4f} | — | — |",
        "",
        f"Ambang batas {thr:.4f} (ternormalisasi), perangkat: {metrics['device']}.",
        f"Confusion: TP={cm['tp']} FN={cm['fn']} TN={cm['tn']} FP={cm['fp']}.",
        "",
        "![confusion](confusion.png) ![scores](scores.png)",
        "",
        f"## Salah klasifikasi ({len(wrong)})",
        "",
        *[f"- `{Path(r.path).name}` aktual {r.label.upper()} {r.detail}, skor {s:.3f}" for r, s in wrong[:50]],
    ]
    (out / "README.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[4:11]))
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
