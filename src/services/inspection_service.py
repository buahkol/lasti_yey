from ..models import Alert
from . import sample_data


class InspectionService:
    """GET /inspections/alerts (FR-22) and the latest alert summary."""

    def recent_alerts(self) -> list[Alert]:
        return list(sample_data.ALERTS)

    def alert_summary(self) -> dict:
        return dict(sample_data.ALERT_SUMMARY)

    def device_status(self) -> dict:
        return dict(sample_data.DEVICE)
