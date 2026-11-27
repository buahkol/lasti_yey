"""Services backed by the SiMonPro REST API.

Same methods and return types as the sample-data services, so controllers and views do not change.
Lists that several pages read in quick succession (products, batches, events) are cached for a few
seconds by ApiClient.get(ttl=...); every write clears that cache.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from ..models import Alert, Batch, Inspection, Product, ProductionEvent, User
from .api_client import ApiClient, ApiError

LIST_TTL = 3.0  # seconds
_SOURCE = {"AI": "AI", "OPERATOR": "Operator", "SENSOR": "Sensor"}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def local(ts: str | None) -> datetime | None:
    """API timestamp (ISO 8601 with offset) -> naive local time, as the views expect."""
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def duration_text(start: datetime, end: datetime | None) -> str:
    """'7 jam 35 menit' for a closed batch, 'berjalan 2 jam' while it runs."""
    minutes = max(0, int(((end or datetime.now()) - start).total_seconds() // 60))
    hours, mins = divmod(minutes, 60)
    parts = ([f"{hours} jam"] if hours else []) + ([f"{mins} menit"] if mins or not hours else [])
    return ("berjalan " if end is None else "") + " ".join(parts)


def _hour(dt: datetime) -> str:
    return f"{dt.hour:02d}.00"


def _batch(row: dict) -> Batch:
    started, ended = local(row["startedAt"]), local(row.get("endedAt"))
    inspected = row["total"]
    return Batch(
        code=row["batchCode"], sku=row["sku"], product=row["productName"], started_at=started,
        duration=duration_text(started, ended),
        # cans counted by the sensor; at least the cans that were inspected
        output=max(row["totalOutput"], inspected),
        ng_percent=row["ng"] / inspected * 100 if inspected else 0.0,
        status=row["batchStatus"], inspection=row["inspectionStatus"],
    )


class _Base:
    def __init__(self, api: ApiClient):
        self.api = api

    def _batches(self) -> list[Batch]:
        return [_batch(r) for r in self.api.get("/batches", ttl=LIST_TTL)]

    def _products(self) -> dict[str, dict]:
        return {p["sku"]: p for p in self.api.get("/products", ttl=LIST_TTL)}

    def _inspections(self, code: str) -> list[Inspection]:
        data = self.api.get(f"/batches/{code}/inspections", ttl=LIST_TTL)
        return [Inspection(r["inspectionId"], code, r["result"], r["anomalyScore"], local(r["timestamp"]),
                           "dent" if r["result"] == "NG" else "none")
                for r in data["inspections"]]

    def _alert(self, batch: Batch | None, row: Inspection, products: dict[str, dict]) -> Alert:
        product = products.get(batch.sku, {}) if batch else {}
        return Alert(row.batch, f"{row.timestamp:%H.%M.%S}", row.score, product.get("threshold") or 0.0,
                     row.defect, batch.product if batch else "", row.timestamp, row.result, row.inspection_id)


class AuthService(_Base):
    """POST /auth/login and POST /auth/logout (FR-01, FR-03)."""

    def login(self, username: str, password: str) -> User | None:
        user = self.api.login(username, password)
        if user is None:
            return None
        full = (user.get("nama") or user["username"]).strip()
        short = full.split()[0] if full else user["username"].capitalize()
        return User(user["username"], short, full, short[:2].upper())

    def logout(self) -> None:
        self.api.logout()


class ProductService(_Base):
    """GET/POST/PUT /products (FR-04) and product availability (FR-18)."""

    def _product(self, row: dict, batches: list[Batch]) -> Product:
        own = [b for b in batches if b.sku == row["sku"]]
        today = [b for b in own if b.started_at.date() == date.today()]
        inspected = sum(b.output for b in today)
        ok_today, updated = sum(b.ok_count for b in today), "belum ada inspeksi"
        try:
            avail = self.api.get(f"/products/{row['sku']}/availability", ttl=LIST_TTL)
            ok_today = avail["availableQty"]
            if avail.get("updatedAt"):
                updated = f"pukul {local(avail['updatedAt']):%H.%M}"
        except ApiError:
            pass
        latest = own[0].status if own else "DITUTUP"  # /batches is sorted newest first
        return Product(row["sku"], row["name"], round(row["unitPrice"]), row.get("threshold") or 0.0,
                       row.get("modelVersion") or "belum ada", latest, ok_today,
                       ok_today / inspected * 100 if inspected else 0.0, updated, len(own))

    def list_products(self) -> list[Product]:
        batches = self._batches()
        return [self._product(r, batches) for r in self.api.get("/products", ttl=LIST_TTL)]

    def find(self, sku: str) -> Product | None:
        return next((p for p in self.list_products() if p.sku == sku), None)

    def add(self, product: Product) -> Product:
        self.api.post("/products", {"sku": product.sku, "name": product.name, "unitPrice": product.price})
        return self.find(product.sku) or product

    def update(self, sku: str, name: str, price: int) -> Product:
        self.api.put(f"/products/{sku}", {"name": name, "unitPrice": price})
        return self.find(sku)


class BatchService(_Base):
    """GET/POST /batches and POST /batches/{code}/close (FR-05, FR-06, FR-27)."""

    def list_batches(self) -> list[Batch]:
        return self._batches()

    def find(self, code: str) -> Batch | None:
        return next((b for b in self._batches() if b.code == code), None)

    def add(self, batch: Batch) -> Batch:
        return _batch(self.api.post("/batches", {"batchCode": batch.code, "sku": batch.sku}))

    def close(self, batch: Batch, inspection: str) -> Batch:
        """The server decides PASSED or HOLD from its NG tolerance; ``inspection`` is only the local guess."""
        return _batch(self.api.post(f"/batches/{batch.code}/close"))

    def save(self, batch: Batch) -> Batch:
        return batch


class EventService(_Base):
    """GET/POST /production/events (FR-17)."""

    def _all(self) -> dict[str, list[ProductionEvent]]:
        out: dict[str, list[ProductionEvent]] = defaultdict(list)
        for r in self.api.get("/production/events", {"limit": 1000}, ttl=LIST_TTL):  # newest first
            out[r["batchCode"]].append(ProductionEvent(f"{local(r['timestamp']):%H.%M}", r["eventType"],
                                                       _SOURCE.get(r["source"], r["source"]), r.get("note") or ""))
        return out

    def list_events(self, batch_code: str) -> list[ProductionEvent]:
        return list(self._all().get(batch_code, []))

    def record(self, batch_code: str, event: ProductionEvent, when: datetime | None = None) -> ProductionEvent:
        when = (when or datetime.now()).astimezone()
        self.api.post("/production/events", {"batchCode": batch_code, "eventType": event.kind, "source": "OPERATOR",
                                             "timestamp": when, "note": event.note or None})
        return event


class InspectionService(_Base):
    """GET /inspections/alerts (FR-22), the latest alert summary and GET /batches/{code}/inspections."""

    def recent_alerts(self, since: datetime | None = None) -> list[Alert]:
        params = {"limit": 500}
        if since is not None:
            params["since"] = since.astimezone()
        rows = self.api.get("/inspections/alerts", params, ttl=LIST_TTL)
        batches = {b.code: b for b in self._batches()}
        products = self._products()
        return [self._alert(batches.get(r["batchCode"]),
                            Inspection(r["inspectionId"], r["batchCode"], "NG", r["anomalyScore"],
                                       local(r["timestamp"]), "dent"), products)
                for r in rows]

    def now(self) -> datetime:
        return datetime.now()

    def alert_summary(self) -> dict:
        now = self.now()
        last = self.recent_alerts(now - timedelta(minutes=30))
        before = [a for a in self.recent_alerts(now - timedelta(minutes=60)) if a.timestamp < now - timedelta(minutes=30)]
        top = max(last, key=lambda a: a.score) if last else None
        return {
            "ng_30min": len(last), "ng_delta": f"{len(last) - len(before):+d}",
            "since": f"{now - timedelta(minutes=30):%H.%M}",
            "avg_score": sum(a.score for a in last) / len(last) if last else 0.0,
            "top_score": top.score if top else 0.0, "top_batch": top.batch if top else "-",
            "top_time": top.time[:5] if top else "-", "affected_batches": len({a.batch for a in last}),
        }

    def device_status(self) -> dict:
        """No device endpoint yet: 'connected' means the device sent a photo in the last 2 minutes."""
        latest = self.recent_alerts()[:1]
        recent = any(b.running for b in self._batches())
        connected = bool(latest and latest[0].timestamp > self.now() - timedelta(minutes=2)) or recent
        return {"name": "ESP32-S3", "ip": "-", "seconds_per_can": 0.0, "connected": connected}

    def history(self, batch_code: str) -> list[Inspection]:
        """Every inspected can of a batch, OK and NG, newest first."""
        try:
            return self._inspections(batch_code)
        except ApiError:
            return []


class ReportService(_Base):
    """GET /production/reports (dashboard) and GET /inspections/reports/{batchCode} (FR-19, FR-24)."""

    def _active(self) -> Batch | None:
        return next((b for b in self._batches() if b.running), None)

    def _today_inspections(self) -> list[Inspection]:
        """Inspections of today for the dashboard chart: the running batch, else every batch of today."""
        active = self._active()
        codes = [active.code] if active else [b.code for b in self._batches() if b.started_at.date() == self.today()]
        rows = [r for c in codes for r in self._inspections(c)]
        return [r for r in rows if r.timestamp.date() == self.today()]

    def dashboard_stats(self) -> dict:
        report = self.api.get("/production/reports", ttl=LIST_TTL)["batches"]
        ok, ng = sum(r["ok"] for r in report), sum(r["ng"] for r in report)
        output = sum(max(r["totalOutput"], r["ok"] + r["ng"]) for r in report)
        rejects = self.api.get("/production/events", {"date": self.today().isoformat(), "eventType": "REJECT",
                                                      "limit": 1000}, ttl=LIST_TTL)
        hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        this_hour = sum(1 for r in self._today_inspections() if r.timestamp >= hour)
        inspected = ok + ng
        return {
            "output": output, "output_delta": f"+{this_hour}", "output_since": f"{hour:%H.%M}",
            "ok": ok, "ok_percent": ok / inspected * 100 if inspected else 0.0,
            "ng": ng, "ng_percent": ng / inspected * 100 if inspected else 0.0,
            "events": sum(r["events"] for r in report), "events_reject": len(rejects),
        }

    def output_per_hour(self) -> tuple[list, int]:
        """(hour, OK, NG) for 12 hours: 07.00 to 18.00, shifted later when the line runs past 18.00."""
        rows = self._today_inspections()
        now = datetime.now().hour
        start = max(0, now - 11) if now > 18 else min([7] + [r.timestamp.hour for r in rows])
        start = min(start, 12)
        counts = {h: [0, 0] for h in range(start, start + 12)}
        for r in rows:
            if r.timestamp.hour in counts:
                counts[r.timestamp.hour][1 if r.is_ng else 0] += 1
        hours = [(f"{h:02d}.00", ok, ng) for h, (ok, ng) in counts.items()]
        return hours, max(0, min(now - start, len(hours) - 1))

    def active_batch_started(self) -> str:
        active = self._active()
        return f"{active.started_at:%H.%M}" if active else "-"

    def batch_report(self, code: str) -> dict | None:
        """Inspection report of one batch, or None while it has no inspections."""
        try:
            self.api.get(f"/inspections/reports/{code}", ttl=LIST_TTL)
        except ApiError:
            return None
        rows = self._inspections(code)
        if not rows:
            return None
        batch = next((b for b in self._batches() if b.code == code), None)
        products = self._products()
        per_hour: dict[str, list[int]] = {}
        for r in sorted(rows, key=lambda r: r.timestamp):
            h = per_hour.setdefault(_hour(r.timestamp), [0, 0])
            h[0] += r.is_ng
            h[1] += 1
        events = EventService(self.api).list_events(code)
        first, last = min(r.timestamp for r in rows), max(r.timestamp for r in rows)
        ng = sum(1 for r in rows if r.is_ng)
        top = sorted((r for r in rows if r.is_ng), key=lambda r: r.score, reverse=True)[:3]
        return {
            "date": f"{first.day} {_MONTHS[first.month - 1]} {first.year}",
            "window": f"{first:%H.%M} sampai {last:%H.%M}",
            "total": len(rows), "ok": len(rows) - ng, "ng": ng,
            "events": len(events), "events_reject": sum(1 for e in events if e.kind == "REJECT"),
            "events_manual": sum(1 for e in events if e.source == "Operator"),
            "ng_per_hour": [(hour, n_ng, n) for hour, (n_ng, n) in per_hour.items()],
            "events_list": events,
            "top_scores": [self._alert(batch, r, products) for r in top],
        }

    def today(self) -> date:
        return date.today()
