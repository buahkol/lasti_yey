from datetime import datetime

from src.controllers import Controllers


def make():
    return Controllers.create(use_api=False)


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


def test_history_folders_hold_ok_and_ng_photos():
    c = make()
    folders = c.history.folders()
    assert len(folders) == len(c.batches.search())
    assert c.history.counts("B-2411-02") == [640, 598, 42]
    photos, pages, total = c.history.photos("B-2411-02", "NG")
    assert total == 42 and pages == 3 and all(p.result == "NG" for p in photos)
    ok, _, ok_total = c.history.photos("B-2411-02", "OK", page=99)
    assert ok_total == 598 and all(p.result == "OK" and p.score < p.threshold for p in ok)
    assert [f.batch.code for f in c.history.folders("cabai")] == [f.batch.code for f in folders
                                                                   if "cabai" in f.batch.product]
    assert c.history.folder(" b-2410-21 ").batch.code == "B-2410-21"
