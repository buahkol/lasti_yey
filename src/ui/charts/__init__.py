"""Painter-based charts (no extra dependency on PyQt6-Charts).

- StackedBarChart: OK and NG per hour (Dashboard)
- PeakBarChart: NG per hour with the peak highlighted (Laporan)
- Gauge: semicircle percentage against a limit (Laporan)
Hovering a bar shows its tooltip; moving the cursor away hides it again. Bar colours never change.
"""

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme import Color, Type, font


def _num(value: float) -> str:
    """Axis and tooltip numbers with a dot as thousands separator: 7500 -> '7.500'."""
    return f"{value:,.0f}".replace(",", ".") if value == int(value) else f"{value:g}"


def _grid_pen() -> QPen:
    pen = QPen(QColor(Color.CHART_GRID), 1)
    pen.setDashPattern([3, 4])
    return pen


def _draw_tooltip(p: QPainter, anchor: QPointF, bounds: QRectF, title: str, value: str, extra: str) -> None:
    f_title, f_value, f_extra = font(Type.CAPTION), font(Type.HEADING), font(Type.LABEL)
    m_t, m_v, m_e = QFontMetrics(f_title), QFontMetrics(f_value), QFontMetrics(f_extra)
    w = max(m_t.horizontalAdvance(title), m_v.horizontalAdvance(value) + 10 + m_e.horizontalAdvance(extra)) + 28
    h = m_t.height() + m_v.height() + 22
    x = anchor.x() + 14
    if x + w > bounds.right():
        x = anchor.x() - 14 - w
    y = max(bounds.top(), min(anchor.y() - h / 2, bounds.bottom() - h))
    rect = QRectF(x, y, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 40))
    p.drawRoundedRect(rect.translated(0, 6), 14, 14)
    p.setBrush(QColor(Color.BRAND_STRONG))
    p.drawRoundedRect(rect, 14, 14)
    p.setFont(f_title)
    p.setPen(QColor("#CDEBFF"))
    p.drawText(QPointF(x + 14, y + 10 + m_t.ascent()), title)
    p.setFont(f_value)
    p.setPen(QColor("#FFFFFF"))
    vy = y + 12 + m_t.height() + m_v.ascent()
    p.drawText(QPointF(x + 14, vy), value)
    p.setFont(f_extra)
    p.setPen(QColor(Color.PINK))
    p.drawText(QPointF(x + 14 + m_v.horizontalAdvance(value) + 10, vy), extra)


class _Animated(QWidget):
    def __init__(self):
        super().__init__()
        self._t = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(700)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)

    def _step(self, value: float) -> None:
        self._t = value
        self.update()

    def showEvent(self, e):  # noqa: N802
        self._anim.stop()
        self._t = 0.0
        self._anim.start()
        super().showEvent(e)


