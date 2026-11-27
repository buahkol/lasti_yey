"""Batches: create/list/close (added beyond D2, FR-05/06), D2 #8 status, D2 #10 history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg2.extensions import connection as PgConnection

from ..config import Settings
from ..db import is_unique_violation
from ..deps import get_conn, get_settings_dep, require_user
from ..schemas import (
    BatchIn,
    BatchOut,
    BatchState,
    BatchStatusList,
    BatchStatusRow,
    InspectionHistory,
    InspectionRow,
    InspectionStatus,
    Result,
)
from ..services import BATCH_LIST_SQL, batch_row_to_api, compute_inspection_status, get_batch, inspection_counts

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[Depends(require_user)])


def _one(conn: PgConnection, code: str) -> BatchOut:
    with conn.cursor() as cur:
        cur.execute(BATCH_LIST_SQL + " WHERE b.kode_batch = %s", (code,))
        r = cur.fetchone()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Batch {code} tidak ditemukan")
    return BatchOut(**batch_row_to_api(r))


@router.get("", response_model=list[BatchOut])
def list_batches(batch_status: BatchState | None = Query(default=None, alias="status"),
                 sku: str | None = None, conn: PgConnection = Depends(get_conn, scope="function")):
    where, params = [], []
    if batch_status:
        where.append("b.status_batch = %s")
        params.append(batch_status.value)
    if sku:
        where.append("b.sku = %s")
        params.append(sku)
    sql = BATCH_LIST_SQL + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY b.mulai DESC"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [BatchOut(**batch_row_to_api(r)) for r in cur.fetchall()]


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(body: BatchIn, conn: PgConnection = Depends(get_conn, scope="function")):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM produk WHERE sku = %s", (body.sku,))
        if cur.fetchone() is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Produk {body.sku} tidak terdaftar")
        try:
            cur.execute("INSERT INTO batch (kode_batch, sku) VALUES (%s, %s)", (body.batch_code, body.sku))
        except Exception as exc:
            if is_unique_violation(exc):
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"Kode batch {body.batch_code} sudah digunakan") from exc
            raise
    return _one(conn, body.batch_code)


# Declared before /{batch_code} so "inspection-status" is not captured as a batch code.
@router.get("/inspection-status", response_model=BatchStatusList)
def inspection_status(sku: str | None = None,
                      status_: InspectionStatus = Query(default=InspectionStatus.PASSED, alias="status"),
                      conn: PgConnection = Depends(get_conn, scope="function")):
    params: list = [status_.value]
    sql = BATCH_LIST_SQL + " WHERE b.status_inspeksi = %s"
    if sku:
        sql += " AND b.sku = %s"
        params.append(sku)
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY b.mulai DESC", params)
        rows = cur.fetchall()
    return BatchStatusList(batches=[
        BatchStatusRow(batch_code=r["kode_batch"], sku=r["sku"], status=r["status_inspeksi"], ok_qty=r["ok"])
        for r in rows
    ])


@router.get("/{batch_code}", response_model=BatchOut)
def get_one(batch_code: str, conn: PgConnection = Depends(get_conn, scope="function")):
    return _one(conn, batch_code)


@router.post("/{batch_code}/close", response_model=BatchOut)
def close_batch(batch_code: str, conn: PgConnection = Depends(get_conn, scope="function"),
                settings: Settings = Depends(get_settings_dep)):
    batch = get_batch(conn, batch_code, for_update=True)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Batch {batch_code} tidak ditemukan")
    if batch["status_batch"] == "DITUTUP":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Batch {batch_code} sudah ditutup")
    total, _, ng = inspection_counts(conn, batch_code)
    new_status = compute_inspection_status("DITUTUP", total, ng, settings.ng_tolerance)
    with conn.cursor() as cur:
        cur.execute("""UPDATE batch SET status_batch = 'DITUTUP', selesai = now(), status_inspeksi = %s
                       WHERE kode_batch = %s""", (new_status, batch_code))
    return _one(conn, batch_code)


@router.get("/{batch_code}/inspections", response_model=InspectionHistory)
def history(batch_code: str, result: Result | None = None, conn: PgConnection = Depends(get_conn, scope="function")):
    total, _, ng = inspection_counts(conn, batch_code)
    if total == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Data inspeksi batch {batch_code} tidak tersedia")
    sql = "SELECT id, hasil, skor_anomali, waktu FROM inspeksi WHERE kode_batch = %s"
    params: list = [batch_code]
    if result:
        sql += " AND hasil = %s"
        params.append(result.value)
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY waktu DESC, id DESC", params)
        rows = cur.fetchall()
    return InspectionHistory(batch_code=batch_code, total=total, ng=ng, inspections=[
        InspectionRow(inspection_id=r["id"], result=r["hasil"], anomaly_score=round(r["skor_anomali"], 4),
                      timestamp=r["waktu"]) for r in rows
    ])
