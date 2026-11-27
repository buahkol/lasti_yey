"""Sample data that matches the Figma screens.

Used by the services until the REST API (/api/v1) is connected. Each block
names the endpoint that will provide it.
"""

from datetime import date, datetime

from ..models import Alert, Batch, Product, ProductionEvent, User

TODAY = date(2026, 11, 25)

# POST /auth/login (FR-01). Prototype account until the server is connected.
DEMO_PASSWORD = "simonpro"
DEMO_USER = User("operasional", "Operasional", "Shift pagi, Lini 1", "OP")

DEVICE = {"name": "ESP32-CAM", "ip": "192.168.1.42", "seconds_per_can": 0.8, "connected": True}

# GET /products + GET /products/{sku}/availability
PRODUCTS = [
    Product("SDN-TMT-155", "Sarden saus tomat 155 g", 12500, 0.62, "pc-v2.1", "BERJALAN", 1228, 98.2, "pukul 10.42", 2),
    Product("SDN-CBI-155", "Sarden saus cabai 155 g", 13000, 0.64, "pc-v2.1", "BERJALAN", 598, 93.4, "pukul 10.36", 1),
    Product("SDN-MNY-425", "Sarden minyak nabati 425 g", 27500, 0.58, "pc-v1.4", "DITUTUP", 972, 99.2, "kemarin", 1),
]


def _batch(code, sku, product, when, duration, output, ng, status, inspection):
    return Batch(code, sku, product, datetime.strptime(when, "%Y-%m-%d %H.%M"), duration, output, ng, status, inspection)


_TMT, _CBI, _MNY = "Sarden saus tomat 155 g", "Sarden saus cabai 155 g", "Sarden minyak nabati 425 g"

# GET /batches/inspection-status
BATCHES = [
    _batch("B-2411-01", "SDN-TMT-155", _TMT, "2026-11-25 07.02", "berjalan 4 jam", 1250, 1.8, "BERJALAN", "HOLD"),
    _batch("B-2411-02", "SDN-CBI-155", _CBI, "2026-11-25 07.30", "berjalan 3 jam", 640, 6.6, "BERJALAN", "HOLD"),
    _batch("B-2410-28", "SDN-MNY-425", _MNY, "2026-11-24 08.10", "8 jam", 980, 0.8, "DITUTUP", "PASSED"),
    _batch("B-2410-27", "SDN-CBI-155", _CBI, "2026-11-24 07.45", "7 jam 35 menit", 760, 2.4, "DITUTUP", "PASSED"),
    _batch("B-2410-26", "SDN-TMT-155", _TMT, "2026-11-23 07.00", "8 jam", 1410, 6.5, "DITUTUP", "HOLD"),
    _batch("B-2410-25", "SDN-MNY-425", _MNY, "2026-11-23 08.00", "6 jam 40 menit", 860, 1.0, "DITUTUP", "PASSED"),
    _batch("B-2410-24", "SDN-TMT-155", _TMT, "2026-11-23 07.10", "7 jam 55 menit", 1322, 4.2, "DITUTUP", "PASSED"),
    _batch("B-2410-23", "SDN-CBI-155", _CBI, "2026-11-24 13.20", "5 jam 10 menit", 690, 3.1, "DITUTUP", "PASSED"),
    _batch("B-2410-22", "SDN-TMT-155", _TMT, "2026-11-24 14.05", "6 jam", 1180, 2.0, "DITUTUP", "PASSED"),
    _batch("B-2410-21", "SDN-MNY-425", _MNY, "2026-11-23 13.40", "5 jam 30 menit", 720, 5.8, "DITUTUP", "HOLD"),
    _batch("B-2410-20", "SDN-CBI-155", _CBI, "2026-11-23 14.10", "6 jam 15 menit", 810, 1.6, "DITUTUP", "PASSED"),
    _batch("B-2410-19", "SDN-TMT-155", _TMT, "2026-11-23 15.00", "5 jam 45 menit", 1050, 2.9, "DITUTUP", "PASSED"),
]

