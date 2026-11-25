from ..models import Alert, Inspection
from . import sample_data


class InspectionService:
    """GET /inspections/alerts (FR-22) and the latest alert summary."""

    def __init__(self):
        self._history: dict[str, list[Inspection]] = {}

    def recent_alerts(self) -> list[Alert]:
        return list(sample_data.ALERTS)

    def alert_summary(self) -> dict:
        return dict(sample_data.ALERT_SUMMARY)

    def device_status(self) -> dict:
        return dict(sample_data.DEVICE)

    def history(self, batch_code: str) -> list[Inspection]:
        if batch_code not in self._history:
            self._history[batch_code] = sample_data.inspection_history(batch_code)
        return list(self._history[batch_code])
