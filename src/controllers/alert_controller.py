from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Alert
from ..services import InspectionService

# Time windows on the Alert page: (tab label, minutes back). "today" starts at midnight and
# "all" has no limit, because alerts and their photos are kept to trace a batch later.
WINDOWS = [("30 menit", 30), ("1 jam", 60), ("3 jam", 180), ("Hari ini", "today"), ("Semua", "all")]


@dataclass
class AlertSummary:
    count: int
    previous: int | None  # count in the window just before, None for "Hari ini" and "Semua"
    since: datetime | None  # None when no alert matches the "Semua" window
    avg_score: float
    avg_threshold: float
    top: Alert | None
    batches: list[str]

    @property
    def delta(self) -> str:
        if self.previous is None:
            return "total"
        diff = self.count - self.previous
        return f"{diff:+d}" if diff else "tetap"


class AlertController:
    """Latest NG cans with photo and anomaly score (FR-22, FR-23), filtered by a recent time window."""

    def __init__(self, service: InspectionService):
        self._service = service

    def window_start(self, index: int, now: datetime | None = None) -> datetime | None:
        now = now or self._service.now()
        span = WINDOWS[index][1]
        if span == "all":
            return None
        if span == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - timedelta(minutes=span)

    def alerts(self, window: int = 0, query: str = "") -> list[Alert]:
        """Alerts in the window; query matches the batch code or product name."""
        q = query.strip().upper()
        rows = self._service.recent_alerts(self.window_start(window))
        return [a for a in rows if not q or q in a.batch.upper() or q in a.product.upper()]

    def counts(self, query: str = "") -> list[int]:
        return [len(self.alerts(i, query)) for i in range(len(WINDOWS))]

    def summary(self, window: int = 0, query: str = "") -> AlertSummary:
        now = self._service.now()
        rows = self.alerts(window, query)
        since = self.window_start(window, now)
        if since is None and rows:
            since = min(a.timestamp for a in rows)
        previous = None
        if isinstance(WINDOWS[window][1], int):
            before = since - (now - since)
            q = query.strip().upper()
            previous = sum(1 for a in self._service.recent_alerts(before)
                           if a.timestamp < since and (not q or q in a.batch.upper() or q in a.product.upper()))
        n = len(rows)
        return AlertSummary(
            count=n, previous=previous, since=since,
            avg_score=sum(a.score for a in rows) / n if n else 0.0,
            avg_threshold=sum(a.threshold for a in rows) / n if n else 0.0,
            top=max(rows, key=lambda a: a.score) if rows else None,
            batches=sorted({a.batch for a in rows}),
        )

    def today(self):
        return self._service.now().date()

    def device(self) -> dict:
        return self._service.device_status()
