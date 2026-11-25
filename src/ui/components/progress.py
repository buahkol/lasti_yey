"""ProgressBar: label on the left, bold value on the right, 8px track, optional marker."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget

from ..theme import TONES, Color, Type
from .base import hbox, set_text_color, text, vbox


class _Track(QWidget):
    def __init__(self, fill: list, track: str, marker_color: str):
        super().__init__()
        self.setFixedHeight(14)
        self.fraction = 0.0
        self.marker = None
        self._fill = fill
        self._track = track
        self._marker_color = marker_color

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        y = 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._track) if isinstance(self._track, str) else self._track)
        p.drawRoundedRect(QRectF(0, y, w, 8), 4, 4)
        fw = max(4.0, w * max(0.0, min(1.0, self.fraction)))
        if len(self._fill) > 1:
            g = QLinearGradient(0, 0, fw, 0)
            for i, c in enumerate(self._fill):
                g.setColorAt(i / (len(self._fill) - 1), QColor(c))
            p.setBrush(g)
        else:
            p.setBrush(QColor(self._fill[0]))
        p.drawRoundedRect(QRectF(0, y, fw, 8), 4, 4)
        if self.marker is not None:
            x = max(1.0, min(w - 1.0, w * self.marker))
            p.setBrush(QColor(self._marker_color))
            p.drawRoundedRect(QRectF(x - 1, 0, 2, 14), 1, 1)


class ProgressBar(QWidget):
    """Design-system progress bar.

    tone: blue | green | pink | amber | indigo
    fraction: 0..1 fill; marker: 0..1 position of the limit marker (or None)
    on_dark: white text and translucent track (used on the navy batch card)
    """

    def __init__(self, label: str, value: str, fraction: float, tone: str = "indigo",
                 suffix: str = "", caption: str = "", marker: float | None = None,
                 on_dark: bool = False, fill_colors: list | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        t = TONES[tone]
        strong = tone in ("pink", "amber")
        lay = vbox(6, (0, 0, 0, 0), self)
        top = hbox(6)
        label_color = "rgba(255,255,255,0.78)" if on_dark else Color.TEXT_SECONDARY
        value_color = "#FFFFFF" if on_dark else (t.ink if strong else Color.TEXT_PRIMARY)
        self.label = text(label, Type.LABEL, label_color)
        top.addWidget(self.label)
        top.addStretch(1)
        self.value = text(value, Type.HEADING, value_color)
        top.addWidget(self.value, 0, Qt.AlignmentFlag.AlignBottom)
        self.suffix = text(suffix, Type.CAPTION, "rgba(255,255,255,0.66)" if on_dark else Color.TEXT_TERTIARY)
        self.suffix.setVisible(bool(suffix))
        top.addWidget(self.suffix, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(top)
        track_color = QColor(255, 255, 255, 46) if on_dark else t.mid
        self.track = _Track(fill_colors or [t.solid], track_color, "#FFFFFF" if on_dark else t.ink)
        self.track.fraction = fraction
        self.track.marker = marker
        lay.addWidget(self.track)
        self.caption = text(caption, Type.CAPTION, t.ink if strong else Color.TEXT_SECONDARY, wrap=True)
        self.caption.setVisible(bool(caption))
        lay.addWidget(self.caption)

    def set_value(self, value: str, fraction: float) -> None:
        self.value.setText(value)
        self.track.fraction = fraction
        self.track.update()

    def set_value_size(self, px: int) -> None:
        f = self.value.font()
        f.setPixelSize(px)
        self.value.setFont(f)

    def set_label_color(self, color: str) -> None:
        set_text_color(self.label, color)