# GET /inspections/alerts
# Sample clock: the screens show the state at 25 Nov 2026, 10.45.
NOW = datetime(2026, 11, 25, 10, 45)


_ALERT_PRODUCT = {"SDN-TMT-155": (0.62, _TMT), "SDN-CBI-155": (0.64, _CBI), "SDN-MNY-425": (0.58, _MNY)}


def _alert(batch: str, time: str, score: float, defect: str, day: date = TODAY) -> Alert:
    sku = next(b.sku for b in BATCHES if b.code == batch)
    threshold, product = _ALERT_PRODUCT[sku]
    at = datetime.combine(day, datetime.strptime(time, "%H.%M.%S").time())
    return Alert(batch, time, score, threshold, defect, product, at)


_NOV24, _NOV23 = date(2026, 11, 24), date(2026, 11, 23)


ALERTS = [
    _alert("B-2411-01", "10.42.07", 0.87, "dent"),
    _alert("B-2411-01", "10.39.51", 0.81, "label"),
    _alert("B-2411-02", "10.36.14", 0.93, "rust"),
    _alert("B-2411-02", "10.33.40", 0.77, "dent"),
    _alert("B-2411-01", "10.31.02", 0.74, "label"),
    _alert("B-2411-02", "10.27.18", 0.70, "rust"),
    _alert("B-2411-01", "10.15.44", 0.68, "dent"),
    _alert("B-2411-02", "10.06.25", 0.79, "label"),
    _alert("B-2411-01", "09.58.12", 0.72, "dent"),
    _alert("B-2411-02", "09.51.37", 0.88, "rust"),
    _alert("B-2411-02", "09.20.03", 0.71, "dent"),
    _alert("B-2411-01", "08.47.55", 0.66, "label"),
    _alert("B-2411-02", "08.12.48", 0.75, "rust"),
    _alert("B-2411-01", "07.36.20", 0.69, "dent"),
    _alert("B-2411-02", "07.24.09", 0.82, "label"),
    # Earlier days: alerts are kept without a time limit so a batch can be traced later.
    _alert("B-2410-27", "14.52.30", 0.78, "dent", _NOV24),
    _alert("B-2410-23", "16.05.12", 0.73, "label", _NOV24),
    _alert("B-2410-27", "11.18.44", 0.84, "rust", _NOV24),
    _alert("B-2410-28", "09.40.03", 0.66, "dent", _NOV24),
    _alert("B-2410-21", "17.22.51", 0.91, "rust", _NOV23),
    _alert("B-2410-26", "13.47.09", 0.86, "dent", _NOV23),
    _alert("B-2410-26", "11.02.36", 0.79, "label", _NOV23),
    _alert("B-2410-21", "15.31.20", 0.74, "dent", _NOV23),
    _alert("B-2410-24", "09.15.58", 0.70, "label", _NOV23),
]
ALERT_SUMMARY = {"ng_30min": 7, "ng_delta": "+3", "since": "10.12", "avg_score": 0.80,
                 "top_score": 0.93, "top_batch": "B-2411-02", "top_time": "10.36", "affected_batches": 2}

# GET /production/reports (dashboard)
DASHBOARD_STATS = {
    "output": 1250, "output_delta": "+180", "output_since": "09.00",
    "ok": 1228, "ok_percent": 98.2,
    "ng": 22, "ng_percent": 1.8,
    "events": 26, "events_reject": 22,
}
# (hour label, OK count, NG count); 18.00 has no data yet
OUTPUT_PER_HOUR = [
    ("07.00", 60, 1), ("08.00", 96, 2), ("09.00", 118, 3), ("10.00", 132, 1), ("11.00", 145, 4),
    ("12.00", 138, 2), ("13.00", 120, 5), ("14.00", 64, 1), ("15.00", 150, 2), ("16.00", 142, 1),
    ("17.00", 136, 1), ("18.00", 0, 0),
]
CURRENT_HOUR_INDEX = 4
ACTIVE_BATCH_STARTED = "07.02"

