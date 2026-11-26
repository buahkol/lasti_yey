"""API tests against the D2 contract (K5) and the PRD functional requirements."""

from __future__ import annotations

from datetime import date

from .conftest import NG_IMG, OK_IMG, inspect, make_batch, now_iso

API = "/api/v1"


# ---- Auth (FR-01..03, NF-04) ----------------------------------------------- #
def test_login_ok_and_wrong_password(client):
    r = client.post(f"{API}/auth/login", json={"username": "operasional", "password": "operasional123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["user"]["username"] == "operasional" and "expiresAt" in body
    r = client.post(f"{API}/auth/login", json={"username": "operasional", "password": "salah"})
    assert r.status_code == 401


def test_logout_invalidates_token(client, user):
    assert client.get(f"{API}/products", headers=user).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=user).status_code == 204
    assert client.get(f"{API}/products", headers=user).status_code == 401


def test_user_endpoints_require_token(client, device):
    assert client.get(f"{API}/products").status_code == 401
    assert client.get(f"{API}/inspections/alerts", headers=device).status_code == 401


def test_device_endpoints_require_key(client, user):
    body = {"batchCode": "X", "quantity": 1, "timestamp": now_iso()}
    assert client.post(f"{API}/production/outputs", json=body).status_code == 401
    assert client.post(f"{API}/production/outputs", json=body,
                       headers={"X-Device-Key": "salah"}).status_code == 401
    assert client.post(f"{API}/production/outputs", json=body, headers=user).status_code == 401


# ---- Products & batches (FR-04..06) ---------------------------------------- #
def test_product_crud(client, user):
    r = client.post(f"{API}/products", json={"sku": "SRD-X", "name": "Uji", "unitPrice": 7000}, headers=user)
    assert r.status_code == 201 and r.json()["unitPrice"] == 7000
    assert client.post(f"{API}/products", json={"sku": "SRD-X", "name": "Uji", "unitPrice": 1},
                       headers=user).status_code == 409
    r = client.put(f"{API}/products/SRD-X", json={"name": "Uji 2", "unitPrice": 7500}, headers=user)
    assert r.status_code == 200 and r.json()["name"] == "Uji 2"
    assert client.put(f"{API}/products/NOPE", json={"name": "a", "unitPrice": 1}, headers=user).status_code == 404
    skus = [p["sku"] for p in client.get(f"{API}/products", headers=user).json()]
    assert "SRD-X" in skus


def test_batch_duplicate_and_unknown_product(client, user):
    make_batch(client, user, "B-1")
    r = client.post(f"{API}/batches", json={"batchCode": "B-1", "sku": "SRD-TOMAT-155G"}, headers=user)
    assert r.status_code == 409
    r = client.post(f"{API}/batches", json={"batchCode": "B-2", "sku": "NOPE"}, headers=user)
    assert r.status_code == 400


def test_closed_batch_rejects_data(client, user, device):
    make_batch(client, user, "B-C")
    assert client.post(f"{API}/batches/B-C/close", headers=user).status_code == 200
    assert client.post(f"{API}/batches/B-C/close", headers=user).status_code == 400
    r = client.post(f"{API}/production/outputs", headers=device,
                    json={"batchCode": "B-C", "quantity": 3, "timestamp": now_iso()})
    assert r.status_code == 400
    assert inspect(client, device, "B-C").status_code == 400


# ---- 1. POST /production/outputs (FR-07..09) ------------------------------- #
def test_outputs_accumulate(client, user, device):
    make_batch(client, user, "B-1113-01")
    for qty, expected in ((10, 10), (10, 20), (5, 25)):
        r = client.post(f"{API}/production/outputs", headers=device,
                        json={"batchCode": "B-1113-01", "quantity": qty, "timestamp": now_iso()})
        assert r.status_code == 201
        assert r.json() == {"status": "recorded", "batchCode": "B-1113-01", "totalOutput": expected}


def test_outputs_invalid(client, user, device):
    make_batch(client, user, "B-O")
    bad = [{"batchCode": "NOPE", "quantity": 1, "timestamp": now_iso()},
           {"batchCode": "B-O", "quantity": 0, "timestamp": now_iso()},
           {"batchCode": "B-O", "quantity": 1},
           {"batchCode": "B-O", "quantity": 1, "timestamp": "bukan-waktu"}]
    for body in bad:
        assert client.post(f"{API}/production/outputs", headers=device, json=body).status_code == 400, body


# ---- 2. POST /production/events (FR-17) ------------------------------------ #
def test_events(client, user):
    make_batch(client, user, "B-E")
    r = client.post(f"{API}/production/events", headers=user, json={
        "batchCode": "B-E", "eventType": "BAHAN_BAKU_HABIS", "source": "OPERATOR",
        "timestamp": now_iso(), "note": "Stok kaleng kosong habis"})
    assert r.status_code == 201 and r.json()["status"] == "recorded" and r.json()["eventId"] > 0
    bad = client.post(f"{API}/production/events", headers=user, json={
        "batchCode": "B-E", "eventType": "LAINNYA", "source": "OPERATOR", "timestamp": now_iso()})
    assert bad.status_code == 400
    events = client.get(f"{API}/production/events", params={"batchCode": "B-E"}, headers=user).json()
    assert len(events) == 1 and events[0]["note"] == "Stok kaleng kosong habis"


# ---- 5. POST /inspections (FR-10..13, FR-16) ------------------------------- #
def test_inspection_ok_and_ng(client, user, device):
    make_batch(client, user, "B-I")
    r = inspect(client, device, "B-I", OK_IMG)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"inspectionId", "result", "anomalyScore", "threshold", "reject"}
    assert body["result"] == "OK" and body["reject"] is False and body["threshold"] == 0.5
    r = inspect(client, device, "B-I", NG_IMG)
    assert r.json()["result"] == "NG" and r.json()["reject"] is True
    # FR-16: one REJECT/AI event per NG
    events = client.get(f"{API}/production/events", params={"batchCode": "B-I"}, headers=user).json()
    assert [(e["eventType"], e["source"]) for e in events] == [("REJECT", "AI")]
    assert events[0]["inspectionId"] == r.json()["inspectionId"]


