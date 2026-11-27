from datetime import datetime

from ..models import Alert, Batch
from ..services import BatchService, InspectionService, ReportService
from .rules import NG_TOLERANCE_PERCENT


class DashboardController:
    """Active batch, today's totals, output per hour and the latest alerts (FR-19, FR-20, FR-22)."""

    def __init__(self, reports: ReportService, inspections: InspectionService, batches: BatchService):
        self._reports = reports
        self._inspections = inspections
        self._batches = batches

    @staticmethod
    def greeting(now: datetime | None = None) -> str:
        hour = (now or datetime.now()).hour
        if 4 <= hour < 11:
            return "Selamat pagi"
        if 11 <= hour < 15:
            return "Selamat siang"
        if 15 <= hour < 18:
            return "Selamat sore"
        return "Selamat malam"

    def active_batch(self) -> Batch | None:
        return next((b for b in self._batches.list_batches() if b.running), None)

    def active_batch_started(self) -> str:
        return self._reports.active_batch_started()

    def stats(self) -> dict:
        return self._reports.dashboard_stats()

    def output_per_hour(self) -> tuple[list, int]:
        return self._reports.output_per_hour()

    def today_batches(self) -> list[tuple[Batch, str]]:
        """Today's batches with the badge to show: HOLD once NG passes the tolerance, else the batch status."""
        today = self._reports.today()
        rows = []
        for b in self._batches.list_batches():
            if b.started_at.date() != today:
                continue
            badge = "HOLD" if b.ng_percent > NG_TOLERANCE_PERCENT else b.status
            rows.append((b, badge))
        return rows

    def alerts(self, limit: int = 6) -> list[Alert]:
        return self._inspections.recent_alerts()[:limit]

    def alert_summary(self) -> dict:
        return self._inspections.alert_summary()
