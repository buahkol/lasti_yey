"""Status elements: Badge, LiveIndicator, UserChip."""

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from ..theme import STATUS_TONE, TONES, Color, Type, font
from .base import hbox, text, vbox


class Badge(QLabel):
    """Uppercase status pill without a dot: OK, NG, PASSED, HOLD, BERJALAN, DITUTUP."""

    def __init__(self, status: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFont(font(Type.OVERLINE))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        tone_name = STATUS_TONE.get(status.upper())
        if tone_name:
            t = TONES[tone_name]
            bg, fg, border = t.soft, t.ink, t.mid
        else:
            bg, fg, border = Color.CANVAS_ALT, Color.TEXT_SECONDARY, Color.BORDER
        self.setText(status.upper())
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border};"
            "border-radius: 8px; padding: 3px 10px;"
        )
        self.adjustSize()
        self.setFixedSize(self.sizeHint())


class _Dot(QFrame):
    def __init__(self, color: str, size: int = 8):
        super().__init__()
        self.setFixedSize(size, size)
        self.setStyleSheet(f"background: {color}; border-radius: {size // 2}px;")


class LiveIndicator(QFrame):
    """Green pill that shows when data was last refreshed (auto refresh 5 s)."""

    def __init__(self, label: str = "Diperbarui 2 detik lalu", parent: QWidget | None = None):
        super().__init__(parent)
        t = TONES["green"]
        self.setObjectName("Live")
        self.setStyleSheet(
            f"QFrame#Live {{ background: {t.soft}; border: 1px solid {t.mid}; border-radius: 19px; }}"
        )
        lay = hbox(8, (12, 8, 14, 8), self)
        self._dot = _Dot(t.solid)
        lay.addWidget(self._dot)
        self.label = text(label, Type.CAPTION, t.ink)
        self.label.setFont(font(Type.CAPTION, weight=600))
        lay.addWidget(self.label)
        self._on = True
        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle)
        self._blink.start(900)

    def _toggle(self) -> None:
        self._on = not self._on
        color = TONES["green"].solid if self._on else TONES["green"].mid
        self._dot.setStyleSheet(f"background: {color}; border-radius: 4px;")

    def set_text(self, value: str) -> None:
        self.label.setText(value)


class UserChip(QFrame):
    """Avatar with initials, name and role."""

    def __init__(self, name: str = "Operasional", role: str = "", initials: str = "OP",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("UserChip")
        self.setStyleSheet(
            f"QFrame#UserChip {{ background: {Color.SURFACE}; border: 1px solid {Color.BORDER}; border-radius: 23px; }}"
        )
        lay = hbox(10, (4, 4, 12, 4), self)
        t = TONES["pink"]
        avatar = QLabel(initials)
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(font(Type.LABEL, weight=700))
        avatar.setStyleSheet(f"background: {t.mid}; color: {t.ink}; border-radius: 18px;")
        lay.addWidget(avatar)
        col = vbox(0)
        col.addWidget(text(name, Type.LABEL))
        if role:
            col.addWidget(text(role, Type.CAPTION, Color.TEXT_TERTIARY))
        lay.addLayout(col)


def event_kind(kind: str) -> QWidget:
    w = QWidget()
    lay = hbox(8, (0, 0, 0, 0), w)
    dot = _Dot(Color.CHART_NG if kind == "REJECT" else TONES["amber"].solid)
    lay.addWidget(dot)
    lay.addWidget(text(kind.replace("_", " "), Type.BODY_STRONG))
    return w