class _BarBase(_Animated):
    def __init__(self, labels: list, highlight: int):
        super().__init__()
        self.labels = labels
        self.highlight = highlight  # bar whose label is bold, for example the current hour
        self.hover: int | None = None  # bar under the cursor; its tooltip shows only while hovering
        self.setMouseTracking(True)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._axis_w = 34
        self._bottom = 26

    def _plot(self) -> QRectF:
        return QRectF(self._axis_w, 8, self.width() - self._axis_w, self.height() - 8 - self._bottom)

    def _col(self, i: int) -> QRectF:
        pr = self._plot()
        cw = pr.width() / len(self.labels)
        return QRectF(pr.left() + i * cw, pr.top(), cw, pr.height())

    def _axis(self, p: QPainter, max_v: float, ticks: list) -> None:
        pr = self._plot()
        p.setFont(font(Type.CAPTION))
        for tv in ticks:
            y = pr.bottom() - tv / max_v * pr.height()
            p.setPen(QPen(QColor(Color.CHART_GRID), 1) if tv == 0 else _grid_pen())
            p.drawLine(QPointF(pr.left(), y), QPointF(pr.right(), y))
            p.setPen(QColor(Color.TEXT_TERTIARY))
            p.drawText(QRectF(0, y - 9, self._axis_w - 8, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       _num(tv))
        for i, lab in enumerate(self.labels):
            c = self._col(i)
            on = i == self.highlight
            p.setFont(font(Type.CAPTION, weight=700 if on else 500))
            p.setPen(QColor(Color.TEXT_PRIMARY if on else Color.TEXT_TERTIARY))
            p.drawText(QRectF(c.left(), pr.bottom() + 6, c.width(), 18), Qt.AlignmentFlag.AlignHCenter, lab)

    def _set_hover(self, index: int | None) -> None:
        if index != self.hover:
            self.hover = index
            self.update()

    def mouseMoveEvent(self, e):  # noqa: N802
        pr = self._plot()
        x, y = e.position().x(), e.position().y()
        index = None
        if pr.left() <= x <= pr.right() and pr.top() <= y <= pr.bottom():
            i = int((x - pr.left()) / (pr.width() / len(self.labels)))
            if 0 <= i < len(self.labels) and self._has_data(i):
                index = i
        self._set_hover(index)

    def leaveEvent(self, e):  # noqa: N802
        self._set_hover(None)
        super().leaveEvent(e)

    def _has_data(self, i: int) -> bool:
        return True


class StackedBarChart(_BarBase):
    """data: list of (label, ok, ng)."""

    def __init__(self, data: list, highlight: int = 0, max_value: float = 200, title_prefix: str = "Pukul "):
        super().__init__([d[0] for d in data], highlight)
        self.data = data
        self.max_value = max_value
        self.title_prefix = title_prefix
        if max_value >= 1000:
            self._axis_w = 48  # room for labels such as 7.500

    def _has_data(self, i: int) -> bool:
        return self.data[i][1] > 0

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self.max_value
        self._axis(p, m, [0, m / 4, m / 2, m * 3 / 4, m])
        pr = self._plot()
        anchor = None
        for i, (lab, ok, ng) in enumerate(self.data):
            c = self._col(i)
            bw = min(34.0, c.width() * 0.5)
            x = c.center().x() - bw / 2
            hovered = i == self.hover
            if ok <= 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(Color.CHART_GRID))
                p.drawRoundedRect(QRectF(x, pr.bottom() - 3, bw, 3), 1.5, 1.5)
                continue
            h_total = ok / m * pr.height() * self._t
            h_ng = max(5.0, ng / m * pr.height() * 3) * self._t
            h_ok = h_total - h_ng - 2
            p.setPen(Qt.PenStyle.NoPen)
            ok_c = QColor(Color.CHART_OK)
            if hovered:
                ok_c = ok_c.darker(115)
            p.setBrush(ok_c)
            if h_ok > 0:
                p.drawRoundedRect(QRectF(x, pr.bottom() - h_ok, bw, h_ok), 5, 5)
            p.setBrush(QColor(Color.CHART_NG))
            p.drawRoundedRect(QRectF(x, pr.bottom() - h_total, bw, h_ng), 5, 5)
            if hovered:
                anchor = (QPointF(x + bw, pr.bottom() - h_total + 10), lab, ok, ng)
        if anchor:
            pt, lab, ok, ng = anchor
            _draw_tooltip(p, pt, QRectF(0, 0, self.width(), self.height()), f"{self.title_prefix}{lab}",
                          f"{_num(ok)} kaleng", f"{_num(ng)} NG")


