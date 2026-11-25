"""StatCard and PanelHeader."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from ..assets import pixmap
from ..theme import TONES, Color, Type, font
from .base import add_shadow, hbox, set_text_color, text, vbox
from .buttons import Button

# light tint used in the top-left gradient of each stat card
_TINT = {
    "blue": "rgba(205,235,255,0.75)",
    "green": "rgba(205,239,228,0.75)",
    "pink": "rgba(251,214,229,0.75)",
    "indigo": "rgba(220,221,251,0.75)",
    "amber": "rgba(248,227,190,0.75)",
}


class StatCard(QFrame):
    """White card with a thin tinted gradient that hints its meaning.

    tone: blue (output) | indigo (OK) | pink (NG) | amber (HOLD / kerugian) | green
    highlight_value: colour the number with the tone ink (only for important numbers)
    """

    def __init__(self, tone: str, icon_name: str, label: str, value: str, unit: str = "",
                 delta: str = "", meta: str = "", delta_icon: str | None = None,
                 highlight_value: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        t = TONES[tone]
        self.setObjectName("StatCard")
        self.setStyleSheet(
            "QFrame#StatCard {"
            f" background: qlineargradient(x1:0, y1:0, x2:0.7, y2:0.9, stop:0 {_TINT[tone]}, stop:0.65 #FFFFFF);"
            f" border: 1px solid {Color.BORDER}; border-radius: 20px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        add_shadow(self)
        lay = vbox(10, (18, 16, 18, 16), self)

        head = hbox(10)
        chip = QLabel()
        chip.setFixedSize(38, 38)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(pixmap(icon_name, t.ink, 20))
        chip.setStyleSheet(f"background: {t.soft}; border: 1px solid {t.mid}; border-radius: 12px;")
        head.addWidget(chip)
        self.label = text(label, Type.LABEL, Color.TEXT_SECONDARY)
        self.label.setFont(font(Type.LABEL, size=14))
        head.addWidget(self.label, 1)
        lay.addLayout(head)

        row = hbox(6)
        self.value = text(value, Type.DISPLAY, t.ink if highlight_value else Color.TEXT_PRIMARY)
        row.addWidget(self.value, 0, Qt.AlignmentFlag.AlignBottom)
        self.unit = text(unit, Type.LABEL, Color.TEXT_TERTIARY)
        self.unit.setVisible(bool(unit))
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)

        foot = hbox(8)
        self.delta = QFrame()
        self.delta.setObjectName("Delta")
        self.delta.setStyleSheet(
            f"QFrame#Delta {{ background: {t.soft}; border: 1px solid {t.mid}; border-radius: 11px; }}"
        )
        d_lay = hbox(4, (8, 2, 10, 2), self.delta)
        if delta_icon:
            di = QLabel()
            di.setPixmap(pixmap(delta_icon, t.ink, 14))
            d_lay.addWidget(di)
        self.delta_text = text(delta, Type.CAPTION, t.ink)
        self.delta_text.setFont(font(Type.CAPTION, weight=700))
        d_lay.addWidget(self.delta_text)
        self.delta.setVisible(bool(delta))
        foot.addWidget(self.delta)
        self.meta = text(meta, Type.CAPTION, Color.TEXT_TERTIARY)
        foot.addWidget(self.meta, 1)
        lay.addLayout(foot)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class PanelHeader(QWidget):
    """Panel title, subtitle and an optional "Lihat semua" style action (text then arrow)."""

    action_clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str = "", action: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        lay = hbox(12, (0, 0, 0, 0), self)
        col = vbox(2)
        self.title = text(title, Type.TITLE)
        col.addWidget(self.title)
        self.subtitle = text(subtitle, Type.CAPTION, Color.TEXT_TERTIARY)
        self.subtitle.setVisible(bool(subtitle))
        col.addWidget(self.subtitle)
        lay.addLayout(col, 1)
        if action:
            self.action = Button(action, "ghost", "sm", "chevron-right", trailing=True)
            self.action.clicked.connect(self.action_clicked)
            lay.addWidget(self.action, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_subtitle(self, value: str) -> None:
        self.subtitle.setText(value)
        set_text_color(self.subtitle, Color.TEXT_TERTIARY)
