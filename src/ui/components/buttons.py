"""Buttons: pill Button (6 variants, 2 sizes) and square IconButton."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QPushButton, QToolButton, QWidget

from ..assets import icon
from ..theme import Color, Size

# icon colour per button variant
_FG = {
    "primary": "#FFFFFF",
    "secondary": Color.SECONDARY_FG,
    "outline": Color.ICON_STRONG,
    "navy": "#FFFFFF",
    "ghost": Color.BRAND,
    "danger": "#FFFFFF",
}


class Button(QPushButton):
    """Pill button.

    variant: primary | secondary | outline | navy | ghost | danger
    size: md (44px) | sm (36px)
    icon_name: leading icon; trailing=True puts the icon after the label
    (used for "Lihat semua" style links).
    """

    def __init__(self, label: str, variant: str = "primary", size: str = "md",
                 icon_name: str | None = None, trailing: bool = False,
                 parent: QWidget | None = None):
        # a thin space keeps the icon from touching the label
        if icon_name:
            label = f"{label} " if trailing else f" {label}"
        super().__init__(label, parent)
        self.setProperty("variant", variant)
        self.setProperty("btnSize", size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._variant = variant
        if icon_name:
            px = 18 if size == "md" else 16
            self.setIcon(icon(icon_name, _FG[variant], px))
            self.setIconSize(QSize(px, px))
            if trailing:
                self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    def set_variant(self, variant: str) -> None:
        self.setProperty("variant", variant)
        self.style().unpolish(self)
        self.style().polish(self)


class IconButton(QToolButton):
    """Square 40px icon button. Always pass a tooltip (accessibility)."""

    def __init__(self, icon_name: str, tooltip: str, style: str = "outline", size: int = Size.ICON_BUTTON,
                 color: str = Color.ICON_STRONG, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("iconStyle", style)
        self.setToolTip(tooltip)
        self.setFixedSize(size, size)
        self.setIcon(icon(icon_name, color, 18))
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_icon(self, icon_name: str, color: str = Color.ICON_STRONG) -> None:
        self.setIcon(icon(icon_name, color, 18))
