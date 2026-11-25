"""Business rules shared by several controllers."""

NG_TOLERANCE_PERCENT = 5.0  # FR-26


def inspection_status(ng_percent: float) -> str:
    """PASSED when the NG percentage is within tolerance, otherwise HOLD (FR-26)."""
    return "HOLD" if ng_percent > NG_TOLERANCE_PERCENT else "PASSED"
