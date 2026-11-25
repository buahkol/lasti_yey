"""Small building blocks shared by every component."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QBoxLayout, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ..theme import Color, Type, font
from ..theme.tokens import TextStyle


def text(content: str, style: TextStyle = Type.BODY, color: str = Color.TEXT_PRIMARY,
         wrap: bool = False, align=None) -> QLabel:
    """Label with a design-system text style and colour."""
    label = QLabel(content)
    label.setFont(font(style))
    label.setStyleSheet(f"color: {color}; background: transparent;")
    label.setWordWrap(wrap)
    if align is not None:
        label.setAlignment(align)
    return label


def set_text_color(label: QLabel, color: str) -> None:
    label.setStyleSheet(f"color: {color}; background: transparent;")


def hbox(spacing: int = 8, margins=(0, 0, 0, 0), parent: QWidget | None = None) -> QHBoxLayout:
    lay = QHBoxLayout(parent) if parent else QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


def vbox(spacing: int = 8, margins=(0, 0, 0, 0), parent: QWidget | None = None) -> QVBoxLayout:
    lay = QVBoxLayout(parent) if parent else QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    return lay


def add_shadow(widget: QWidget, kind: str = "card") -> None:
    """Soft elevation (Figma Shadow/Card and Shadow/Pop)."""
    effect = QGraphicsDropShadowEffect(widget)
    if kind == "pop":
        effect.setBlurRadius(48)
        effect.setOffset(0, 18)
        effect.setColor(QColor(23, 42, 58, 46))
    else:
        effect.setBlurRadius(24)
        effect.setOffset(0, 6)
        effect.setColor(QColor(23, 42, 58, 16))
    widget.setGraphicsEffect(effect)


def spacer(horizontal: bool = True) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    if horizontal:
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    else:
        w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return w


class Card(QFrame):
    """White rounded container with a soft shadow (Figma panel/card)."""

    def __init__(self, padding=(20, 20, 20, 20), spacing: int = 12, direction: str = "v",
                 shadow: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout_: QBoxLayout = vbox(spacing, padding, self) if direction == "v" else hbox(spacing, padding, self)
        if shadow:
            add_shadow(self)

    def add(self, widget: QWidget, stretch: int = 0, align=None) -> QWidget:
        if align is not None:
            self.layout_.addWidget(widget, stretch, align)
        else:
            self.layout_.addWidget(widget, stretch)
        return widget


class Divider(QFrame):
    def __init__(self, vertical: bool = False, color: str = Color.BORDER):
        super().__init__()
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)
        self.setStyleSheet(f"background: {color}; border: none;")
