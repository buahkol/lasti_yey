from dataclasses import dataclass


@dataclass
class ProductionEvent:
    """Production event (FR-17). REJECT events are recorded by the AI, others by the operator."""

    time: str
    kind: str  # REJECT, ALAT_BERHENTI, BAHAN_BAKU_HABIS
    source: str  # AI or Operator
    note: str
