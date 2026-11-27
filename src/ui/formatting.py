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


def threshold(value: float) -> str:
    """0.9 -> '0,90', 0.975 -> '0,975', 0.172956 -> '0,173': at least 2, at most 3 decimals."""
    s = f"{value:.3f}"
    return (s[:-1] if s.endswith("0") else s).replace(".", ",")


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def day(value, year: bool = False) -> str:
    text = f"{value.day} {_MONTHS[value.month - 1]}"
    return f"{text} {value.year}" if year else text