def test_inspection_rejects_non_image(client, user, device):
    make_batch(client, user, "B-N")
    r = client.post(f"{API}/inspections", headers=device, data={"batchCode": "B-N", "timestamp": now_iso()},
                    files={"image": ("x.jpg", b"bukan gambar", "image/jpeg")})
    assert r.status_code == 400
    assert client.get(f"{API}/batches/B-N/inspections", headers=user).status_code == 404  # nothing stored


def test_inspection_unknown_batch_and_missing_fields(client, device):
    assert inspect(client, device, "NOPE").status_code == 400
    r = client.post(f"{API}/inspections", headers=device, data={"batchCode": "X"})
    assert r.status_code == 400


# ---- 6. alerts, 11. photo (FR-22, 23, 31) ---------------------------------- #
def test_alerts_since_and_photo(client, user, device):
    make_batch(client, user, "B-A")
    inspect(client, device, "B-A", OK_IMG)
    first = inspect(client, device, "B-A", NG_IMG).json()
    alerts = client.get(f"{API}/inspections/alerts", headers=user).json()
    assert len(alerts) == 1
    a = alerts[0]
    assert set(a) == {"inspectionId", "batchCode", "anomalyScore", "imageUrl", "timestamp"}
    assert a["imageUrl"] == f"/api/v1/inspections/{first['inspectionId']}/photo"
    newer = client.get(f"{API}/inspections/alerts", params={"since": a["timestamp"]}, headers=user).json()
    assert newer == []
    p = client.get(a["imageUrl"], headers=user)
    assert p.status_code == 200 and p.headers["content-type"] == "image/jpeg" and p.content == NG_IMG
    assert client.get(a["imageUrl"].replace("/photo", "/image"), headers=user).status_code == 200
    t = client.get(a["imageUrl"], params={"size": "thumb"}, headers=user)
    assert t.status_code == 200 and t.content[:3] == b"\xff\xd8\xff"
    assert client.get(f"{API}/inspections/999999/photo", headers=user).status_code == 404


# ---- 7. batch inspection report (FR-24) ------------------------------------ #
def test_batch_report_loss_and_hours(client, user, device):
    make_batch(client, user, "B-R", "SRD-TOMAT-155G")  # 6000 per can
    for hour, img in ((8, NG_IMG), (9, NG_IMG), (9, NG_IMG), (9, OK_IMG), (10, OK_IMG)):
        assert inspect(client, device, "B-R", img, now_iso(hour)).status_code == 201
    r = client.get(f"{API}/inspections/reports/B-R", headers=user)
    assert r.status_code == 200
    body = r.json()
    assert (body["total"], body["ok"], body["ng"]) == (5, 2, 3)
    assert body["ngPerHour"] == {"08": 1, "09": 2}
    assert body["estimatedLoss"] == 18000
    assert body["ngPercent"] == 60.0
    assert client.get(f"{API}/inspections/reports/NOPE", headers=user).status_code == 404


# ---- 8. status + close rule (FR-26, 27) ------------------------------------ #
def test_batch_status_rule(client, user, device):
    make_batch(client, user, "B-PASS")
    make_batch(client, user, "B-HOLD")
    for _ in range(20):
        inspect(client, device, "B-PASS", OK_IMG)
    inspect(client, device, "B-PASS", NG_IMG)  # 1/21 = 4.8% <= 5%
    for img in (OK_IMG, OK_IMG, NG_IMG):  # 33% > 5%
        inspect(client, device, "B-HOLD", img)

    running = client.get(f"{API}/batches/inspection-status", params={"status": "HOLD"}, headers=user).json()
    assert {b["batchCode"] for b in running["batches"]} == {"B-PASS", "B-HOLD"}

    assert client.post(f"{API}/batches/B-PASS/close", headers=user).json()["inspectionStatus"] == "PASSED"
    assert client.post(f"{API}/batches/B-HOLD/close", headers=user).json()["inspectionStatus"] == "HOLD"

    passed = client.get(f"{API}/batches/inspection-status", headers=user).json()  # default PASSED
    assert passed == {"batches": [{"batchCode": "B-PASS", "sku": "SRD-TOMAT-155G",
                                   "status": "PASSED", "okQty": 20}]}
    other = client.get(f"{API}/batches/inspection-status", params={"sku": "SRD-CABAI-155G"},
                       headers=user).json()
    assert other == {"batches": []}