class PeakBarChart(_BarBase):
    """data: list of (label, ng_count, output). The highest bar uses the indigo to magenta gradient."""

    def __init__(self, data: list, max_value: float = 12):
        peak = max(range(len(data)), key=lambda i: data[i][1])
        super().__init__([d[0] for d in data], peak)
        self.data = data
        self.peak = peak
        self.max_value = max_value

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self.max_value
        self._axis(p, m, [0, m / 4, m / 2, m * 3 / 4, m])
        pr = self._plot()
        anchor = None
        for i, (lab, ng, out) in enumerate(self.data):
            c = self._col(i)
            bw = min(48.0, c.width() * 0.45)
            x = c.center().x() - bw / 2
            h = ng / m * pr.height() * self._t
            rect = QRectF(x, pr.bottom() - h, bw, h)
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            path.addRoundedRect(rect, 10, 10)
            path.addRect(QRectF(x, rect.bottom() - 10, bw, 10))
            p.setPen(Qt.PenStyle.NoPen)
            if i == self.peak:
                g = QLinearGradient(0, rect.top(), 0, rect.bottom())
                g.setColorAt(0, QColor(Color.INDIGO))
                g.setColorAt(1, QColor(Color.MAGENTA))
                p.setBrush(g)
            else:
                p.setBrush(QColor(Color.PINK).darker(110) if i == self.hover else QColor(Color.PINK))
            p.drawPath(path.simplified())
            if i != self.hover:
                p.setFont(font(Type.CAPTION))
                p.setPen(QColor(Color.TEXT_SECONDARY))
                p.drawText(QRectF(c.left(), rect.top() - 22, c.width(), 18), Qt.AlignmentFlag.AlignHCenter, str(ng))
            else:
                anchor = (QPointF(x + bw, rect.top() + 6), lab, ng, out)
        if anchor:
            pt, lab, ng, out = anchor
            nxt = f"{int(lab[:2]) + 1:02d}.00"
            pct = f"{ng / out * 100:.1f}%".replace(".", ",") if out else "0%"
            _draw_tooltip(p, pt, QRectF(0, 0, self.width(), self.height()), f"Pukul {lab} sampai {nxt}",
                          f"{ng} NG dari {out}", pct)


class Gauge(_Animated):
    """Semicircle gauge: value and limit in the same unit (percent)."""

    def __init__(self, value: float, limit: float, maximum: float = 10.0):
        super().__init__()
        self.value, self.limit, self.maximum = value, limit, maximum
        self.setFixedSize(320, 212)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r, cx, cy, thick = 136.0, self.width() / 2, 172.0, 24.0
        rect = QRectF(cx - r + thick / 2, cy - r + thick / 2, 2 * r - thick, 2 * r - thick)
        pen = QPen(QColor(Color.CANVAS), thick)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, 180 * 16, -180 * 16)
        frac = max(0.0, min(1.0, self.value / self.maximum)) * self._t
        g = QLinearGradient(rect.left(), 0, rect.right(), 0)
        g.setColorAt(0, QColor(Color.INDIGO))
        g.setColorAt(0.7, QColor(Color.MAGENTA))
        pen = QPen(g, thick)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, 180 * 16, int(-180 * 16 * frac))
        # limit marker
        ang = math.pi * (1 - self.limit / self.maximum)
        x1, y1 = cx + (r + 6) * math.cos(ang), cy - (r + 6) * math.sin(ang)
        x2, y2 = cx + (r - thick - 6) * math.cos(ang), cy - (r - thick - 6) * math.sin(ang)
        p.setPen(QPen(QColor(Color.ICON_STRONG), 2))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.setFont(font(Type.CAPTION))
        p.setPen(QColor(Color.TEXT_SECONDARY))
        lim = f"batas {self.limit:g}%".replace(".", ",")
        p.drawText(QRectF(x1 - 60, y1 - 22, 120, 18), Qt.AlignmentFlag.AlignHCenter, lim)
        p.setFont(font(Type.DISPLAY))
        p.setPen(QColor(Color.TEXT_PRIMARY))
        p.drawText(QRectF(0, cy - 62, self.width(), 40), Qt.AlignmentFlag.AlignHCenter,
                   f"{self.value * self._t:.1f}%".replace(".", ","))
        p.setFont(font(Type.CAPTION))
        p.setPen(QColor(Color.TEXT_TERTIARY))
        p.drawText(QRectF(0, cy - 22, self.width(), 18), Qt.AlignmentFlag.AlignHCenter, "persentase NG")
        p.setPen(QColor(Color.TEXT_TERTIARY))
        for edge, label in ((rect.left(), "0%"), (rect.right(), f"{self.maximum:g}%")):
            p.drawText(QRectF(edge - 30, cy + 8, 60, 18), Qt.AlignmentFlag.AlignHCenter, label)


__all__ = ["StackedBarChart", "PeakBarChart", "Gauge"]
