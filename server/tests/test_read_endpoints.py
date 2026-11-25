"""Read endpoints (D2 #3, #4, #6, #7, #8, #10, #11) and POST /shipments (D2 #9) against PRD FR-18..FR-31.

Complements test_api.py: exact error bodies, date handling in WIB, filters, auth and validation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from .conftest import NG_IMG, OK_IMG, WIB, inspect, make_batch, now_iso

API = "/api/v1"


def _passed_batch(client, user, device, code, ok=5, sku="SRD-TOMAT-155G"):
    make_batch(client, user, code, sku)
    for _ in range(ok):
        assert inspect(client, device, code, OK_IMG).status_code == 201
    assert client.post(f"{API}/batches/{code}/close", headers=user).json()["inspectionStatus"] == "PASSED"


def _hold_batch(client, user, device, code):
    make_batch(client, user, code)
    for img in (OK_IMG, NG_IMG):
        assert inspect(client, device, code, img).status_code == 201
    assert client.post(f"{API}/batches/{code}/close", headers=user).json()["inspectionStatus"] == "HOLD"


# ---- POST /shipments (FR-28, FR-29) ---------------------------------------- #
def test_shipment_409_body_lists_hold_batches_at_top_level(client, user, device):
    _passed_batch(client, user, device, "B-OK")
    _hold_batch(client, user, device, "B-NG")
    make_batch(client, user, "B-RUN")  # still running -> HOLD as well
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-9", "batchCodes": ["B-OK", "B-NG", "B-RUN"], "quantity": 3})
    assert r.status_code == 409
    body = r.json()
    assert isinstance(body["detail"], str) and body["detail"]
    assert body["holdBatches"] == ["B-NG", "B-RUN"]
    # Nothing was saved by the rejected request.
    assert client.get(f"{API}/shipments", headers=user).json() == []


def test_shipment_unknown_batch_is_400_with_list(client, user, device):
    _passed_batch(client, user, device, "B-OK2")
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-1", "batchCodes": ["B-OK2", "NOPE"], "quantity": 1})
    assert r.status_code == 400
    assert r.json()["unknownBatches"] == ["NOPE"]


@pytest.mark.parametrize("payload", [
    {"orderId": "PO-1", "batchCodes": [], "quantity": 1},
    {"orderId": "PO-1", "batchCodes": ["B-X"], "quantity": 0},
    {"orderId": "", "batchCodes": ["B-X"], "quantity": 1},
    {"batchCodes": ["B-X"], "quantity": 1},
    {"orderId": "PO-1", "quantity": 1},
])
def test_shipment_invalid_body_is_400(client, user, payload):
    assert client.post(f"{API}/shipments", headers=user, json=payload).status_code == 400


def test_shipment_multiple_batches_and_duplicates(client, user, device):
    _passed_batch(client, user, device, "B-M1", ok=3)
    _passed_batch(client, user, device, "B-M2", ok=4)
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-M", "batchCodes": ["B-M1", "B-M2", "B-M1"], "quantity": 7})
    assert r.status_code == 201
    assert r.json()["batchCodes"] == ["B-M1", "B-M2"]  # duplicate removed
    listing = client.get(f"{API}/shipments", headers=user).json()
    assert listing[0]["batchCodes"] == ["B-M1", "B-M2"] and listing[0]["quantity"] == 7
    only_m2 = client.get(f"{API}/shipments", params={"batchCode": "B-M2"}, headers=user).json()
    assert len(only_m2) == 1


# ---- GET /products/{sku}/availability (FR-18) ------------------------------- #
def test_availability_default_date_is_today_in_wib(client, user):
    body = client.get(f"{API}/products/SRD-TOMAT-155G/availability", headers=user).json()
    assert body["date"] == datetime.now(WIB).date().isoformat()
    assert body["availableQty"] == 0 and body["updatedAt"] is None


def test_availability_filters_by_date_and_sku(client, user, device):
    make_batch(client, user, "B-D1", "SRD-TOMAT-155G")
    make_batch(client, user, "B-D2", "SRD-CABAI-155G")
    yesterday = (datetime.now(WIB) - timedelta(days=1)).isoformat()
    inspect(client, device, "B-D1", OK_IMG)
    inspect(client, device, "B-D1", OK_IMG, yesterday)
    inspect(client, device, "B-D1", NG_IMG)
    inspect(client, device, "B-D2", OK_IMG)

    def qty(sku, **params):
        r = client.get(f"{API}/products/{sku}/availability", params=params, headers=user)
        assert r.status_code == 200
        return r.json()["availableQty"]

    assert qty("SRD-TOMAT-155G") == 1                      # NG and yesterday's can not counted
    assert qty("SRD-TOMAT-155G", date=(datetime.now(WIB) - timedelta(days=1)).date().isoformat()) == 1
    assert qty("SRD-CABAI-155G") == 1                      # other product is separate
    assert qty("SRD-TOMAT-155G", date="2001-01-01") == 0


def test_availability_errors(client, user):
    assert client.get(f"{API}/products/NOPE/availability", headers=user).status_code == 404
    bad = client.get(f"{API}/products/SRD-TOMAT-155G/availability", params={"date": "kemarin"}, headers=user)
    assert bad.status_code == 400


# ---- GET /production/reports (FR-19) --------------------------------------- #
def test_production_report_by_date_and_batch(client, user, device):
    make_batch(client, user, "B-P1")
    make_batch(client, user, "B-P2")
    client.post(f"{API}/production/outputs", headers=device,
                json={"batchCode": "B-P1", "quantity": 4, "timestamp": now_iso()})
    inspect(client, device, "B-P1", OK_IMG)
    inspect(client, device, "B-P2", NG_IMG)
    today = datetime.now(WIB).date().isoformat()

    rep = client.get(f"{API}/production/reports", params={"date": today}, headers=user).json()
    rows = {b["batchCode"]: b for b in rep["batches"]}
    assert rep["date"] == today and set(rows) == {"B-P1", "B-P2"}
    assert (rows["B-P1"]["totalOutput"], rows["B-P1"]["ok"], rows["B-P1"]["ng"]) == (4, 1, 0)
    assert (rows["B-P2"]["totalOutput"], rows["B-P2"]["ok"], rows["B-P2"]["ng"], rows["B-P2"]["events"]) == (0, 0, 1, 1)

    old = client.get(f"{API}/production/reports", params={"date": "2001-01-01"}, headers=user).json()
    assert old == {"date": "2001-01-01", "batches": []}
    one = client.get(f"{API}/production/reports", params={"batchCode": "B-P2"}, headers=user).json()
    assert [b["batchCode"] for b in one["batches"]] == ["B-P2"]


# ---- GET /inspections/alerts (FR-22) --------------------------------------- #
def test_alerts_are_newest_first_filtered_and_limited(client, user, device):
    make_batch(client, user, "B-AL1")
    make_batch(client, user, "B-AL2")
    ids = [inspect(client, device, code, NG_IMG).json()["inspectionId"] for code in ("B-AL1", "B-AL2", "B-AL1")]
    inspect(client, device, "B-AL1", OK_IMG)  # OK is never an alert
    alerts = client.get(f"{API}/inspections/alerts", headers=user)
    assert isinstance(alerts.json(), list)  # bare array, as in D2
    assert [a["inspectionId"] for a in alerts.json()] == ids[::-1]
    assert [a["inspectionId"] for a in client.get(f"{API}/inspections/alerts", params={"limit": 1},
                                                  headers=user).json()] == [ids[-1]]
    only = client.get(f"{API}/inspections/alerts", params={"batchCode": "B-AL2"}, headers=user).json()
    assert [a["inspectionId"] for a in only] == [ids[1]]
    future = (datetime.now(WIB) + timedelta(hours=1)).isoformat()
    assert client.get(f"{API}/inspections/alerts", params={"since": future}, headers=user).json() == []


# ---- GET /batches/inspection-status (FR-27) -------------------------------- #
def test_inspection_status_filters(client, user, device):
    _passed_batch(client, user, device, "B-S-OK", ok=3)
    _hold_batch(client, user, device, "B-S-HOLD")
    _passed_batch(client, user, device, "B-S-CABAI", ok=2, sku="SRD-CABAI-155G")

    def rows(**params):
        r = client.get(f"{API}/batches/inspection-status", params=params, headers=user)
        assert r.status_code == 200
        return {b["batchCode"]: b for b in r.json()["batches"]}

    assert set(rows()) == {"B-S-OK", "B-S-CABAI"}                      # default PASSED
    assert rows()["B-S-OK"]["okQty"] == 3
    assert set(rows(status="HOLD")) == {"B-S-HOLD"}
    assert set(rows(sku="SRD-CABAI-155G")) == {"B-S-CABAI"}
    assert rows(status="HOLD", sku="SRD-CABAI-155G") == {}
    assert client.get(f"{API}/batches/inspection-status", params={"status": "LAIN"},
                      headers=user).status_code == 400


# ---- GET /batches/{batchCode}/inspections (FR-30) -------------------------- #
def test_history_total_counts_all_even_with_filter(client, user, device):
    make_batch(client, user, "B-HF")
    for img in (OK_IMG, OK_IMG, NG_IMG):
        inspect(client, device, "B-HF", img)
    ok = client.get(f"{API}/batches/B-HF/inspections", params={"result": "OK"}, headers=user).json()
    assert (ok["total"], ok["ng"], len(ok["inspections"])) == (3, 1, 2)
    assert client.get(f"{API}/batches/B-HF/inspections", params={"result": "X"}, headers=user).status_code == 400


def test_history_of_batch_without_inspections_is_404(client, user):
    make_batch(client, user, "B-NONE")
    assert client.get(f"{API}/batches/B-NONE/inspections", headers=user).status_code == 404


# ---- authentication on every read endpoint (NF-04) ------------------------- #
@pytest.mark.parametrize("method,path", [
    ("GET", "/products/SRD-TOMAT-155G/availability"),
    ("GET", "/production/reports"),
    ("GET", "/inspections/alerts"),
    ("GET", "/inspections/reports/B-1"),
    ("GET", "/batches/inspection-status"),
    ("GET", "/batches/B-1/inspections"),
    ("GET", "/inspections/1/photo"),
    ("POST", "/shipments"),
])
def test_read_endpoints_require_token(client, device, method, path):
    assert client.request(method, f"{API}{path}").status_code == 401
    # A device key must not open user endpoints.
    assert client.request(method, f"{API}{path}", headers=device).status_code == 401


# ---- Swagger UI (/docs) must offer "Authorize" ------------------------------ #
def test_openapi_declares_security_schemes(client):
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert schemes["HTTPBearer"]["scheme"] == "bearer"
    key = schemes["APIKeyHeader"]
    assert (key["type"], key["in"], key["name"]) == ("apiKey", "header", "X-Device-Key")


def test_bearer_token_still_accepted_and_wrong_scheme_rejected(client, user):
    assert client.get(f"{API}/inspections/alerts", headers=user).status_code == 200
    token = user["Authorization"].split(" ", 1)[1]
    assert client.get(f"{API}/inspections/alerts", headers={"Authorization": f"Basic {token}"}).status_code == 401
