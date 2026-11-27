from dataclasses import dataclass
from datetime import datetime


@dataclass
class Inspection:
    """One inspected can with its photo (OK or NG), from GET /batches/{code}/inspections."""

    inspection_id: int
    batch: str
    result: str
    score: float
    timestamp: datetime
    defect: str = "none"

    @property
    def is_ng(self) -> bool:
        return self.result == "NG"
