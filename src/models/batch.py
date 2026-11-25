from dataclasses import dataclass
from datetime import datetime


class BatchStatus:
    RUNNING = "BERJALAN"
    CLOSED = "DITUTUP"


class InspectionStatus:
    PASSED = "PASSED"
    HOLD = "HOLD"


@dataclass
class Batch:
    """Production batch (FR-05, FR-06) and its inspection status (FR-26, FR-27)."""

    code: str
    sku: str
    product: str
    started_at: datetime
    duration: str
    output: int
    ng_percent: float
    status: str = BatchStatus.RUNNING
    inspection: str = InspectionStatus.HOLD

    @property
    def running(self) -> bool:
        return self.status == BatchStatus.RUNNING

    @property
    def ng_count(self) -> int:
        return round(self.output * self.ng_percent / 100)

    @property
    def ok_count(self) -> int:
        return self.output - self.ng_count

    @property
    def start_label(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        return f"{self.started_at.day} {months[self.started_at.month - 1]}, {self.started_at:%H.%M}"
