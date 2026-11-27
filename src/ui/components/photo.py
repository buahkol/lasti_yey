"""Can photo placeholder, AlertRow and DefectCard.

``CanPhoto`` shows the real inspection photo (``GET /inspections/{id}/photo``) when it is given an
``inspection_id`` and the app has registered a loader with ``set_photo_loader``. Without one (sample
data, or the photo is missing) it paints a stand-in can with the PatchCore anomaly highlight.
"""

from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import QFrame, QSizePolicy, QWidget

from .. import formatting as fmt
from ..theme import TONES, Color, Type
from .base import add_shadow, hbox, text, vbox
from .buttons import IconButton
from .progress import ProgressBar
from .status import Badge

_W, _H = 240.0, 170.0
THUMB_MAX_WIDTH = 320  # smaller widgets ask the server for the thumbnail

_loader: Callable[[int, bool], bytes | None] | None = None
_pixmaps: dict[tuple[int, bool], QPixmap | None] = {}


def set_photo_loader(loader: Callable[[int, bool], bytes | None] | None) -> None:
    """loader(inspection_id, thumb) -> JPEG bytes or None. None turns real photos off (sample data)."""
    global _loader
    _loader = loader
    _pixmaps.clear()


def real_photos() -> bool:
    """True when camera photos are shown (API mode) instead of painted placeholders."""
    return _loader is not None


def _photo(inspection_id: int, thumb: bool) -> QPixmap | None:
    key = (inspection_id, thumb)
    if key not in _pixmaps:
        pm = None
        try:
            data = _loader(inspection_id, thumb) if _loader else None
        except Exception:  # noqa: BLE001 - a photo that cannot be loaded falls back to the placeholder
            data = None
        if data:
            pm = QPixmap()
            if not pm.loadFromData(data):
                pm = None
        _pixmaps[key] = pm
    return _pixmaps[key]
_HEAT = {"dent": (77, 68, 70), "rust": (154, 116, 60), "label": (164, 86, 70)}


class CanPhoto(QWidget):
    """Photo area. defect: dent | rust | label | none. radius: (tl, tr, br, bl)."""

    def __init__(self, defect: str = "dent", radius=(12, 12, 12, 12), heatmap: bool = True,
                 parent: QWidget | None = None, inspection_id: int | None = None):
        super().__init__(parent)
        self.defect = defect
        self.inspection_id = inspection_id
        self.radius = radius
        self.heatmap = heatmap
        self._pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def has_real_photo(self) -> bool:
        """True when a camera photo is (or can be) shown instead of the painted placeholder."""
        return bool(self._pixmap or (self.inspection_id and _loader and _photo(self.inspection_id, False)))

    def set_pixmap(self, pm: QPixmap | None) -> None:
        self._pixmap = pm
        self.update()

    def set_heatmap(self, on: bool) -> None:
        self.heatmap = on
        self.update()

    def _clip(self) -> QPainterPath:
        w, h = self.width(), self.height()
        tl, tr, br, bl = self.radius
        path = QPainterPath()
        path.moveTo(tl, 0)
        path.lineTo(w - tr, 0)
        path.quadTo(w, 0, w, tr)
        path.lineTo(w, h - br)
        path.quadTo(w, h, w - br, h)
        path.lineTo(bl, h)
        path.quadTo(0, h, 0, h - bl)
        path.lineTo(0, tl)
        path.quadTo(0, 0, tl, 0)
        return path

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipPath(self._clip())
        w, h = self.width(), self.height()
        pixmap = self._pixmap
        if pixmap is None and self.inspection_id and _loader:
            pixmap = _photo(self.inspection_id, w <= THUMB_MAX_WIDTH)
        if pixmap:
            scaled = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int((w - scaled.width()) / 2), int((h - scaled.height()) / 2), scaled)
            return
        # background (photo box)
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#2B3440"))
        bg.setColorAt(1, QColor("#151B22"))
        p.fillRect(self.rect(), bg)
        # scale design space with "cover" behaviour, centred
        s = max(w / _W, h / _H)
        p.translate((w - _W * s) / 2, (h - _H * s) / 2)
        p.scale(s, s)
        glow = QRadialGradient(QPointF(120, 60), 120)
        glow.setColorAt(0, QColor(91, 104, 120, 140))
        glow.setColorAt(1, QColor(91, 104, 120, 0))
        p.fillRect(QRectF(0, 0, _W, _H), glow)
        floor = QLinearGradient(0, 124, 0, 170)
        floor.setColorAt(0, QColor(29, 36, 44, 0))
        floor.setColorAt(1, QColor(14, 18, 23, 255))
        p.fillRect(QRectF(0, 124, _W, 46), floor)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawEllipse(QRectF(45, 126, 150, 16))
        # can body
        metal = QLinearGradient(45, 0, 195, 0)
        for pos, c in ((0, "#9AA6B2"), (0.22, "#E9EEF2"), (0.5, "#B7C1CB"), (0.72, "#F4F7F9"), (1, "#8E9AA6")):
            metal.setColorAt(pos, QColor(c))
        p.setBrush(metal)
        p.drawRoundedRect(QRectF(45, 58, 150, 74), 14, 14)
        rim = QLinearGradient(45, 0, 195, 0)
        for pos, c in ((0, "#C9D2DA"), (0.5, "#FFFFFF"), (1, "#AAB5C0")):
            rim.setColorAt(pos, QColor(c))
        p.setBrush(rim)
        p.drawRoundedRect(QRectF(45, 56, 150, 10), 6, 6)
        label = QLinearGradient(45, 0, 195, 0)
        for pos, c in ((0, "#B5383F"), (0.3, "#D9534F"), (0.55, "#E36A60"), (1, "#B5383F")):
            label.setColorAt(pos, QColor(c))
        p.setBrush(label)
        p.drawRect(QRectF(45, 74, 150, 40))
        p.setBrush(QColor(255, 237, 204, 215))
        p.drawRoundedRect(QRectF(90, 86, 60, 8), 4, 4)
        p.setBrush(QColor(255, 237, 204, 150))
        p.drawRoundedRect(QRectF(102, 99, 36, 4), 2, 2)
        # defect
        if self.defect == "dent":
            p.setBrush(QColor(64, 72, 82, 140))
            p.drawEllipse(QRectF(64, 60, 26, 18))
        elif self.defect == "rust":
            p.setBrush(QColor(138, 75, 30, 215))
            for x, y, d in ((150, 112, 10), (160, 118, 7), (143, 118, 5)):
                p.drawEllipse(QRectF(x, y, d, d * 0.8))
        elif self.defect == "label":
            p.setBrush(QColor("#DDE3E8"))
            p.drawPolygon(QPolygonF([QPointF(150, 74), QPointF(182, 76), QPointF(170, 104)]))
        if self.heatmap and self.defect in _HEAT:
            x, y, d = _HEAT[self.defect]
            heat = QRadialGradient(QPointF(x, y), d / 2)
            heat.setColorAt(0, QColor(253, 49, 174, 190))
            heat.setColorAt(0.5, QColor(244, 179, 205, 90))
            heat.setColorAt(1, QColor(244, 179, 205, 0))
            p.setBrush(QBrush(heat))
            p.drawEllipse(QPointF(x, y), d / 2, d * 0.4)
            pen = QPen(QColor(Color.MAGENTA), 1.25)
            pen.setDashPattern([3, 3])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, y), d * 0.31, d * 0.25)
        p.resetTransform()
        vig = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.75)
        vig.setColorAt(0.6, QColor(0, 0, 0, 0))
        vig.setColorAt(1, QColor(0, 0, 0, 110))
        p.fillRect(self.rect(), vig)


