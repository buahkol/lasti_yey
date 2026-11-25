from dataclasses import dataclass


@dataclass
class Alert:
    """One NG can detected by PatchCore (FR-22, FR-23)."""

    batch: str
    time: str
    score: float
    threshold: float
    defect: str  # kind of defect, used for the placeholder photo until real images arrive
    product: str = ""
