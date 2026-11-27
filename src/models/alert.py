from dataclasses import dataclass
from datetime import datetime


@dataclass
class Alert:
    """One NG can detected by PatchCore (FR-22, FR-23)."""

    batch: str
    time: str
    score: float
    threshold: float
    defect: str  # kind of defect, used for the placeholder photo until real images arrive
    product: str = ""
    timestamp: datetime | None = None  # full date and time, used for the time window filter
    result: str = "NG"  # OK photos only appear in Riwayat
    inspection_id: int | None = None