class AlertRow(QFrame):
    """List row for one NG can: thumbnail, batch, time and bold pink score."""

    clicked = pyqtSignal()

    def __init__(self, batch: str, time: str, score: str, defect: str = "dent",
                 highlight: bool = False, parent: QWidget | None = None, inspection_id: int | None = None):
        super().__init__(parent)
        self.setObjectName("AlertRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        bg = "rgba(255,233,245,0.6)" if highlight else "transparent"
        self.setStyleSheet(
            f"QFrame#AlertRow {{ background: {bg}; border-radius: 14px; }}"
            f"QFrame#AlertRow:hover {{ background: {TONES['blue'].soft}; }}"
        )
        lay = hbox(12, (8, 8, 12, 8), self)
        thumb = CanPhoto(defect, (12, 12, 12, 12), heatmap=True, inspection_id=inspection_id)
        thumb.setFixedSize(52, 48)
        lay.addWidget(thumb)
        col = vbox(2)
        col.addWidget(text(batch, Type.BODY_STRONG))
        col.addWidget(text(time, Type.CAPTION, Color.TEXT_TERTIARY))
        lay.addLayout(col, 1)
        sc = vbox(0)
        s = text(score, Type.HEADING, TONES["pink"].ink, align=Qt.AlignmentFlag.AlignRight)
        sc.addWidget(s)
        sc.addWidget(text("skor anomali", Type.CAPTION, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignRight))
        lay.addLayout(sc)

    def mouseReleaseEvent(self, e):  # noqa: N802
        self.clicked.emit()
        super().mouseReleaseEvent(e)


class DefectCard(QFrame):
    """Card for one inspected can with photo, batch, time and score bar. result is NG (pink) or OK (indigo)."""

    clicked = pyqtSignal()

    def __init__(self, batch: str, time: str, score: float, threshold: float, defect: str = "dent",
                 highlight: bool = False, parent: QWidget | None = None, result: str = "NG",
                 inspection_id: int | None = None):
        super().__init__(parent)
        self.setObjectName("DefectCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = f"2px solid {Color.CHART_NG}" if highlight else f"1px solid {Color.BORDER}"
        self.setStyleSheet(f"QFrame#DefectCard {{ background: {Color.SURFACE}; border: {border}; border-radius: 18px; }}")
        add_shadow(self)
        lay = vbox(0, (1, 1, 1, 1), self)
        self.photo = CanPhoto(defect, (17, 17, 0, 0), inspection_id=inspection_id)
        self.photo.setMinimumHeight(190)
        lay.addWidget(self.photo, 1)
        self._badge = Badge(result, self.photo)
        self._badge.move(12, 12)
        self._expand = IconButton("expand", "Lihat foto penuh", "outline", 34, parent=self.photo)
        self._expand.clicked.connect(self.clicked)
        info = vbox(10, (14, 12, 14, 14))
        r1 = hbox(8)
        r1.addWidget(text(batch, Type.HEADING), 1)
        r1.addWidget(text(time, Type.CAPTION, Color.TEXT_TERTIARY))
        info.addLayout(r1)
        bar = ProgressBar("Skor", f"{score:.2f}".replace(".", ","), score, "pink" if result == "NG" else "indigo",
                          suffix=f"ambang {fmt.threshold(threshold)}")
        info.addWidget(bar)
        lay.addLayout(info)

    def resizeEvent(self, e):  # noqa: N802
        self._expand.move(self.photo.width() - 34 - 12, 12)
        super().resizeEvent(e)

    def mouseReleaseEvent(self, e):  # noqa: N802
        self.clicked.emit()
        super().mouseReleaseEvent(e)

