"""Build a PatchCore memory bank for one product from the manifest's train split (AI-01, AI-06).

uv run python -m ml.build_memory_bank --manifest dataset/manifests/DEMO-CAN.csv \
    --data-root ~/goodsad --sku DEMO-CAN
Writes models/<sku>/v<N>.pt and an uncalibrated v<N>.json; run calibrate_threshold next.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from ml.common import ROOT, read_manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=None,
                    help="folder the manifest paths are relative to (the one given to split_dataset)")
    ap.add_argument("--sku", required=True)
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models")
    ap.add_argument("--backbone", default="wide_resnet50_2")
    ap.add_argument("--feature-dim", type=int, default=1024)
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1 as fractions, e.g. 0.2,0.1,0.8,0.9")
    ap.add_argument("--coreset", type=float, default=0.1, help="coreset ratio (0.01-0.25)")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--version", default="", help="override version label (default: next vN)")
    a = ap.parse_args()

    import torch
    from PIL import Image

    from server.app.ml import patchcore as pc

    rows = [r for r in read_manifest(a.manifest, a.data_root) if r.split == "train" and r.label == "ok"]
    if not rows:
        raise SystemExit("No train/ok rows in manifest")
    device = pc.pick_device(a.device)
    crop = [float(x) for x in a.crop.split(",")] if a.crop else None
    pre = pc.Preprocess(a.image_size, tuple(crop) if crop else None)
    extractor = pc.FeatureExtractor(a.backbone, a.feature_dim).to(device)
    print(f"{len(rows)} train images, backbone={a.backbone}, device={device}")

    t0 = time.perf_counter()
    feats = []
    for i in range(0, len(rows), a.batch_size):
        batch = torch.stack([pre(Image.open(r.path)) for r in rows[i : i + a.batch_size]]).to(device)
        f, (h, w) = extractor(batch)
        feats.append(f.reshape(-1, f.shape[-1]))
    all_feats = torch.cat(feats)
    print(f"Extracted {tuple(all_feats.shape)} patch features ({h}x{w} per image) "
          f"in {time.perf_counter() - t0:.1f}s")

    t1 = time.perf_counter()
    idx = pc.greedy_coreset(all_feats, a.coreset)
    bank = all_feats[idx]
    print(f"Coreset {a.coreset:.0%}: bank {tuple(bank.shape)} in {time.perf_counter() - t1:.1f}s")

    version = a.version or pc.next_version(a.model_dir, a.sku)
    meta = pc.ModelMeta(
        sku=a.sku, version=version, backbone=a.backbone, feature_dim=a.feature_dim,
        image_size=a.image_size, crop=crop, coreset_ratio=a.coreset,
        n_train_images=len(rows), bank_size=int(bank.shape[0]),
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    pt = pc.save_bank(a.model_dir, meta, bank)
    print(f"Saved {pt} (uncalibrated). Next: python -m ml.calibrate_threshold "
          f"--manifest {a.manifest}"
          + (f" --data-root {a.data_root}" if a.data_root else "")
          + f" --sku {a.sku} --version {version}")


if __name__ == "__main__":
    main()
