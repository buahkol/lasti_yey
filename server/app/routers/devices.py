"""Endpoints for the ESP32 device itself (X-Device-Key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import connection as PgConnection

from ..deps import get_conn, require_device
from ..schemas import CurrentBatchOut

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[Depends(require_device)])


@router.get("/current-batch", response_model=CurrentBatchOut)
def current_batch(sku: str | None = Query(default=None), conn: PgConnection = Depends(get_conn, scope="function")):
    """The batch the device should send cans to: the newest running batch (of ``sku`` if given).

    The operator creates and closes batches in the desktop app; the device polls this and follows,
    so nobody has to type the batch code on the device. ``batchCode`` is null when nothing runs.
    """
    sql = "SELECT kode_batch, sku FROM batch WHERE status_batch = 'BERJALAN'"
    params: list = []
    if sku:
        sql += " AND sku = %s"
        params.append(sku)
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY mulai DESC LIMIT 1", params)
        row = cur.fetchone()
    return CurrentBatchOut(batch_code=row["kode_batch"] if row else None, sku=row["sku"] if row else None)
