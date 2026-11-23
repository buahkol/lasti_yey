"""Minimal PatchCore (Roth et al., 2022) for per-product can inspection.

Shared by the server (inference) and ``ml/`` scripts (memory-bank building,
threshold calibration, evaluation) so preprocessing is identical in both.

Pipeline
--------
image -> optional fixed crop -> resize -> ImageNet normalise
      -> backbone layer2 + layer3 features -> 3x3 local average
      -> upsample layer3 to layer2 grid -> concat -> channel pooling to ``feature_dim``
      -> patch features [N_patches, D]
Training: patch features of all normal images -> greedy coreset -> memory bank.
Scoring : each patch's nearest-neighbour distance to the bank; image score = max.
          Raw scores are min-max normalised per product to 0..1 using the
          validation set (D2 examples use 0..1 scores).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def pick_device(pref: str = "auto") -> torch.device:
    if pref == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(pref)


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
@dataclass
class Preprocess:
    image_size: int = 224
    # Optional crop box as fractions of width/height: (x0, y0, x1, y1).
    crop: tuple[float, float, float, float] | None = None

    def __call__(self, img: Image.Image) -> torch.Tensor:
        img = img.convert("RGB")
        if self.crop:
            w, h = img.size
            x0, y0, x1, y1 = self.crop
            img = img.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))
        img = img.resize((self.image_size, self.image_size), Image.BILINEAR)
        arr = torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0).permute(2, 0, 1)
        mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
        std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
        return (arr - mean) / std


# --------------------------------------------------------------------------- #
# Feature extractor
# --------------------------------------------------------------------------- #
_BACKBONES = {"wide_resnet50_2", "resnet18", "resnet50"}


class FeatureExtractor(nn.Module):
    """Mid-level ResNet features (layer2 + layer3) as locally aware patch features."""

    def __init__(self, backbone: str = "wide_resnet50_2", feature_dim: int = 1024):
        super().__init__()
        import torchvision.models as tvm

        if backbone not in _BACKBONES:
            raise ValueError(f"Unsupported backbone {backbone!r}; choose from {sorted(_BACKBONES)}")
        net = getattr(tvm, backbone)(weights="DEFAULT")
        self.stem = nn.Sequential(net.conv1, net.bn1, net.relu, net.maxpool, net.layer1)
        self.layer2 = net.layer2
        self.layer3 = net.layer3
        self.backbone = backbone
        self.feature_dim = feature_dim
        self.eval()
        for p in self.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, tuple[int, int]]:
        """x: [B,3,H,W] -> (features [B, h*w, D], (h, w))."""
        f1 = self.stem(x)
        f2 = self.layer2(f1)
        f3 = self.layer3(f2)
        f2 = F.avg_pool2d(f2, 3, stride=1, padding=1)
        f3 = F.avg_pool2d(f3, 3, stride=1, padding=1)
        f3 = F.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        feat = torch.cat([f2, f3], dim=1)  # [B, C, h, w]
        b, c, h, w = feat.shape
        feat = feat.permute(0, 2, 3, 1).reshape(b, h * w, c)
        if c > self.feature_dim:
            feat = F.adaptive_avg_pool1d(feat, self.feature_dim)
        return feat, (h, w)


# --------------------------------------------------------------------------- #
# Coreset + nearest neighbour
# --------------------------------------------------------------------------- #
@torch.no_grad()
def greedy_coreset(
    features: torch.Tensor, ratio: float, proj_dim: int = 128, seed: int = 0
) -> torch.Tensor:
    """Approximate greedy k-center selection; returns indices into ``features``."""
    n = features.shape[0]
    k = max(1, int(math.ceil(n * ratio)))
    if k >= n:
        return torch.arange(n, device=features.device)
    gen = torch.Generator(device="cpu").manual_seed(seed)
    if features.shape[1] > proj_dim:
        proj = torch.randn(features.shape[1], proj_dim, generator=gen).to(features)
        reduced = features @ proj
    else:
        reduced = features
    selected = torch.empty(k, dtype=torch.long, device=features.device)
    idx = int(torch.randint(n, (1,), generator=gen))
    min_d = torch.full((n,), float("inf"), device=features.device)
    for i in range(k):
        selected[i] = idx
        d = torch.linalg.vector_norm(reduced - reduced[idx], dim=1)
        min_d = torch.minimum(min_d, d)
        idx = int(torch.argmax(min_d))
    return selected


@torch.no_grad()
def nearest_distance(query: torch.Tensor, bank: torch.Tensor, chunk: int = 16384) -> torch.Tensor:
    """Min L2 distance of each query row to the bank. query [P,D], bank [M,D] -> [P]."""
    best = torch.full((query.shape[0],), float("inf"), device=query.device)
    for start in range(0, bank.shape[0], chunk):
        d = torch.cdist(query, bank[start : start + chunk])
        best = torch.minimum(best, d.min(dim=1).values)
    return best


# --------------------------------------------------------------------------- #
# Model artifact
# --------------------------------------------------------------------------- #
@dataclass
class ModelMeta:
    sku: str
    version: str
    backbone: str = "wide_resnet50_2"
    feature_dim: int = 1024
    image_size: int = 224
    crop: list[float] | None = None
    coreset_ratio: float = 0.1
    n_train_images: int = 0
    bank_size: int = 0
    # Filled by calibrate_threshold.py
    raw_min: float | None = None
    raw_max: float | None = None
    threshold: float | None = None  # on the normalised 0..1 scale
    calibration: dict = field(default_factory=dict)
    created_at: str = ""

    @property
    def is_calibrated(self) -> bool:
        return None not in (self.raw_min, self.raw_max, self.threshold)

    def preprocess(self) -> Preprocess:
        return Preprocess(self.image_size, tuple(self.crop) if self.crop else None)

    def normalise(self, raw: float) -> float:
        if not self.is_calibrated:
            raise RuntimeError(f"Model {self.sku}/{self.version} is not calibrated")
        span = max(self.raw_max - self.raw_min, 1e-12)
        return float(min(max((raw - self.raw_min) / span, 0.0), 1.0))


_VERSION_RE = re.compile(r"^v(\d+)$")


def model_paths(model_dir: Path, sku: str, version: str) -> tuple[Path, Path]:
    base = Path(model_dir) / sku
    return base / f"{version}.pt", base / f"{version}.json"


def latest_version(model_dir: Path, sku: str, calibrated_only: bool = True) -> str | None:
    base = Path(model_dir) / sku
    if not base.is_dir():
        return None
    versions = []
    for js in base.glob("v*.json"):
        m = _VERSION_RE.match(js.stem)
        if not m or not js.with_suffix(".pt").exists():
            continue
        if calibrated_only and not ModelMeta(**json.loads(js.read_text())).is_calibrated:
            continue
        versions.append(int(m.group(1)))
    return f"v{max(versions)}" if versions else None


def next_version(model_dir: Path, sku: str) -> str:
    base = Path(model_dir) / sku
    nums = [int(m.group(1)) for p in base.glob("v*.pt") if (m := _VERSION_RE.match(p.stem))]
    return f"v{max(nums, default=0) + 1}"


def save_meta(model_dir: Path, meta: ModelMeta) -> Path:
    _, js = model_paths(model_dir, meta.sku, meta.version)
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(asdict(meta), indent=2))
    return js


def load_meta(model_dir: Path, sku: str, version: str) -> ModelMeta:
    _, js = model_paths(model_dir, sku, version)
    return ModelMeta(**json.loads(js.read_text()))


class PatchCore:
    """One product's memory bank + metadata, bound to a shared feature extractor."""

    def __init__(self, meta: ModelMeta, bank: torch.Tensor, extractor: FeatureExtractor):
        self.meta = meta
        self.extractor = extractor
        self.device = next(extractor.parameters()).device
        self.bank = bank.to(self.device, dtype=torch.float32)
        self._pre = meta.preprocess()

    @classmethod
    def load(cls, model_dir: Path, sku: str, version: str, extractor: FeatureExtractor) -> PatchCore:
        pt, _ = model_paths(model_dir, sku, version)
        meta = load_meta(model_dir, sku, version)
        data = torch.load(pt, map_location="cpu", weights_only=True)
        return cls(meta, data["bank"], extractor)

    @torch.no_grad()
    def raw_scores(self, images: list[Image.Image]) -> list[float]:
        x = torch.stack([self._pre(im) for im in images]).to(self.device)
        feats, _ = self.extractor(x)
        out = []
        for f in feats:
            out.append(float(nearest_distance(f, self.bank).max()))
        return out

    def raw_score(self, image: Image.Image) -> float:
        return self.raw_scores([image])[0]


def save_bank(model_dir: Path, meta: ModelMeta, bank: torch.Tensor) -> Path:
    pt, _ = model_paths(model_dir, meta.sku, meta.version)
    pt.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"bank": bank.to("cpu", dtype=torch.float16)}, pt)
    save_meta(model_dir, meta)
    return pt
