"""Theme: design tokens, fonts and global stylesheet."""

from PyQt6.QtWidgets import QApplication

from .fonts import font, load_fonts
from .style import build_stylesheet
from .tokens import NG_TOLERANCE_PERCENT, STATUS_TONE, TONES, Color, Radius, Size, Type


def apply_theme(app: QApplication) -> None:
    """Load fonts and apply the global stylesheet to the application."""
    load_fonts()
    app.setFont(font(Type.BODY))
    app.setStyleSheet(build_stylesheet())


__all__ = [
    "Color", "Type", "Radius", "Size", "TONES", "STATUS_TONE", "NG_TOLERANCE_PERCENT",
    "font", "load_fonts", "apply_theme",
]
