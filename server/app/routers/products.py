"""Products: CRUD (added beyond D2, FR-04) and D2 #3 availability (FR-18)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg2.extensions import connection as PgConnection

from ..db import is_unique_violation
from ..deps import get_conn, require_user
from ..schemas import AvailabilityOut, ProductIn, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(require_user)])


def _row(r: dict) -> ProductOut:
    return ProductOut(sku=r["sku"], name=r["nama"], unit_price=float(r["harga_satuan"]),
                      model_version=r["versi_model"], threshold=r["ambang_batas"])


@router.get("", response_model=list[ProductOut])
def list_products(conn: PgConnection = Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM produk ORDER BY sku")
        return [_row(r) for r in cur.fetchall()]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, conn: PgConnection = Depends(get_conn)):
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s) RETURNING *",
                        (body.sku, body.name, body.unit_price))
            return _row(cur.fetchone())
    except Exception as exc:
        if is_unique_violation(exc):
            raise HTTPException(status.HTTP_409_CONFLICT, f"SKU {body.sku} sudah terdaftar") from exc
        raise


@router.put("/{sku}", response_model=ProductOut)
def update_product(sku: str, body: ProductUpdate, conn: PgConnection = Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("UPDATE produk SET nama = %s, harga_satuan = %s WHERE sku = %s RETURNING *",
                    (body.name, body.unit_price, sku))
        r = cur.fetchone()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Produk {sku} tidak ditemukan")
    return _row(r)


@router.get("/{sku}/availability", response_model=AvailabilityOut)
def availability(sku: str, date_: date | None = Query(default=None, alias="date"),
                 conn: PgConnection = Depends(get_conn)):
    """Cans that passed inspection for this product on the date (shipments not subtracted)."""
    day = date_ or date.today()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM produk WHERE sku = %s", (sku,))
        if cur.fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Produk {sku} tidak ditemukan")
        cur.execute(
            """SELECT count(*) FILTER (WHERE i.hasil = 'OK') AS ok, max(i.waktu) AS last
               FROM inspeksi i JOIN batch b ON b.kode_batch = i.kode_batch
               WHERE b.sku = %s AND i.waktu::date = %s""",
            (sku, day),
        )
        r = cur.fetchone()
    return AvailabilityOut(sku=sku, date=day, available_qty=r["ok"], updated_at=r["last"])
