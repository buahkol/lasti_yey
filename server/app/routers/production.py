"""D2 #1 outputs, #2 events, #4 production reports (+ GET events, added)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg2.extensions import connection as PgConnection

from ..deps import Principal, get_conn, require_device, require_user, require_user_or_device
from ..schemas import (
    BatchReportRow,
    EventCreated,
    EventIn,
    EventOut,
    EventSource,
    EventType,
    OutputIn,
    OutputOut,
    ProductionReport,
)
from ..services import get_batch, require_open_batch

router = APIRouter(prefix="/production", tags=["production"])


@router.post("/outputs", response_model=OutputOut, status_code=status.HTTP_201_CREATED)
def record_output(body: OutputIn, _: Principal = Depends(require_device),
                  conn: PgConnection = Depends(get_conn)):
    require_open_batch(conn, body.batch_code)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO output_produksi (kode_batch, jumlah, waktu) VALUES (%s, %s, %s)",
                    (body.batch_code, body.quantity, body.timestamp))
        cur.execute("SELECT COALESCE(sum(jumlah), 0) AS t FROM output_produksi WHERE kode_batch = %s",
                    (body.batch_code,))
        total = cur.fetchone()["t"]
    return OutputOut(batch_code=body.batch_code, total_output=int(total))


@router.post("/events", response_model=EventCreated, status_code=status.HTTP_201_CREATED)
def record_event(body: EventIn, who: Principal = Depends(require_user_or_device),
                 conn: PgConnection = Depends(get_conn)):
    if get_batch(conn, body.batch_code) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Kode batch {body.batch_code} tidak terdaftar")
    # REJECT/AI events are written by POST /inspections; operators record the manual types (FR-17).
    if who.kind == "user" and body.event_type == EventType.REJECT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Kejadian REJECT dicatat otomatis oleh inspeksi AI")
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO kejadian_produksi (kode_batch, jenis, sumber, keterangan, waktu)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (body.batch_code, body.event_type.value, body.source.value, body.note, body.timestamp),
        )
        return EventCreated(event_id=cur.fetchone()["id"])


@router.get("/events", response_model=list[EventOut], dependencies=[Depends(require_user)])
def list_events(batch_code: str | None = Query(default=None, alias="batchCode"),
                date_: date | None = Query(default=None, alias="date"),
                event_type: EventType | None = Query(default=None, alias="eventType"),
                limit: int = Query(default=200, ge=1, le=1000),
                conn: PgConnection = Depends(get_conn)):
    where, params = [], []
    if batch_code:
        where.append("kode_batch = %s")
        params.append(batch_code)
    if date_:
        where.append("waktu::date = %s")
        params.append(date_)
    if event_type:
        where.append("jenis = %s")
        params.append(event_type.value)
    sql = "SELECT * FROM kejadian_produksi" + (" WHERE " + " AND ".join(where) if where else "")
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY waktu DESC, id DESC LIMIT %s", [*params, limit])
        return [EventOut(event_id=r["id"], batch_code=r["kode_batch"], event_type=r["jenis"],
                         source=EventSource(r["sumber"]), timestamp=r["waktu"], note=r["keterangan"],
                         inspection_id=r["id_inspeksi"]) for r in cur.fetchall()]


@router.get("/reports", response_model=ProductionReport, dependencies=[Depends(require_user)])
def production_report(batch_code: str | None = Query(default=None, alias="batchCode"),
                      date_: date | None = Query(default=None, alias="date"),
                      conn: PgConnection = Depends(get_conn)):
    """Per-batch recap. Without batchCode: every batch active on the date (started, or had data)."""
    day = date_ or date.today()
    if batch_code:
        cond, params = "b.kode_batch = %s", [batch_code]
    else:
        cond = """(b.mulai::date = %s
                   OR EXISTS (SELECT 1 FROM inspeksi x WHERE x.kode_batch = b.kode_batch AND x.waktu::date = %s)
                   OR EXISTS (SELECT 1 FROM output_produksi y
                              WHERE y.kode_batch = b.kode_batch AND y.waktu::date = %s))"""
        params = [day, day, day]
    sql = f"""
        SELECT b.kode_batch,
               COALESCE((SELECT sum(jumlah) FROM output_produksi o WHERE o.kode_batch = b.kode_batch), 0) AS total_output,
               (SELECT count(*) FROM inspeksi i WHERE i.kode_batch = b.kode_batch AND i.hasil = 'OK') AS ok,
               (SELECT count(*) FROM inspeksi i WHERE i.kode_batch = b.kode_batch AND i.hasil = 'NG') AS ng,
               (SELECT count(*) FROM kejadian_produksi k WHERE k.kode_batch = b.kode_batch) AS events
        FROM batch b WHERE {cond} ORDER BY b.mulai"""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return ProductionReport(date=day, batches=[
        BatchReportRow(batch_code=r["kode_batch"], total_output=int(r["total_output"]),
                       ok=r["ok"], ng=r["ng"], events=r["events"]) for r in rows
    ])
