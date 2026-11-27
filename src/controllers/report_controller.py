from datetime import date, timedelta

from ..models import Batch
from ..services import BatchService, ProductService, ReportService
from .rules import NG_TOLERANCE_PERCENT

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def day_label(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]}"


class ReportController:
    """Inspection report per batch (FR-24) and production recap per date range (FR-21)."""

    def __init__(self, reports: ReportService, batches: BatchService, products: ProductService):
        self._reports = reports
        self._batches = batches
        self._products = products

    def batches(self) -> list[Batch]:
        return self._batches.list_batches()

    def today(self) -> date:
        """Today's date from the data source (the sample data has a fixed day)."""
        return self._reports.today()

    def batch_report(self, code: str) -> dict | None:
        """Report for one batch, or None when the server has no inspection data for it yet."""
        batch = self._batches.find(code)
        report = self._reports.batch_report(code)
        if batch is None or report is None:
            return None
        product = self._products.find(batch.sku)
        unit_price = product.price if product else 0
        ng_percent = report["ng"] / report["total"] * 100 if report["total"] else 0.0
        report.update(code=batch.code, product=batch.product, unit_price=unit_price, ng_percent=ng_percent,
                      ok_percent=100 - ng_percent, loss=report["ng"] * unit_price,
                      held=ng_percent > NG_TOLERANCE_PERCENT)
        return report

    def date_recap(self, start: date, end: date) -> dict:
        """Output, OK, NG and loss for every batch that started within [start, end]."""
        if end < start:
            start, end = end, start
        rows = []
        for b in self._batches.list_batches():
            if start <= b.started_at.date() <= end:
                product = self._products.find(b.sku)
                price = product.price if product else 0
                rows.append({"batch": b, "ok": b.ok_count, "ng": b.ng_count, "loss": b.ng_count * price})
        rows.sort(key=lambda r: r["batch"].started_at, reverse=True)
        per_day = []
        d = start
        while d <= end:
            day_rows = [r for r in rows if r["batch"].started_at.date() == d]
            per_day.append((day_label(d), sum(r["ok"] for r in day_rows), sum(r["ng"] for r in day_rows)))
            d += timedelta(days=1)
        total = sum(r["batch"].output for r in rows)
        ng = sum(r["ng"] for r in rows)
        closed = [r["batch"] for r in rows if not r["batch"].running]
        return {
            "start": start, "end": end, "rows": rows, "per_day": per_day,
            "total": total, "ok": total - ng, "ng": ng,
            "ng_percent": ng / total * 100 if total else 0.0,
            "loss": sum(r["loss"] for r in rows),
            "batch_count": len(rows),
            "passed": sum(1 for b in closed if b.inspection == "PASSED"),
            "hold": sum(1 for b in closed if b.inspection == "HOLD"),
            "running": sum(1 for r in rows if r["batch"].running),
        }
