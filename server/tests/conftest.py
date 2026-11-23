"""Test fixtures: a fresh schema in the configured Postgres + the brightness stub model.

Needs a reachable Postgres (DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD, same as the
app). WARNING: the target database's public schema is dropped and recreated.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.app.config import Settings
from server.app.main import create_app
from server.app.ml.inspector import StubInspector

ROOT = Path(__file__).resolve().parents[2]
DEVICE_KEY = "simonpro-dev-key-01"
WIB = timezone(timedelta(hours=7))


def _settings(tmp: Path) -> Settings:
    return Settings(
        db_host=os.environ.get("DB_HOST", "localhost"),
        db_port=int(os.environ.get("DB_PORT", "5433")),
        db_name=os.environ.get("DB_NAME", "simonpro_test"),
        db_user=os.environ.get("DB_USER", "postgres"),
        db_password=os.environ.get("DB_PASSWORD", "secret"),
        model_backend="stub",
        image_dir=tmp / "images",
        dataset_dir=tmp / "dataset",
        enable_dev_capture=True,
    )


@pytest.fixture(scope="session")
def settings(tmp_path_factory) -> Settings:
    s = _settings(tmp_path_factory.mktemp("simonpro"))
    conn = psycopg2.connect(host=s.db_host, port=s.db_port, dbname=s.db_name, user=s.db_user,
                            password=s.db_password)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute((ROOT / "database" / "init.sql").read_text())
        cur.execute((ROOT / "database" / "dummy.sql").read_text())
    conn.close()
    return s


@pytest.fixture(scope="session")
def app_client(settings):
    app = create_app(settings, StubInspector(threshold=0.5))
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_tables(settings):
    conn = psycopg2.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
                            user=settings.db_user, password=settings.db_password)
    with conn, conn.cursor() as cur:
        cur.execute("""TRUNCATE pengiriman_batch, pengiriman, kejadian_produksi, inspeksi,
                       output_produksi, batch, sesi RESTART IDENTITY CASCADE""")
    conn.close()


@pytest.fixture
def client(app_client):
    return app_client


@pytest.fixture
def token(client) -> str:
    r = client.post("/api/v1/auth/login", json={"username": "operasional", "password": "operasional123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def user(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def device() -> dict:
    return {"X-Device-Key": DEVICE_KEY}


def jpeg(brightness: int) -> bytes:
    """Stub model: score = brightness/255, threshold 0.5. 230 -> NG, 20 -> OK."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (brightness,) * 3).save(buf, "JPEG")
    return buf.getvalue()


OK_IMG = jpeg(20)
NG_IMG = jpeg(230)


def now_iso(hour: int | None = None) -> str:
    t = datetime.now(WIB)
    if hour is not None:
        t = t.replace(hour=hour, minute=5, second=0, microsecond=0)
    return t.isoformat()


def make_batch(client, user, code="B-TEST-01", sku="SRD-TOMAT-155G") -> dict:
    r = client.post("/api/v1/batches", json={"batchCode": code, "sku": sku}, headers=user)
    assert r.status_code == 201, r.text
    return r.json()


def inspect(client, device, code, img=OK_IMG, ts=None):
    return client.post("/api/v1/inspections", headers=device,
                       data={"batchCode": code, "timestamp": ts or now_iso()},
                       files={"image": ("kaleng.jpg", img, "image/jpeg")})
