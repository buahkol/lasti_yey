"""D2 #5 POST /inspections, #6 alerts, #7 batch inspection report, #11 photo."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from psycopg2.extensions import connection as PgConnection

from ..config import Settings
from ..deps import Principal, get_conn, get_inspector, get_settings_dep, require_device, require_user
from ..ml.inspector import BaseInspector, ModelUnavailable
from ..schemas import AlertOut, BatchInspectionReport, InspectionResult
from ..services import decode_image, get_batch, inspection_counts, require_open_batch, save_image, thumbnail_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inspections", tags=["inspections"])

API_PREFIX = "/api/v1"


@router.post("", response_model=InspectionResult, status_code=status.HTTP_201_CREATED)
async def inspect_package(
    image: UploadFile = File(...),
    batch_code: str = Form(..., alias="batchCode"),
    timestamp: datetime = Form(...),
    _: Principal = Depends(require_device),
    conn: PgConnection = Depends(get_conn),
    inspector: BaseInspector = Depends(get_inspector),
    settings: Settings = Depends(get_settings_dep),
):
    t0 = time.perf_counter()
    batch = await run_in_threadpool(require_open_batch, conn, batch_code)
    data = await image.read()
    img = decode_image(data)
    try:
        outcome = await run_in_threadpool(inspector.inspect, batch["sku"], img)
    except ModelUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Model inspeksi untuk produk {batch['sku']} belum tersedia") from exc

    rel = await run_in_threadpool(save_image, settings.image_dir, batch_code, timestamp, data, img)
    result = "NG" if outcome.is_ng else "OK"
    latency = int((time.perf_counter() - t0) * 1000)

    def _store() -> int:
        try:
            # Re-check under a shared lock: the batch may have been closed during inference.
            # Locking only here (not for the whole upload) keeps a slow device from blocking a close.
            require_open_batch(conn, batch_code, lock=True)
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO inspeksi (kode_batch, hasil, skor_anomali, skor_mentah, ambang_batas,
                                             versi_model, lokasi_citra, waktu, latensi_ms)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (batch_code, result, outcome.score, outcome.raw_score, outcome.threshold,
                     outcome.version, rel, timestamp, latency),
                )
                inspection_id = cur.fetchone()["id"]
                if result == "NG":  # FR-16: same transaction as the inspection row
                    cur.execute(
                        """INSERT INTO kejadian_produksi (kode_batch, jenis, sumber, keterangan, waktu, id_inspeksi)
                           VALUES (%s, 'REJECT', 'AI', %s, %s, %s)""",
                        (batch_code, f"Skor anomali {outcome.score:.3f} > ambang {outcome.threshold:.3f}",
                         timestamp, inspection_id),
                    )
            return inspection_id
        except Exception:
            (settings.image_dir / rel).unlink(missing_ok=True)
            raise

    inspection_id = await run_in_threadpool(_store)
    logger.info("inspection %s batch=%s %s score=%.3f thr=%.3f infer=%dms total=%dms",
                inspection_id, batch_code, result, outcome.score, outcome.threshold,
                outcome.inference_ms, latency)
    return InspectionResult(inspection_id=inspection_id, result=result,
                            anomaly_score=round(outcome.score, 4), threshold=round(outcome.threshold, 4),
                            reject=result == "NG")


@router.get("/alerts", response_model=list[AlertOut], dependencies=[Depends(require_user)])
def alerts(since: datetime | None = None, batch_code: str | None = Query(default=None, alias="batchCode"),
           limit: int = Query(default=50, ge=1, le=500), conn: PgConnection = Depends(get_conn)):
    where, params = ["hasil = 'NG'"], []
    if since:
        where.append("waktu > %s")
        params.append(since)
    if batch_code:
        where.append("kode_batch = %s")
        params.append(batch_code)
    with conn.cursor() as cur:
        cur.execute(f"""SELECT id, kode_batch, skor_anomali, waktu FROM inspeksi
                        WHERE {' AND '.join(where)} ORDER BY waktu DESC, id DESC LIMIT %s""",
                    [*params, limit])
        rows = cur.fetchall()
    return [AlertOut(inspection_id=r["id"], batch_code=r["kode_batch"],
                     anomaly_score=round(r["skor_anomali"], 4),
                     image_url=f"{API_PREFIX}/inspections/{r['id']}/photo", timestamp=r["waktu"])
            for r in rows]


@router.get("/reports/{batch_code}", response_model=BatchInspectionReport,
            dependencies=[Depends(require_user)])
def batch_report(batch_code: str, conn: PgConnection = Depends(get_conn)):
    batch = get_batch(conn, batch_code)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Batch {batch_code} tidak ditemukan")
    total, ok, ng = inspection_counts(conn, batch_code)
    with conn.cursor() as cur:
        # Hours in the session time zone (Asia/Jakarta), zero-padded as in D2 ("08", "09").
        cur.execute("""SELECT to_char(waktu, 'HH24') AS jam, count(*) AS n FROM inspeksi
                       WHERE kode_batch = %s AND hasil = 'NG' GROUP BY jam ORDER BY jam""", (batch_code,))
        per_hour = {r["jam"]: r["n"] for r in cur.fetchall()}
    price = float(batch["harga_satuan"])
    return BatchInspectionReport(
        batch_code=batch_code, total=total, ok=ok, ng=ng, ng_per_hour=per_hour,
        estimated_loss=ng * price, sku=batch["sku"], unit_price=price,
        ng_percent=round(100 * ng / total, 2) if total else 0.0,
        inspection_status=batch["status_inspeksi"], batch_status=batch["status_batch"],
    )


def _photo(inspection_id: int, size: str, conn: PgConnection, settings: Settings) -> FileResponse:
    with conn.cursor() as cur:
        cur.execute("SELECT lokasi_citra FROM inspeksi WHERE id = %s", (inspection_id,))
        r = cur.fetchone()
    path = settings.image_dir / r["lokasi_citra"] if r else None
    if path is None or not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Foto inspeksi {inspection_id} tidak ditemukan")
    if size == "thumb":
        path = thumbnail_path(settings.image_dir, r["lokasi_citra"])
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{inspection_id}/photo", response_class=FileResponse, dependencies=[Depends(require_user)])
def photo(inspection_id: int, size: str = Query(default="full", pattern="^(full|thumb)$"),
          conn: PgConnection = Depends(get_conn), settings: Settings = Depends(get_settings_dep)):
    return _photo(inspection_id, size, conn, settings)


# D2's alert example links to /image; kept as an alias of /photo (noted in the D3 report).
@router.get("/{inspection_id}/image", response_class=FileResponse, include_in_schema=False,
            dependencies=[Depends(require_user)])
def image_alias(inspection_id: int, size: str = Query(default="full", pattern="^(full|thumb)$"),
                conn: PgConnection = Depends(get_conn), settings: Settings = Depends(get_settings_dep)):
    return _photo(inspection_id, size, conn, settings)
