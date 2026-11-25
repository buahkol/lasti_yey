"""Hard-coded sample data that matches the Figma screens.

Replace these with calls to the REST API (base URL /api/v1) once the backend
endpoints are ready. Each block notes the endpoint that will provide it.
"""

from datetime import date

TODAY = date(2026, 11, 25)
NG_TOLERANCE = 5.0  # percent, FR-26

# Prototype login (FR-01). Replace with the real auth service.
DEMO_USER = {"username": "operasional", "password": "simonpro", "name": "Operasional",
             "role": "Shift pagi, Lini 1", "initials": "OP"}

DEVICE = {"name": "ESP32-CAM", "ip": "192.168.1.42", "seconds_per_can": 0.8, "connected": True}

# --- Dashboard: GET /production/reports + GET /inspections/alerts ---------
ACTIVE_BATCH = {
    "code": "B-2411-01", "sku": "SDN-TMT-155", "product": "Sarden saus tomat 155 g",
    "started": "07.02", "ng_percent": 1.8,
}

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

TODAY_BATCHES = [
    {"code": "B-2411-01", "product": "Sarden saus tomat 155 g", "output": 1250, "ng_percent": 1.8, "status": "BERJALAN"},
    {"code": "B-2411-02", "product": "Sarden saus cabai 155 g", "output": 640, "ng_percent": 6.6, "status": "HOLD"},
]

# (batch, time, score, threshold, defect kind for the placeholder photo)
ALERTS = [
    ("B-2411-01", "10.42.07", 0.87, 0.62, "dent"),
    ("B-2411-01", "10.39.51", 0.81, 0.62, "label"),
    ("B-2411-02", "10.36.14", 0.93, 0.64, "rust"),
    ("B-2411-02", "10.33.40", 0.77, 0.64, "dent"),
    ("B-2411-01", "10.31.02", 0.74, 0.62, "label"),
    ("B-2411-02", "10.27.18", 0.70, 0.64, "rust"),
    ("B-2411-01", "10.15.44", 0.68, 0.62, "dent"),
]
ALERT_SUMMARY = {"ng_30min": 7, "ng_delta": "+3", "since": "10.12", "avg_score": 0.80,
                 "top_score": 0.93, "top_batch": "B-2411-02", "top_time": "10.36", "affected_batches": 2}

# --- Produk: product table + GET /products/{sku}/availability ---------------
PRODUCTS = [
    {"sku": "SDN-TMT-155", "name": "Sarden saus tomat 155 g", "price": 12500, "threshold": 0.62,
     "model": "pc-v2.1", "status": "BERJALAN", "ok_today": 1228, "ok_ratio": 98.2, "updated": "pukul 10.42",
     "batches": 2},
    {"sku": "SDN-CBI-155", "name": "Sarden saus cabai 155 g", "price": 13000, "threshold": 0.64,
     "model": "pc-v2.1", "status": "BERJALAN", "ok_today": 598, "ok_ratio": 93.4, "updated": "pukul 10.36",
     "batches": 1},
    {"sku": "SDN-MNY-425", "name": "Sarden minyak nabati 425 g", "price": 27500, "threshold": 0.58,
     "model": "pc-v1.4", "status": "DITUTUP", "ok_today": 972, "ok_ratio": 99.2, "updated": "kemarin",
     "batches": 1},
]

# --- Batch: GET /batches/inspection-status --------------------------------
BATCHES = [
    {"code": "B-2411-01", "sku": "SDN-TMT-155", "product": "Sarden saus tomat 155 g", "start": "25 Nov, 07.02",
     "duration": "berjalan 4 jam", "output": 1250, "ng_percent": 1.8, "batch": "BERJALAN", "inspection": "HOLD"},
    {"code": "B-2411-02", "sku": "SDN-CBI-155", "product": "Sarden saus cabai 155 g", "start": "25 Nov, 07.30",
     "duration": "berjalan 3 jam", "output": 640, "ng_percent": 6.6, "batch": "BERJALAN", "inspection": "HOLD"},
    {"code": "B-2410-28", "sku": "SDN-MNY-425", "product": "Sarden minyak nabati 425 g", "start": "24 Nov, 08.10",
     "duration": "8 jam", "output": 980, "ng_percent": 0.8, "batch": "DITUTUP", "inspection": "PASSED"},
    {"code": "B-2410-27", "sku": "SDN-CBI-155", "product": "Sarden saus cabai 155 g", "start": "24 Nov, 07.45",
     "duration": "7 jam 35 menit", "output": 760, "ng_percent": 2.4, "batch": "DITUTUP", "inspection": "PASSED"},
    {"code": "B-2410-26", "sku": "SDN-TMT-155", "product": "Sarden saus tomat 155 g", "start": "23 Nov, 07.00",
     "duration": "8 jam", "output": 1410, "ng_percent": 6.5, "batch": "DITUTUP", "inspection": "HOLD"},
    {"code": "B-2410-25", "sku": "SDN-MNY-425", "product": "Sarden minyak nabati 425 g", "start": "23 Nov, 08.00",
     "duration": "6 jam 40 menit", "output": 860, "ng_percent": 1.0, "batch": "DITUTUP", "inspection": "PASSED"},
    {"code": "B-2410-24", "sku": "SDN-TMT-155", "product": "Sarden saus tomat 155 g", "start": "23 Nov, 07.10",
     "duration": "7 jam 55 menit", "output": 1322, "ng_percent": 4.2, "batch": "DITUTUP", "inspection": "PASSED"},
]
BATCH_TOTAL = 12

# --- Laporan: GET /inspections/reports/{batchCode} -------------------------
REPORT = {
    "code": "B-2411-02", "product": "Sarden saus cabai 155 g", "date": "25 Nov 2026",
    "window": "07.30 sampai 14.50", "total": 640, "ok": 598, "ng": 42, "ng_percent": 6.6,
    "unit_price": 13000, "events": 44, "events_reject": 42, "events_manual": 2,
    # (hour, NG count, output in that hour)
    "ng_per_hour": [("07.00", 3, 60), ("08.00", 4, 78), ("09.00", 5, 84), ("10.00", 9, 96), ("11.00", 7, 88),
                    ("12.00", 5, 70), ("13.00", 4, 66), ("14.00", 3, 58), ("15.00", 2, 40)],
    "events_list": [
        ("10.42", "REJECT", "AI", "Skor 0,87 melewati ambang 0,62"),
        ("10.36", "REJECT", "AI", "Skor 0,93 melewati ambang 0,64"),
        ("09.58", "ALAT_BERHENTI", "Operator", "Penyetelan ulang penahan kaleng selama 6 menit"),
        ("09.12", "BAHAN_BAKU_HABIS", "Operator", "Menunggu kiriman label selama 8 menit"),
        ("08.47", "REJECT", "AI", "Skor 0,72 melewati ambang 0,64"),
        ("08.15", "REJECT", "AI", "Skor 0,69 melewati ambang 0,64"),
    ],
    "top_scores": [("B-2411-02", "10.36.14", "0,93", "rust"), ("B-2411-02", "10.33.40", "0,77", "dent"),
                   ("B-2411-02", "10.12.30", "0,72", "label")],
}


def rupiah(value: int) -> str:
    """12500 -> 'Rp12.500'."""
    return "Rp" + f"{value:,}".replace(",", ".")


def num(value: int) -> str:
    """1250 -> '1.250'."""
    return f"{value:,}".replace(",", ".")


def pct(value: float) -> str:
    """1.8 -> '1,8%'."""
    return f"{value:.1f}%".replace(".", ",")
