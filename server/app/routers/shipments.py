"""D2 #9 POST /shipments (FR-28, FR-29) and GET /shipments (added)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg2.extensions import connection as PgConnection

from ..deps import get_conn, require_user
from ..schemas import ShipmentCreated, ShipmentIn, ShipmentOut

router = APIRouter(prefix="/shipments", tags=["shipments"], dependencies=[Depends(require_user)])


@router.post("", response_model=ShipmentCreated, status_code=status.HTTP_201_CREATED)
def submit_shipment(body: ShipmentIn, conn: PgConnection = Depends(get_conn)):
    codes = list(dict.fromkeys(body.batch_codes))  # de-duplicate, keep order
    with conn.cursor() as cur:
        cur.execute(
            """SELECT b.kode_batch, b.status_inspeksi,
                      (SELECT count(*) FROM inspeksi i WHERE i.kode_batch = b.kode_batch AND i.hasil = 'OK') AS ok
               FROM batch b WHERE b.kode_batch = ANY(%s) FOR UPDATE OF b""",
            (codes,),
        )
        found = {r["kode_batch"]: r for r in cur.fetchall()}
        unknown = [c for c in codes if c not in found]
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                {"message": "Kode batch tidak terdaftar", "unknownBatches": unknown})
        hold = [c for c in codes if found[c]["status_inspeksi"] != "PASSED"]
        if hold:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                {"message": "Batch belum lolos inspeksi", "holdBatches": hold})
        ok_total = sum(found[c]["ok"] for c in codes)
        if body.quantity > ok_total:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Jumlah kaleng ({body.quantity}) melebihi kaleng OK pada batch ({ok_total})")
        cur.execute("INSERT INTO pengiriman (nomor_pesanan, jumlah) VALUES (%s, %s) RETURNING id",
                    (body.order_id, body.quantity))
        sid = cur.fetchone()["id"]
        cur.executemany("INSERT INTO pengiriman_batch (id_pengiriman, kode_batch) VALUES (%s, %s)",
                        [(sid, c) for c in codes])
    return ShipmentCreated(shipment_id=sid, order_id=body.order_id, batch_codes=codes)


@router.get("", response_model=list[ShipmentOut])
def list_shipments(batch_code: str | None = Query(default=None, alias="batchCode"),
                   limit: int = Query(default=200, ge=1, le=1000), conn: PgConnection = Depends(get_conn)):
    sql = """SELECT s.id, s.nomor_pesanan, s.jumlah, s.dibuat_pada,
                    array_agg(sb.kode_batch ORDER BY sb.kode_batch) AS batches
             FROM pengiriman s JOIN pengiriman_batch sb ON sb.id_pengiriman = s.id"""
    params: list = []
    if batch_code:
        sql += " WHERE s.id IN (SELECT id_pengiriman FROM pengiriman_batch WHERE kode_batch = %s)"
        params.append(batch_code)
    sql += " GROUP BY s.id ORDER BY s.dibuat_pada DESC LIMIT %s"
    with conn.cursor() as cur:
        cur.execute(sql, [*params, limit])
        return [ShipmentOut(shipment_id=r["id"], order_id=r["nomor_pesanan"], batch_codes=r["batches"],
                            quantity=r["jumlah"], created_at=r["dibuat_pada"]) for r in cur.fetchall()]
