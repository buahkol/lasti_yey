"""Alert (FR-22, FR-23): latest NG cans with photo and anomaly score."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from .. import mock_data as data
from ..assets import pixmap
from ..components import Button, DefectCard, LiveIndicator, SegmentedTabs, StatCard, hbox, text, toast, vbox
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
    def __init__(self, window_getter):
        super().__init__("Alert kemasan cacat")
        self._win = window_getter
        self.actions.addWidget(LiveIndicator())
        self.actions.addWidget(Button("30 menit terakhir", "outline", "md", "clock"))

        a = data.ALERT_SUMMARY
        stats = hbox(16)
        stats.addWidget(StatCard("pink", "warning", "NG 30 menit terakhir", str(a["ng_30min"]), "kaleng",
                                 a["ng_delta"], f"sejak pukul {a['since']}", "trend-up", highlight_value=True))
        stats.addWidget(StatCard("indigo", "activity", "Skor anomali rata-rata", f"{a['avg_score']:.2f}".replace(".", ","),
                                 "", "ambang 0,62", "B-2411-01"))
        stats.addWidget(StatCard("blue", "trend-up", "Skor tertinggi", f"{a['top_score']:.2f}".replace(".", ","), "",
                                 a["top_batch"], f"pukul {a['top_time']}"))
        stats.addWidget(StatCard("amber", "layers", "Batch terdampak", str(a["affected_batches"]), "batch", "HOLD",
                                 "B-2411-01 dan B-2411-02"))
        self.body.addLayout(stats)

        bar = hbox(12)
        batches = sorted({al[0] for al in data.ALERTS})
        items = [("Semua batch", str(len(data.ALERTS)))] + [
            (b, str(sum(1 for al in data.ALERTS if al[0] == b))) for b in batches]
        self._batches = [None] + batches
        tabs = SegmentedTabs(items)
        tabs.changed.connect(self._filter)
        bar.addWidget(tabs)
        bar.addStretch(1)
        bar.addWidget(_DashedRing())
        bar.addWidget(text("Area skor anomali tertinggi dari PatchCore", Type.CAPTION, Color.TEXT_SECONDARY))
        self.body.addLayout(bar)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(16)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(self.grid_host, 1)
        self._filter(0)

    def _filter(self, index: int) -> None:
        batch = self._batches[index]
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        alerts = [al for al in data.ALERTS if batch is None or al[0] == batch]
        for i, al in enumerate(alerts):
            code, time, score, thr, defect = al
            card = DefectCard(code, time, score, thr, defect, highlight=i == 0 and batch is None)
            card.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            self.grid.addWidget(card, i // 4, i % 4)
        n = len(alerts)
        older = _OlderTile(lambda: toast(self._win(), "info", "Riwayat dan klaim",
                                         "Halaman ini dikerjakan pada Desktop P2."))
        self.grid.addWidget(older, n // 4, n % 4)
        for c in range(4):
            self.grid.setColumnStretch(c, 1)
