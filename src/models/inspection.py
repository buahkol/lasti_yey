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
    threshold: float | None = None  # threshold this can was judged with (None: use the product's)
    model_version: str = ""

    @property
    def is_ng(self) -> bool:
        return self.result == "NG"
