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


def test_greeting_follows_time():
    from src.controllers.dashboard_controller import DashboardController
    greetings = [DashboardController.greeting(datetime(2026, 11, 25, h)) for h in (6, 12, 16, 19, 2)]
    assert greetings == ["Selamat pagi", "Selamat siang", "Selamat sore", "Selamat malam", "Selamat malam"]


def test_record_event_accepts_typed_kind():
    c = make()
    result = c.events.record("B-2411-02", "Pemadaman listrik", "Listrik padam 10 menit", datetime(2026, 11, 25, 10, 50))
    assert result.errors == {}
    assert c.events.events("B-2411-02")[0].kind == "PEMADAMAN_LISTRIK"
    assert ("PEMADAMAN_LISTRIK", "Pemadaman listrik", "Diketik sebelumnya") in c.events.kind_suggestions()
    assert c.events.record("B-2411-02", "alat berhenti", "").event.kind == "ALAT_BERHENTI"
    assert "kind" in c.events.record("B-2411-02", "  ", "").errors


def test_alert_time_windows_grow_with_the_window():
    c = make()
    counts = c.alerts.counts()
    assert counts == sorted(counts) and counts[0] == 7
    summary = c.alerts.summary(0)
    assert summary.count == 7 and summary.top.score == 0.93
    assert summary.batches == ["B-2411-01", "B-2411-02"]
