"""Batch lifecycle rules under concurrency, plus error paths the main API tests do not reach."""

from __future__ import annotations

import threading
import time
from datetime import date

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.app.main import create_app
from server.app.ml.inspector import ModelUnavailable, StubInspector

from .conftest import NG_IMG, OK_IMG, inspect, make_batch, now_iso

API = "/api/v1"


def _hold_close_in_progress(settings, batch_code: str):
    """Open a transaction that has locked the batch and marked it closed, like close_batch mid-flight."""
    conn = psycopg2.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
                            user=settings.db_user, password=settings.db_password)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM batch WHERE kode_batch = %s FOR UPDATE", (batch_code,))
        cur.execute("UPDATE batch SET status_batch = 'DITUTUP', selesai = now() WHERE kode_batch = %s",
                    (batch_code,))
    return conn


def _run_while_close_pending(settings, batch_code, request):
    """Fire ``request`` while a close is uncommitted; return (response, was_blocked_before_commit)."""
    close_tx = _hold_close_in_progress(settings, batch_code)
    out: dict = {}
    t = threading.Thread(target=lambda: out.update(r=request()))
    t.start()
    time.sleep(0.7)
    blocked = t.is_alive()
    close_tx.commit()
    close_tx.close()
    t.join(10)
    assert not t.is_alive(), "request never finished after the close committed"
    return out["r"], blocked


def test_inspection_started_before_close_is_refused_not_orphaned(client, user, device, settings):
    """An inspection must not slip into a batch that is being closed (its NG would be uncounted)."""
    make_batch(client, user, "B-RACE")
    r, blocked = _run_while_close_pending(settings, "B-RACE", lambda: inspect(client, device, "B-RACE", NG_IMG))
    assert blocked, "the write should wait for the close instead of racing it"
    assert r.status_code == 400
    assert client.get(f"{API}/batches/B-RACE/inspections", headers=user).status_code == 404  # none stored
    assert not any(p.parent.name == "B-RACE" for p in settings.image_dir.rglob("*.jpg")), "orphan image left"
    events = client.get(f"{API}/production/events", params={"batchCode": "B-RACE"}, headers=user).json()
    assert events == []


def test_output_started_before_close_is_refused(client, user, device, settings):
    make_batch(client, user, "B-RACE2")
    body = {"batchCode": "B-RACE2", "quantity": 5, "timestamp": now_iso()}
    r, blocked = _run_while_close_pending(
        settings, "B-RACE2", lambda: client.post(f"{API}/production/outputs", headers=device, json=body))
    assert blocked
    assert r.status_code == 400


def test_close_counts_every_inspection_that_was_accepted(client, user, device):
    """Status is computed from the same rows that were accepted: 1 NG in 21 stays within 5%."""
    make_batch(client, user, "B-CNT")
    for _ in range(20):
        assert inspect(client, device, "B-CNT", OK_IMG).status_code == 201
    assert inspect(client, device, "B-CNT", NG_IMG).status_code == 201
    closed = client.post(f"{API}/batches/B-CNT/close", headers=user).json()
    assert (closed["total"], closed["ng"], closed["inspectionStatus"]) == (21, 1, "PASSED")
    assert inspect(client, device, "B-CNT", NG_IMG).status_code == 400  # refused after close


# ---- Error paths ------------------------------------------------------------ #
class _NoModelInspector(StubInspector):
    def inspect(self, sku, image):
        raise ModelUnavailable(sku)


def test_inspection_503_when_model_missing(settings):
    with TestClient(create_app(settings, _NoModelInspector())) as c:
        tok = c.post(f"{API}/auth/login", json={"username": "operasional", "password": "operasional123"}).json()
        user = {"Authorization": f"Bearer {tok['token']}"}
        device = {"X-Device-Key": "simonpro-dev-key-01"}
        make_batch(c, user, "B-503")
        r = inspect(c, device, "B-503")
        assert r.status_code == 503
        assert c.get(f"{API}/batches/B-503/inspections", headers=user).status_code == 404  # nothing stored


