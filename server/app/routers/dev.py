"""POST /dev/capture: store training photos from the device (ENABLE_DEV_CAPTURE=1 only).

Saves to <dataset_dir>/raw/<sku>/<label>/<canId>_<timestamp>.jpg, the layout that
``ml/split_dataset.py raw`` expects (canId keeps one physical can in one split).
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..config import Settings
from ..deps import Principal, get_settings_dep, require_device
from ..services import decode_image

router = APIRouter(prefix="/dev", tags=["dev"])
_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


class CaptureOut(BaseModel):
    path: str
    count: int


@router.post("/capture", response_model=CaptureOut, status_code=status.HTTP_201_CREATED)
async def capture(
    image: UploadFile = File(...),
    sku: str = Form(...),
    label: str = Form(..., pattern="^(ok|ng)$"),
    can_id: str = Form("c000", alias="canId"),
    _: Principal = Depends(require_device),
    settings: Settings = Depends(get_settings_dep),
):
    if not settings.enable_dev_capture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    if not _SAFE.match(sku) or not _SAFE.match(can_id) or "_" in can_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "sku/canId hanya huruf, angka, '.', '-' (canId tanpa '_')")
    data = await image.read()
    decode_image(data)
    folder = settings.dataset_dir / "raw" / sku / label
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{can_id}_{datetime.now():%Y%m%dT%H%M%S%f}.jpg"
    dest.write_bytes(data)
    return CaptureOut(path=str(dest.relative_to(settings.dataset_dir)), count=len(list(folder.glob("*.jpg"))))
