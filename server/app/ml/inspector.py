"""Inspection backends used by ``POST /inspections``.

* ``PatchCoreInspector`` loads every calibrated product model once at startup
  (AI-03) and serialises GPU access with a lock.
* ``StubInspector`` needs no torch: score = mean brightness. Used by tests and
  for exercising the API/firmware before a model exists (bright image -> NG).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ModelUnavailable(Exception):
    pass


@dataclass
class InspectionOutcome:
    raw_score: float
    score: float  # normalised 0..1
    threshold: float
    version: str
    inference_ms: int

    @property
    def is_ng(self) -> bool:
        # D2: NG when the anomaly score exceeds the threshold.
        return self.score > self.threshold


class BaseInspector:
    def inspect(self, sku: str, image: Image.Image) -> InspectionOutcome:
        raise NotImplementedError

    def models(self) -> dict[str, tuple[str, float]]:
        """sku -> (version, threshold) for every loaded model."""
        raise NotImplementedError

    @property
    def device(self) -> str:
        return "cpu"


class StubInspector(BaseInspector):
    def __init__(self, threshold: float = 0.5, version: str = "stub"):
        self.threshold = threshold
        self.version = version

    def inspect(self, sku: str, image: Image.Image) -> InspectionOutcome:
        t0 = time.perf_counter()
        score = float(np.asarray(image.convert("L"), dtype=np.float32).mean() / 255.0)
        return InspectionOutcome(score, score, self.threshold, self.version,
                                 int((time.perf_counter() - t0) * 1000))

    def models(self) -> dict[str, tuple[str, float]]:
        return {}


class PatchCoreInspector(BaseInspector):
    def __init__(self, model_dir: Path, device_pref: str = "auto"):
        from . import patchcore as pc

        self._pc = pc
        self.model_dir = Path(model_dir)
        self._device = pc.pick_device(device_pref)
        self._extractors: dict[tuple[str, int], pc.FeatureExtractor] = {}
        self._models: dict[str, pc.PatchCore] = {}
        self._lock = threading.Lock()

    @property
    def device(self) -> str:
        return str(self._device)

    def load_all(self) -> None:
        if not self.model_dir.is_dir():
            logger.warning("Model dir %s does not exist; no models loaded", self.model_dir)
            return
        for sku_dir in sorted(p for p in self.model_dir.iterdir() if p.is_dir()):
            self.load(sku_dir.name)

    def load(self, sku: str) -> bool:
        pc = self._pc
        version = pc.latest_version(self.model_dir, sku)
        if version is None:
            logger.warning("No calibrated model for %s", sku)
            return False
        meta = pc.load_meta(self.model_dir, sku, version)
        key = (meta.backbone, meta.feature_dim)
        if key not in self._extractors:
            logger.info("Loading backbone %s on %s", meta.backbone, self._device)
            self._extractors[key] = pc.FeatureExtractor(meta.backbone, meta.feature_dim).to(self._device)
        model = pc.PatchCore.load(self.model_dir, sku, version, self._extractors[key])
        # Warm-up so the first real request is not slow (cuDNN autotune, allocations).
        model.raw_score(Image.new("RGB", (meta.image_size, meta.image_size)))
        self._models[sku] = model
        logger.info("Loaded %s %s (bank=%d, threshold=%.4f)", sku, version, meta.bank_size, meta.threshold)
        return True

    def inspect(self, sku: str, image: Image.Image) -> InspectionOutcome:
        model = self._models.get(sku)
        if model is None:
            raise ModelUnavailable(sku)
        with self._lock:
            t0 = time.perf_counter()
            raw = model.raw_score(image)
            if self._device.type == "cuda":
                import torch

                torch.cuda.synchronize()
            ms = int((time.perf_counter() - t0) * 1000)
        meta = model.meta
        return InspectionOutcome(raw, meta.normalise(raw), float(meta.threshold), meta.version, ms)

    def models(self) -> dict[str, tuple[str, float]]:
        return {sku: (m.meta.version, float(m.meta.threshold)) for sku, m in self._models.items()}
