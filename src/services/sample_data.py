"""Sample data that matches the Figma screens.

Used by the services until the REST API (/api/v1) is connected. Each block
names the endpoint that will provide it.
"""

import random
import re
from datetime import date, datetime, timedelta

from ..models import Alert, Batch, Inspection, Product, ProductionEvent, User

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


def _alert(batch: str, time: str, score: float, defect: str) -> Alert:
    threshold, product = (0.62, _TMT) if batch == "B-2411-01" else (0.64, _CBI)
    at = datetime.combine(TODAY, datetime.strptime(time, "%H.%M.%S").time())
    return Alert(batch, time, score, threshold, defect, product, at)


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




def _minutes(duration: str) -> int:
    hours = re.search(r"(\d+) jam", duration)
    minutes = re.search(r"(\d+) menit", duration)
    return (int(hours[1]) * 60 if hours else 0) + (int(minutes[1]) if minutes else 0)


def inspection_history(batch_code: str) -> list[Inspection]:
    first_id = 1
    for batch in sorted(BATCHES, key=lambda b: b.started_at):
        if batch.code == batch_code:
            break
        first_id += batch.output
    else:
        return []
    threshold = next(p.threshold for p in PRODUCTS if p.sku == batch.sku)
    rnd = random.Random(batch_code)
    ng = set(rnd.sample(range(batch.output), batch.ng_count))
    step = _minutes(batch.duration) * 60 / max(batch.output, 1)
    rows = []
    for i in range(batch.output):
        when = batch.started_at + timedelta(seconds=round(step * (i + 0.5)))
        if i in ng:
            score, result, defect = rnd.uniform(threshold + 0.01, 0.95), "NG", rnd.choice(["dent", "rust", "label"])
        else:
            score, result, defect = rnd.uniform(0.18, threshold - 0.06), "OK", "none"
        rows.append(Inspection(first_id + i, batch_code, result, round(score, 2), when, defect))
    return rows[::-1]
