"""Alert (FR-22, FR-23): latest NG cans with photo and anomaly score."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from ...controllers import AlertController
from ...controllers.alert_controller import WINDOWS
from .. import formatting as fmt
from ..components import (
    AdaptiveRow, DefectCard, LiveIndicator, ResponsiveGrid, SearchField, SegmentedTabs, StatCard, hbox, text,
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


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _and(items: list[str]) -> str:
    if len(items) > 3:
        return f"{', '.join(items[:2])} dan {len(items) - 2} lainnya"
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " dan " + items[-1]


class AlertPage(Page):
    def __init__(self, controller: AlertController, window_getter):
        super().__init__("Alert kemasan cacat")
        self._ctrl = controller
        self._win = window_getter
        self.window = 0
        self.search = SearchField("Cari kode batch atau produk", 280)
        self.search.edit.textChanged.connect(lambda _: self._render())
        self.actions.addWidget(self.search)
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

    def _when(self, alert) -> str:
        if alert.timestamp and alert.timestamp.date() != self._ctrl.today():
            return f"{alert.timestamp.day} {_MONTHS[alert.timestamp.month - 1]}, {alert.time[:5]}"
        return f"pukul {alert.time[:5]}"

    def on_show(self) -> None:
        self._render()

    def _set_window(self, index: int) -> None:
        self.window = index
        self._render()

    def _render(self) -> None:
        label, span = WINDOWS[self.window]
        period = {"today": "hari ini", "all": "semua waktu"}.get(span, f"{label} terakhir")
        query = self.search.edit.text()
        self.tabs.set_counts(self._ctrl.counts(query))
        a = self._ctrl.summary(self.window, query)
        if a.since is None:
            since = "belum ada data"
        elif a.since.date() == self._ctrl.today():
            since = f"sejak pukul {a.since:%H.%M}"
        else:
            since = f"sejak {a.since.day} {_MONTHS[a.since.month - 1]}"
        self.stats.clear()
        self.stats.add(StatCard("pink", "warning", f"NG {period}", str(a.count), "kaleng", a.delta,
                                since, "trend-up" if a.delta.startswith("+") else None,
                                highlight_value=True))
        self.stats.add(StatCard("indigo", "activity", "Skor anomali rata-rata", fmt.score(a.avg_score) if a.count else "-",
                                "", f"ambang {fmt.score(a.avg_threshold)}" if a.count else "ambang -", f"{a.count} kaleng"))
        top = a.top
        self.stats.add(StatCard("blue", "trend-up", "Skor tertinggi", fmt.score(top.score) if top else "-", "",
                                top.batch if top else "-", self._when(top) if top else ""))
        products = len({al.product for al in self._ctrl.alerts(self.window, query)})
        self.stats.add(StatCard("amber", "layers", "Batch terdampak", str(len(a.batches)), "batch",
                                f"{products} produk" if a.batches else "-", _and(a.batches)))
        self.grid.clear()
        alerts = self._ctrl.alerts(self.window, query)
        for i, al in enumerate(alerts):
            older = al.timestamp and al.timestamp.date() != self._ctrl.today()
            when = f"{al.timestamp.day} {_MONTHS[al.timestamp.month - 1]}, {al.time[:5]}" if older else al.time
            card = DefectCard(al.batch, when, al.score, al.threshold, al.defect, highlight=i == 0)
            card.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            self.grid.add(card)
        self.empty.setVisible(not alerts)
        if query.strip():
            self.empty.setText(f"Tidak ada kaleng NG untuk “{query.strip()}” dalam {period}.")
        else:
            self.empty.setText(f"Tidak ada kaleng NG dalam {period}. Pilih rentang waktu yang lebih panjang.")