def test_operator_cannot_record_reject_but_device_can(client, user, device):
    make_batch(client, user, "B-REJ")
    body = {"batchCode": "B-REJ", "eventType": "REJECT", "source": "OPERATOR", "timestamp": now_iso()}
    assert client.post(f"{API}/production/events", headers=user, json=body).status_code == 400
    assert client.post(f"{API}/production/events", headers=device, json=body).status_code == 201
    assert client.post(f"{API}/production/events", headers=user,
                       json={**body, "batchCode": "NOPE", "eventType": "RATE_DROP"}).status_code == 400


def test_event_filters(client, user):
    make_batch(client, user, "B-EV")
    for kind in ("BAHAN_BAKU_HABIS", "ALAT_BERHENTI", "ALAT_BERHENTI"):
        r = client.post(f"{API}/production/events", headers=user, json={
            "batchCode": "B-EV", "eventType": kind, "source": "OPERATOR", "timestamp": now_iso()})
        assert r.status_code == 201
    base = {"batchCode": "B-EV"}
    assert len(client.get(f"{API}/production/events", params=base, headers=user).json()) == 3
    stops = client.get(f"{API}/production/events", params={**base, "eventType": "ALAT_BERHENTI"},
                       headers=user).json()
    assert len(stops) == 2 and {e["eventType"] for e in stops} == {"ALAT_BERHENTI"}
    today = client.get(f"{API}/production/events", params={**base, "date": date.today().isoformat()},
                       headers=user).json()
    assert len(today) == 3
    assert client.get(f"{API}/production/events", params={**base, "date": "2001-01-01"},
                      headers=user).json() == []
    assert len(client.get(f"{API}/production/events", params={**base, "limit": 1}, headers=user).json()) == 1


def test_batch_list_filters(client, user):
    make_batch(client, user, "B-L1", "SRD-TOMAT-155G")
    make_batch(client, user, "B-L2", "SRD-CABAI-155G")
    client.post(f"{API}/batches/B-L1/close", headers=user)

    def codes(**params):
        return [b["batchCode"] for b in client.get(f"{API}/batches", params=params, headers=user).json()]

    assert sorted(codes()) == ["B-L1", "B-L2"]
    assert codes(status="DITUTUP") == ["B-L1"]
    assert codes(status="BERJALAN") == ["B-L2"]
    assert codes(sku="SRD-CABAI-155G") == ["B-L2"]
    assert codes(status="DITUTUP", sku="SRD-CABAI-155G") == []
    assert client.get(f"{API}/batches/B-L1", headers=user).json()["batchStatus"] == "DITUTUP"
    assert client.get(f"{API}/batches/NOPE", headers=user).status_code == 404
    assert client.post(f"{API}/batches/NOPE/close", headers=user).status_code == 404


@pytest.mark.parametrize("path", ["/inspections/alerts", "/production/reports", "/batches"])
def test_read_endpoints_return_401_without_token(client, path):
    assert client.get(f"{API}{path}").status_code == 401


def test_device_follows_the_newest_running_batch(client, user, device):
    """GET /devices/current-batch: the device follows what the operator opens and closes in the app."""
    url = f"{API}/devices/current-batch"
    assert client.get(url).status_code == 401                       # device key required
    assert client.get(url, headers=device).json() == {"batchCode": None, "sku": None}
    make_batch(client, user, "B-DEV-1")
    make_batch(client, user, "B-DEV-2", sku="SRD-CABAI-155G")
    assert client.get(url, headers=device).json() == {"batchCode": "B-DEV-2", "sku": "SRD-CABAI-155G"}
    assert client.get(url, params={"sku": "SRD-TOMAT-155G"}, headers=device).json()["batchCode"] == "B-DEV-1"
    client.post(f"{API}/batches/B-DEV-2/close", headers=user)
    assert client.get(url, headers=device).json()["batchCode"] == "B-DEV-1"
