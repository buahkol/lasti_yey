"""Business rules and shared queries."""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from psycopg2.extensions import connection as PgConnection


def compute_inspection_status(batch_status: str, total: int, ng: int, tolerance: float) -> str:
    """FR-26: HOLD while running or when NG% exceeds tolerance; PASSED once closed and within it."""
    if batch_status != "DITUTUP" or total == 0:
        return "HOLD"
    return "PASSED" if ng / total <= tolerance else "HOLD"


def get_batch(conn: PgConnection, batch_code: str, for_update: bool = False) -> dict | None:
    sql = """SELECT b.*, p.nama AS nama_produk, p.harga_satuan
             FROM batch b JOIN produk p ON p.sku = b.sku WHERE b.kode_batch = %s"""
    if for_update:
        sql += " FOR UPDATE OF b"
    with conn.cursor() as cur:
        cur.execute(sql, (batch_code,))
        return cur.fetchone()


def require_open_batch(conn: PgConnection, batch_code: str) -> dict:
    """400 for unknown or closed batches (FR-06, FR-09)."""
    batch = get_batch(conn, batch_code)
    if batch is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Kode batch {batch_code} tidak terdaftar")
    if batch["status_batch"] != "BERJALAN":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Batch {batch_code} sudah ditutup")
    return batch


def inspection_counts(conn: PgConnection, batch_code: str) -> tuple[int, int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) AS total,
                      count(*) FILTER (WHERE hasil = 'OK') AS ok,
                      count(*) FILTER (WHERE hasil = 'NG') AS ng
               FROM inspeksi WHERE kode_batch = %s""",
            (batch_code,),
        )
        r = cur.fetchone()
    return r["total"], r["ok"], r["ng"]


BATCH_LIST_SQL = """
SELECT b.kode_batch, b.sku, p.nama AS nama_produk, b.status_batch, b.status_inspeksi,
       b.mulai, b.selesai,
       COALESCE(o.total_output, 0) AS total_output,
       COALESCE(i.total, 0) AS total, COALESCE(i.ok, 0) AS ok, COALESCE(i.ng, 0) AS ng
FROM batch b
JOIN produk p ON p.sku = b.sku
LEFT JOIN (SELECT kode_batch, sum(jumlah) AS total_output FROM output_produksi GROUP BY kode_batch) o
       ON o.kode_batch = b.kode_batch
LEFT JOIN (SELECT kode_batch, count(*) AS total,
                  count(*) FILTER (WHERE hasil = 'OK') AS ok,
                  count(*) FILTER (WHERE hasil = 'NG') AS ng
           FROM inspeksi GROUP BY kode_batch) i
       ON i.kode_batch = b.kode_batch
"""


def batch_row_to_api(r: dict) -> dict:
    return {
        "batch_code": r["kode_batch"], "sku": r["sku"], "product_name": r["nama_produk"],
        "batch_status": r["status_batch"], "inspection_status": r["status_inspeksi"],
        "started_at": r["mulai"], "ended_at": r["selesai"], "total_output": int(r["total_output"]),
        "total": int(r["total"]), "ok": int(r["ok"]), "ng": int(r["ng"]),
    }


# ---- Images ---------------------------------------------------------------- #
def decode_image(data: bytes) -> Image.Image:
    """FR-13: reject files that are not readable images with 400."""
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Berkas gambar kosong")
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Berkas bukan gambar yang dapat dibaca") from exc
    return img.convert("RGB")


def save_image(image_dir: Path, batch_code: str, taken_at: datetime, data: bytes, img: Image.Image) -> str:
    """Store the original JPEG (re-encode non-JPEG uploads). Returns path relative to image_dir."""
    rel = Path(taken_at.strftime("%Y-%m-%d")) / batch_code / f"{taken_at:%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
    dest = image_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if data[:3] == b"\xff\xd8\xff":
        dest.write_bytes(data)
    else:
        img.save(dest, "JPEG", quality=92)
    return str(rel)


def thumbnail_path(image_dir: Path, rel: str, size: int = 240) -> Path:
    src = image_dir / rel
    thumb = image_dir / ".thumbs" / Path(rel).with_suffix(f".{size}.jpg")
    if not thumb.exists():
        thumb.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            im.save(thumb, "JPEG", quality=85)
    return thumb
