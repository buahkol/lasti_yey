"""Overlay (modal with scrim), StatusDialog and Toast."""

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from ..assets import pixmap
from ..theme import TONES, Color, Type
from .base import add_shadow, hbox, text, vbox
from .buttons import Button, IconButton


class Overlay(QWidget):
    """Dims the window and shows a centred content widget. Esc or a click on the scrim closes it."""

    closed = pyqtSignal()

    def __init__(self, window: QWidget, content: QWidget, dismiss_on_scrim: bool = True):
        super().__init__(window)
        self._content = content
        self._dismiss = dismiss_on_scrim
        content.setParent(self)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        window.installEventFilter(self)
        self.setGeometry(window.rect())
        self._center()

    def open(self) -> "Overlay":
        self.show()
        self.raise_()
        self.setFocus()
        return self

    def close_overlay(self) -> None:
        self.parent().removeEventFilter(self)
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def _center(self) -> None:
        self._content.adjustSize()
        c = self._content
        c.move(int((self.width() - c.width()) / 2), int((self.height() - c.height()) / 2))

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
            self._center()
        return False

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(23, 42, 58, 115))

    def mousePressEvent(self, e):  # noqa: N802
        if self._dismiss and not self._content.geometry().contains(e.position().toPoint()):
            self.close_overlay()

    def keyPressEvent(self, e):  # noqa: N802
        if e.key() == Qt.Key.Key_Escape:
            self.close_overlay()
        else:
            super().keyPressEvent(e)


class ModalCard(QFrame):
    """White rounded modal surface with a soft indigo wash at the top."""

    def __init__(self, width: int, padding=(28, 24, 28, 24), spacing: int = 16):
        super().__init__()
        self.setObjectName("Modal")
        self.setFixedWidth(width)
        self.setStyleSheet(
            "QFrame#Modal { background: qlineargradient(x1:0, y1:0, x2:0, y2:0.35, "
            "stop:0 rgba(220,221,251,0.6), stop:1 #FFFFFF); border-radius: 24px; }"
        )
        add_shadow(self, "pop")
        self.body = vbox(spacing, padding, self)

    def header(self, icon_name: str, title: str, subtitle: str, on_close) -> None:
        row = hbox(12)
        chip = QLabel()
        chip.setFixedSize(44, 44)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(pixmap(icon_name, "#FFFFFF", 22))
        chip.setStyleSheet(f"background: {Color.PRIMARY}; border-radius: 12px;")
        row.addWidget(chip)
        col = vbox(2)
        col.addWidget(text(title, Type.TITLE))
        col.addWidget(text(subtitle, Type.CAPTION, Color.TEXT_TERTIARY))
        row.addLayout(col, 1)
        close = IconButton("x", "Tutup", "ghost")
        close.clicked.connect(on_close)
        row.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(row)


class _IconHalo(QWidget):
    def __init__(self, icon_name: str, tone: str):
        super().__init__()
        self._icon = icon_name
        self._tone = TONES[tone]
        self.setFixedSize(160, 120)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(80, 60)
        p.setPen(QPen(QColor(self._tone.mid), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r in (75, 55):
            p.drawEllipse(c, r, r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._tone.solid))
        p.drawEllipse(c, 32, 32)
        p.drawPixmap(QRectF(66, 46, 28, 28).toRect(), pixmap(self._icon, "#FFFFFF", 28, 2.2))


class StatusDialog(QFrame):
    """Success / failed / confirm pop-up. kind: success | failed | confirm."""

    _KIND = {"success": ("green", "check", "#E2F5F0"), "failed": ("pink", "x", "#FFE9F5"),
             "confirm": ("amber", "lock", "#FCF2E1")}

    def __init__(self, kind: str, title: str, body: str, actions: list):
        """actions: list of (label, variant, callback)."""
        super().__init__()
        tone, icon_name, head = self._KIND[kind]
        self.setObjectName("Status")
        self.setFixedWidth(420)
        self.setStyleSheet("QFrame#Status { background: #FFFFFF; border-radius: 24px; }")
        add_shadow(self, "pop")
        lay = vbox(0, (0, 0, 0, 0), self)
        top = QFrame()
        top.setObjectName("Head")
        top.setStyleSheet(
            "QFrame#Head { border-top-left-radius: 24px; border-top-right-radius: 24px; "
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {head}, stop:1 #FFFFFF); }}"
        )
        t_lay = hbox(0, (0, 18, 0, 6), top)
        t_lay.addStretch(1)
        t_lay.addWidget(_IconHalo(icon_name, tone))
        t_lay.addStretch(1)
        lay.addWidget(top)
        body_lay = vbox(8, (28, 8, 28, 24))
        body_lay.addWidget(text(title, Type.TITLE, align=Qt.AlignmentFlag.AlignCenter))
        body_lay.addWidget(text(body, Type.BODY, Color.TEXT_SECONDARY, wrap=True, align=Qt.AlignmentFlag.AlignCenter))
        body_lay.addSpacing(14)
        row = hbox(10)
        for label, variant, cb in actions:
            b = Button(label, variant)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(cb)
            row.addWidget(b)
        body_lay.addLayout(row)
        lay.addLayout(body_lay)


def show_status(window: QWidget, kind: str, title: str, body: str, actions: list | None = None) -> Overlay:
    """Convenience: open a StatusDialog. actions callbacks receive no args; overlay closes after."""
    holder: dict = {}

    def wrap(cb):
        def run():
            holder["o"].close_overlay()
            if cb:
                cb()
        return run

    actions = actions or [("Tutup", "primary", None)]
    dialog = StatusDialog(kind, title, body, [(lbl, var, wrap(cb)) for lbl, var, cb in actions])
    holder["o"] = Overlay(window, dialog).open()
    return holder["o"]


class Toast(QFrame):
    """Short notification at the top right; hides after 4 seconds."""

    _KIND = {"success": ("green", "check-circle"), "error": ("pink", "x-circle"), "info": ("blue", "bell")}

    def __init__(self, window: QWidget, kind: str, title: str, body: str = ""):
        super().__init__(window)
        tone, icon_name = self._KIND[kind]
        t = TONES[tone]
        self.setObjectName("Toast")
        self.setFixedWidth(400)
        self.setStyleSheet(
            f"QFrame#Toast {{ background: #FFFFFF; border: 1px solid {t.mid}; border-left: 5px solid {t.solid};"
            " border-radius: 16px; }"
        )
        add_shadow(self, "pop")
        lay = hbox(12, (14, 14, 12, 14), self)
        chip = QLabel()
        chip.setFixedSize(40, 40)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(pixmap(icon_name, t.ink, 20))
        chip.setStyleSheet(f"background: {t.soft}; border-radius: 12px;")
        lay.addWidget(chip)
        col = vbox(2)
        col.addWidget(text(title, Type.HEADING))
        if body:
            col.addWidget(text(body, Type.CAPTION, Color.TEXT_SECONDARY, wrap=True))
        lay.addLayout(col, 1)
        close = IconButton("x", "Tutup", "ghost", 30, Color.ICON)
        close.clicked.connect(self.deleteLater)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self.adjustSize()
        self.move(window.width() - self.width() - 28, 28)
        self.show()
        self.raise_()
        QTimer.singleShot(4000, self.deleteLater)


def toast(window: QWidget, kind: str, title: str, body: str = "") -> Toast:
    return Toast(window, kind, title, body)


__all__ = ["Overlay", "ModalCard", "StatusDialog", "show_status", "Toast", "toast"]