def test_empty_batch_closes_as_hold(client, user):
    make_batch(client, user, "B-EMPTY")
    assert client.post(f"{API}/batches/B-EMPTY/close", headers=user).json()["inspectionStatus"] == "HOLD"


# ---- 9. shipments (FR-28, 29) ---------------------------------------------- #
def test_shipments(client, user, device):
    make_batch(client, user, "B-S1")
    make_batch(client, user, "B-S2")
    for _ in range(5):
        inspect(client, device, "B-S1", OK_IMG)
    inspect(client, device, "B-S2", NG_IMG)
    client.post(f"{API}/batches/B-S1/close", headers=user)
    client.post(f"{API}/batches/B-S2/close", headers=user)

    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-1", "batchCodes": ["B-S1", "B-S2"], "quantity": 3})
    assert r.status_code == 409 and r.json()["holdBatches"] == ["B-S2"]
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-1", "batchCodes": ["NOPE"], "quantity": 3})
    assert r.status_code == 400
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-1", "batchCodes": ["B-S1"], "quantity": 99})
    assert r.status_code == 400
    r = client.post(f"{API}/shipments", headers=user,
                    json={"orderId": "PO-1113-07", "batchCodes": ["B-S1"], "quantity": 5})
    assert r.status_code == 201
    assert r.json() == {"shipmentId": r.json()["shipmentId"], "orderId": "PO-1113-07",
                        "batchCodes": ["B-S1"], "status": "recorded"}
    lst = client.get(f"{API}/shipments", headers=user).json()
    assert lst[0]["orderId"] == "PO-1113-07" and lst[0]["quantity"] == 5


# ---- 10. history (FR-30) --------------------------------------------------- #
def test_history_filter_and_404(client, user, device):
    make_batch(client, user, "B-H")
    inspect(client, device, "B-H", OK_IMG)
    inspect(client, device, "B-H", NG_IMG)
    r = client.get(f"{API}/batches/B-H/inspections", headers=user).json()
    assert (r["batchCode"], r["total"], r["ng"], len(r["inspections"])) == ("B-H", 2, 1, 2)
    assert set(r["inspections"][0]) == {"inspectionId", "result", "anomalyScore", "timestamp"}
    ng = client.get(f"{API}/batches/B-H/inspections", params={"result": "NG"}, headers=user).json()
    assert [i["result"] for i in ng["inspections"]] == ["NG"]
    assert client.get(f"{API}/batches/NOPE/inspections", headers=user).status_code == 404


# ---- 3. availability, 4. production report (FR-18, 19) --------------------- #
def test_availability_and_production_report(client, user, device):
    make_batch(client, user, "B-AV")
    client.post(f"{API}/production/outputs", headers=device,
                json={"batchCode": "B-AV", "quantity": 3, "timestamp": now_iso()})
    for img in (OK_IMG, OK_IMG, NG_IMG):
        inspect(client, device, "B-AV", img)
    r = client.get(f"{API}/products/SRD-TOMAT-155G/availability", headers=user)
    assert r.status_code == 200
    body = r.json()
    assert body["sku"] == "SRD-TOMAT-155G" and body["availableQty"] == 2 and body["updatedAt"]
    assert body["date"] == date.today().isoformat()
    assert client.get(f"{API}/products/NOPE/availability", headers=user).status_code == 404

    rep = client.get(f"{API}/production/reports", headers=user).json()
    assert rep["date"] == date.today().isoformat()
    assert rep["batches"] == [{"batchCode": "B-AV", "totalOutput": 3, "ok": 2, "ng": 1, "events": 1}]
    one = client.get(f"{API}/production/reports", params={"batchCode": "B-AV"}, headers=user).json()
    assert len(one["batches"]) == 1


# ---- dev capture ----------------------------------------------------------- #
def test_dev_capture(client, device, settings):
    r = client.post(f"{API}/dev/capture", headers=device,
                    data={"sku": "SRD-TOMAT-155G", "label": "ok", "canId": "c001"},
                    files={"image": ("k.jpg", OK_IMG, "image/jpeg")})
    assert r.status_code == 201 and r.json()["count"] == 1
    assert (settings.dataset_dir / r.json()["path"]).read_bytes() == OK_IMG


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200 and r.json()["modelBackend"] == "stub"
