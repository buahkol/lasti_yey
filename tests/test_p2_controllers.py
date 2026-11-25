from datetime import datetime

from src.controllers import Controllers


def make():
    return Controllers.create()


def test_record_event_on_running_batch():
    c = make()
    before = len(c.events.events("B-2411-02"))
    result = c.events.record("B-2411-02", "BAHAN_BAKU_HABIS", "Menunggu label", datetime(2026, 11, 25, 10, 48))
    assert result.errors == {}
    events = c.events.events("B-2411-02")
    assert len(events) == before + 1
    assert events[0].time == "10.48" and events[0].source == "Operator"


def test_record_event_rejects_closed_batch_and_reject_kind():
    c = make()
    assert "batch" in c.events.record("B-2410-28", "ALAT_BERHENTI", "").errors
    assert "kind" in c.events.record("B-2411-02", "REJECT", "").errors


def test_shipment_only_offers_passed_batches():
    c = make()
    codes = [b.code for b in c.shipments.passed_batches()]
    assert "B-2410-26" not in codes
    assert "B-2411-01" not in codes


def test_shipment_saved_with_batch_codes():
    c = make()
    result = c.shipments.submit("po-2611-018", ["B-2410-28", "B-2410-27"], "1.200")
    assert result.shipment is not None
    assert result.shipment.order_id == "PO-2611-018"
    assert result.shipment.quantity == 1200
    assert c.shipments.shipments()[0].batch_codes == ["B-2410-28", "B-2410-27"]


def test_shipment_with_hold_batch_is_rejected():
    c = make()
    result = c.shipments.submit("PO-2611-019", ["B-2410-28", "B-2410-26"], "50")
    assert result.shipment is None
    assert result.hold_batches == ["B-2410-26"]


def test_shipment_validation_errors():
    result = make().shipments.submit("", [], "nol")
    assert set(result.errors) == {"order", "batches", "quantity"}


def test_history_counts_match_batch_and_filter():
    c = make()
    h = c.history.find(" b-2410-24 ")
    batch = h.batch
    assert (h.total, h.ng, h.ok) == (batch.output, batch.ng_count, batch.ok_count)
    assert all(r.result == "NG" for r in c.history.filtered(h, "NG"))
    assert len(c.history.filtered(h, "OK")) == h.ok
    times = [r.timestamp for r in h.rows]
    assert times == sorted(times, reverse=True)


def test_history_unknown_batch_is_not_found():
    assert make().history.find("B-2499-01") is None
