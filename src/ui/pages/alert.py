"""Alert (FR-22, FR-23): latest NG cans with photo and anomaly score."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from ...controllers import AlertController
from .. import formatting as fmt
from ..assets import pixmap
from ..components import (
    AdaptiveRow, Button, DefectCard, LiveIndicator, ResponsiveGrid, SegmentedTabs, StatCard, hbox, text, toast, vbox,
)
from ..shell import Page
from ..theme import Color, Type
from .common import open_photo_viewer


class _DashedRing(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(16, 14)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(Color.MAGENTA), 1.5)
        pen.setDashPattern([2, 2])
        p.setPen(pen)
        p.drawEllipse(1, 1, 13, 11)


class _OlderTile(QFrame):
    def __init__(self, on_click):
        super().__init__()
        self.setObjectName("Older")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"QFrame#Older {{ background: rgba(255,255,255,0.6); border: 1px dashed {Color.BORDER_STRONG};"
                           " border-radius: 18px; }")
        lay = vbox(8, (16, 16, 16, 16), self)
        lay.addStretch(1)
        ic = QLabel()
        ic.setPixmap(pixmap("history", Color.ICON, 24))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        lay.addWidget(text("Alert sebelumnya", Type.HEADING, align=Qt.AlignmentFlag.AlignCenter))
        lay.addWidget(text("Lihat di halaman Riwayat dan klaim", Type.CAPTION, Color.TEXT_TERTIARY,
                           align=Qt.AlignmentFlag.AlignCenter))
        lay.addStretch(1)
        self._on_click = on_click

    def mouseReleaseEvent(self, e):  # noqa: N802
        self._on_click()
        super().mouseReleaseEvent(e)


class AlertPage(Page):
    def __init__(self, controller: AlertController, window_getter):
        super().__init__("Alert kemasan cacat")
        self._ctrl = controller
        self._win = window_getter
        self.actions.addWidget(LiveIndicator())
        self.actions.addWidget(Button("30 menit terakhir", "outline", "md", "clock"))

        a = self._ctrl.summary()
        stats = ResponsiveGrid(220, 4, 16, steps=(4, 2, 1))
        stats.add(StatCard("pink", "warning", "NG 30 menit terakhir", str(a["ng_30min"]), "kaleng",
                           a["ng_delta"], f"sejak pukul {a['since']}", "trend-up", highlight_value=True))
        stats.add(StatCard("indigo", "activity", "Skor anomali rata-rata", fmt.score(a["avg_score"]),
                           "", "ambang 0,62", "B-2411-01"))
        stats.add(StatCard("blue", "trend-up", "Skor tertinggi", fmt.score(a["top_score"]), "",
                           a["top_batch"], f"pukul {a['top_time']}"))
        stats.add(StatCard("amber", "layers", "Batch terdampak", str(a["affected_batches"]), "batch", "HOLD",
                           "B-2411-01 dan B-2411-02"))
        self.body.addWidget(stats)

        bar = AdaptiveRow(spacing=12)
        batches = self._ctrl.batches()
        items = [("Semua batch", str(len(self._ctrl.alerts())))] + [
            (b, str(len(self._ctrl.alerts(b)))) for b in batches]
        self._batches = [None] + batches
        tabs = SegmentedTabs(items)
        tabs.changed.connect(self._filter)
        bar.add(tabs, 0, align=Qt.AlignmentFlag.AlignLeft)
        bar.add_stretch()
        legend = QWidget()
        l_lay = hbox(8, (0, 0, 0, 0), legend)
        l_lay.addWidget(_DashedRing())
        l_lay.addWidget(text("Area skor anomali tertinggi dari PatchCore", Type.CAPTION, Color.TEXT_SECONDARY))
        bar.add(legend, 0, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.body.addWidget(bar)

        self.grid = ResponsiveGrid(250, 4, 16, steps=(4, 3, 2, 1))
        self.body.addWidget(self.grid, 1)
        self._filter(0)

    def _filter(self, index: int) -> None:
        batch = self._batches[index]
        self.grid.clear()
        for i, al in enumerate(self._ctrl.alerts(batch)):
            card = DefectCard(al.batch, al.time, al.score, al.threshold, al.defect, highlight=i == 0 and batch is None)
            card.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            self.grid.add(card)
        self.grid.add(_OlderTile(lambda: toast(self._win(), "info", "Riwayat dan klaim",
                                               "Halaman ini dikerjakan pada Desktop P2.")))
