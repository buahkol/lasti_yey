from ..models import Alert
from ..services import InspectionService


class AlertController:
    """Latest NG cans with photo and anomaly score (FR-22, FR-23)."""

    def __init__(self, service: InspectionService):
        self._service = service

    def alerts(self, batch: str | None = None) -> list[Alert]:
        return [a for a in self._service.recent_alerts() if batch is None or a.batch == batch]

    def batches(self) -> list[str]:
        return sorted({a.batch for a in self._service.recent_alerts()})

    def summary(self) -> dict:
        return self._service.alert_summary()

    def device(self) -> dict:
        return self._service.device_status()