# GET /inspections/reports/{batchCode}
BATCH_REPORTS = {
    "B-2411-02": {
        "date": "25 Nov 2026", "window": "07.30 sampai 14.50", "total": 640, "ok": 598, "ng": 42,
        "events": 44, "events_reject": 42, "events_manual": 2,
        # (hour, NG count, output in that hour)
        "ng_per_hour": [("07.00", 3, 60), ("08.00", 4, 78), ("09.00", 5, 84), ("10.00", 9, 96), ("11.00", 7, 88),
                        ("12.00", 5, 70), ("13.00", 4, 66), ("14.00", 3, 58), ("15.00", 2, 40)],
        "events_list": [
            ProductionEvent("10.42", "REJECT", "AI", "Skor 0,87 melewati ambang 0,62"),
            ProductionEvent("10.36", "REJECT", "AI", "Skor 0,93 melewati ambang 0,64"),
            ProductionEvent("09.58", "ALAT_BERHENTI", "Operator", "Penyetelan ulang penahan kaleng selama 6 menit"),
            ProductionEvent("09.12", "BAHAN_BAKU_HABIS", "Operator", "Menunggu kiriman label selama 8 menit"),
            ProductionEvent("08.47", "REJECT", "AI", "Skor 0,72 melewati ambang 0,64"),
            ProductionEvent("08.15", "REJECT", "AI", "Skor 0,69 melewati ambang 0,64"),
        ],
        "top_scores": [Alert("B-2411-02", "10.36.14", 0.93, 0.64, "rust", _CBI),
                       Alert("B-2411-02", "10.33.40", 0.77, 0.64, "dent", _CBI),
                       Alert("B-2411-02", "10.12.30", 0.72, 0.64, "label", _CBI)],
    },
}



def _event(time, kind, note):
    return ProductionEvent(time, kind, "AI" if kind == "REJECT" else "Operator", note)


EVENTS = {
    "B-2411-02": [
        _event("10.42", "REJECT", "Skor 0,87 melewati ambang 0,64"),
        _event("10.36", "REJECT", "Skor 0,93 melewati ambang 0,64"),
        _event("10.12", "REJECT", "Skor 0,77 melewati ambang 0,64"),
        _event("09.58", "ALAT_BERHENTI", "Penyetelan ulang penahan kaleng selama 6 menit"),
        _event("09.41", "REJECT", "Skor 0,71 melewati ambang 0,64"),
        _event("09.12", "BAHAN_BAKU_HABIS", "Menunggu kiriman label selama 8 menit"),
        _event("08.47", "REJECT", "Skor 0,72 melewati ambang 0,64"),
        _event("08.15", "REJECT", "Skor 0,69 melewati ambang 0,64"),
        _event("07.58", "REJECT", "Skor 0,70 melewati ambang 0,64"),
        _event("07.44", "REJECT", "Skor 0,66 melewati ambang 0,64"),
        _event("07.39", "REJECT", "Skor 0,68 melewati ambang 0,64"),
    ],
    "B-2411-01": [
        _event("10.42", "REJECT", "Skor 0,87 melewati ambang 0,62"),
        _event("10.39", "REJECT", "Skor 0,81 melewati ambang 0,62"),
        _event("10.31", "REJECT", "Skor 0,74 melewati ambang 0,62"),
        _event("10.15", "REJECT", "Skor 0,68 melewati ambang 0,62"),
        _event("09.20", "ALAT_BERHENTI", "Konveyor berhenti selama 4 menit karena sabuk longgar"),
        _event("08.05", "REJECT", "Skor 0,70 melewati ambang 0,62"),
    ],
    "B-2410-26": [
        _event("13.48", "REJECT", "Skor 0,79 melewati ambang 0,62"),
        _event("11.02", "BAHAN_BAKU_HABIS", "Menunggu kaleng kosong dari gudang selama 12 menit"),
        _event("09.37", "REJECT", "Skor 0,73 melewati ambang 0,62"),
    ],
}
