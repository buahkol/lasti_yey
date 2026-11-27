"""Alert (FR-22, FR-23): latest NG cans with photo and anomaly score."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from ...controllers import AlertController
from ...controllers.alert_controller import WINDOWS
from .. import formatting as fmt
from ..components import AdaptiveRow, DefectCard, LiveIndicator, ResponsiveGrid, SegmentedTabs, StatCard, hbox, text
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


def _and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " dan " + items[-1]


class AlertPage(Page):
    def __init__(self, controller: AlertController, window_getter):
        super().__init__("Alert kemasan cacat")
        self._ctrl = controller
        self._win = window_getter
        self.window = 0
        self.actions.addWidget(LiveIndicator())

        self.stats = ResponsiveGrid(220, 4, 16, steps=(4, 2, 1))
        self.body.addWidget(self.stats)

        bar = AdaptiveRow(spacing=12)
        self.tabs = SegmentedTabs([(label, "0") for label, _ in WINDOWS])
        self.tabs.changed.connect(self._set_window)
        bar.add(self.tabs, 0, align=Qt.AlignmentFlag.AlignLeft)
        bar.add_stretch()
        legend = QWidget()
        l_lay = hbox(8, (0, 0, 0, 0), legend)
        l_lay.addWidget(_DashedRing())
        l_lay.addWidget(text("Area skor anomali tertinggi dari PatchCore", Type.CAPTION, Color.TEXT_SECONDARY))
        bar.add(legend, 0, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.body.addWidget(bar)

        self.grid = ResponsiveGrid(250, 4, 16, steps=(4, 3, 2, 1))
        self.body.addWidget(self.grid)
        self.empty = text("", Type.BODY, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignCenter)
        self.empty.setContentsMargins(0, 48, 0, 48)
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self._render()

    def on_show(self) -> None:
        self._render()

    def _set_window(self, index: int) -> None:
        self.window = index
        self._render()

    def _render(self) -> None:
        label = WINDOWS[self.window][0]
        period = "hari ini" if WINDOWS[self.window][1] is None else f"{label} terakhir"
        self.tabs.set_counts(self._ctrl.counts())
        a = self._ctrl.summary(self.window)
        self.stats.clear()
        self.stats.add(StatCard("pink", "warning", f"NG {period}", str(a.count), "kaleng", a.delta,
                                f"sejak pukul {a.since:%H.%M}", "trend-up" if a.delta.startswith("+") else None,
                                highlight_value=True))
        self.stats.add(StatCard("indigo", "activity", "Skor anomali rata-rata", fmt.score(a.avg_score) if a.count else "-",
                                "", f"ambang {fmt.score(a.avg_threshold)}" if a.count else "ambang -", f"{a.count} kaleng"))
        top = a.top
        self.stats.add(StatCard("blue", "trend-up", "Skor tertinggi", fmt.score(top.score) if top else "-", "",
                                top.batch if top else "-", f"pukul {top.time[:5]}" if top else ""))
        self.stats.add(StatCard("amber", "layers", "Batch terdampak", str(len(a.batches)), "batch",
                                "HOLD" if a.batches else "-", _and(a.batches)))
        self.grid.clear()
        alerts = self._ctrl.alerts(self.window)
        for i, al in enumerate(alerts):
            card = DefectCard(al.batch, al.time, al.score, al.threshold, al.defect, highlight=i == 0)
            card.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            self.grid.add(card)
        self.empty.setVisible(not alerts)
        self.empty.setText(f"Tidak ada kaleng NG dalam {period}. Pilih rentang waktu yang lebih panjang.")
