from dataclasses import dataclass
from datetime import datetime


@dataclass
class Inspection:
    inspection_id: int
    batch: str
    result: str
    score: float
    timestamp: datetime
    defect: str = "none"

    @property
    def is_ng(self) -> bool:
        return self.result == "NG"
