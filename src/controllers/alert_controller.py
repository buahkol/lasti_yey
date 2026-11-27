from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Alert
from ..services import InspectionService

# Time windows on the Alert page: (tab label, minutes back, None = since midnight)
WINDOWS = [("30 menit", 30), ("1 jam", 60), ("3 jam", 180), ("Hari ini", None)]


@dataclass
class AlertSummary:
    count: int
    previous: int | None  # count in the window just before, None for "Hari ini"
    since: datetime
    avg_score: float
    avg_threshold: float
    top: Alert | None
    batches: list[str]

    @property
    def delta(self) -> str:
        if self.previous is None:
            return f"{self.count} kaleng"
        diff = self.count - self.previous
        return f"{diff:+d}" if diff else "tetap"


class AlertController:
    """Latest NG cans with photo and anomaly score (FR-22, FR-23), filtered by a recent time window."""

    def __init__(self, service: InspectionService):
        self._service = service

    def window_start(self, index: int, now: datetime | None = None) -> datetime:
        now = now or self._service.now()
        minutes = WINDOWS[index][1]
        if minutes is None:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - timedelta(minutes=minutes)

    def alerts(self, window: int = 0) -> list[Alert]:
        return self._service.recent_alerts(self.window_start(window))

    def counts(self) -> list[int]:
        return [len(self.alerts(i)) for i in range(len(WINDOWS))]

    def summary(self, window: int = 0) -> AlertSummary:
        now = self._service.now()
        since = self.window_start(window, now)
        rows = self._service.recent_alerts(since)
        previous = None
        if WINDOWS[window][1] is not None:
            before = since - (now - since)
            previous = sum(1 for a in self._service.recent_alerts(before) if a.timestamp < since)
        n = len(rows)
        return AlertSummary(
            count=n, previous=previous, since=since,
            avg_score=sum(a.score for a in rows) / n if n else 0.0,
            avg_threshold=sum(a.threshold for a in rows) / n if n else 0.0,
            top=max(rows, key=lambda a: a.score) if rows else None,
            batches=sorted({a.batch for a in rows}),
        )

    def device(self) -> dict:
        return self._service.device_status()
