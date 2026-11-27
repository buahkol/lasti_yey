from datetime import datetime

from ..models import Alert, Inspection
from . import sample_data


class InspectionService:
    """GET /inspections/alerts (FR-22) and the latest alert summary."""

    def __init__(self):
        self._history: dict[str, list[Inspection]] = {}

    def recent_alerts(self, since: datetime | None = None) -> list[Alert]:
        """Newest first. since mirrors the ?since= query of GET /inspections/alerts."""
        return [a for a in sample_data.ALERTS if since is None or (a.timestamp and a.timestamp >= since)]

    def now(self) -> datetime:
        """Clock used for time windows. Sample data uses a fixed time; the API version uses datetime.now()."""
        return sample_data.NOW

    def alert_summary(self) -> dict:
        return dict(sample_data.ALERT_SUMMARY)

    def device_status(self) -> dict:
        return dict(sample_data.DEVICE)

    def history(self, batch_code: str) -> list[Inspection]:
        if batch_code not in self._history:
            self._history[batch_code] = sample_data.inspection_history(batch_code)
        return list(self._history[batch_code])
