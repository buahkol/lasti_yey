"""Number formats used across the UI (Indonesian style)."""


def rupiah(value: int) -> str:
    """12500 -> 'Rp12.500'."""
    return "Rp" + f"{value:,}".replace(",", ".")


def num(value: int) -> str:
    """1250 -> '1.250'."""
    return f"{value:,}".replace(",", ".")


def pct(value: float) -> str:
    """1.8 -> '1,8%'."""
    return f"{value:.1f}%".replace(".", ",")


def score(value: float) -> str:
    """0.87 -> '0,87'."""
    return f"{value:.2f}".replace(".", ",")
