"""Dashboard (FR-19, FR-20, FR-22): active batch, totals, output per hour and latest alerts."""

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from ...controllers import DashboardController
from ...controllers import BatchController
from ...models import Batch, User
from .. import formatting as fmt
from ..assets import icon
from ..charts import StackedBarChart
from ..components import (
    AdaptiveRow, AlertRow, Badge, Button, Card, LiveIndicator, PanelHeader, ProgressBar, ResponsiveGrid, SearchField,
    StatCard, UserChip, hbox, text, vbox,
)
from ..shell import Page
from ..theme import NG_TOLERANCE_PERCENT, TONES, Color, Type
from .common import confirm_close_batch, open_photo_viewer


class BatchHero(QFrame):
    """Navy card for the batch that is currently running."""

    def __init__(self, batch: Batch, started: str, on_report, on_close):
        super().__init__()
        self.setMinimumWidth(460)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        b = batch
        lay = vbox(0, (28, 24, 28, 24), self)
        top = hbox(8)
        pill = QLabel("BERJALAN")
        pill.setFont(Badge("OK").font())
        pill.setStyleSheet(f"background: {Color.AQUA}; color: {Color.TEXT_PRIMARY}; border-radius: 8px; padding: 4px 10px;")
        top.addWidget(pill)
        top.addStretch(1)
        top.addWidget(text(f"Dimulai pukul {started}", Type.CAPTION, "rgba(255,255,255,0.75)"))
        lay.addLayout(top)
        lay.addSpacing(16)
        lay.addWidget(text("Batch aktif", Type.LABEL, "rgba(255,255,255,0.72)"))
        lay.addWidget(text(b.code, Type.DISPLAY_XL, "#FFFFFF"))
        lay.addWidget(text(f"{b.product} ({b.sku})", Type.BODY, "rgba(255,255,255,0.82)"))
        lay.addStretch(1)
        frac = b.ng_percent / NG_TOLERANCE_PERCENT
        lay.addWidget(ProgressBar("Persentase NG", fmt.pct(b.ng_percent), frac, "indigo",
                                  suffix=f"dari batas {NG_TOLERANCE_PERCENT:g}%", marker=1.0, on_dark=True,
                                  fill_colors=["#A8E9EC", "#C7C9F6", "#F4B3CD"]))
        lay.addSpacing(18)
        acts = hbox(10)
        report = Button("Lihat laporan batch", "outline", "md", "report")
        report.setStyleSheet(f"QPushButton {{ background: #FFFFFF; color: {Color.TEXT_PRIMARY}; border: 1px solid #FFFFFF; }}"
                             f"QPushButton:hover {{ background: {Color.BRAND_SOFT}; }}")
        report.clicked.connect(on_report)
        acts.addWidget(report)
        close = Button("Tutup batch", "ghost", "md", "lock")
        close.setIcon(icon("lock", "#FFFFFF", 18))
        close.setStyleSheet("QPushButton { color: #FFFFFF; border: 1px solid rgba(255,255,255,0.4); }"
                            "QPushButton:hover { background: rgba(255,255,255,0.08); }")
        close.clicked.connect(on_close)
        acts.addWidget(close)
        acts.addStretch(1)
        lay.addLayout(acts)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(r, 24, 24)
        p.setClipPath(clip)
        g = QLinearGradient(0, 0, r.width(), r.height())
        g.setColorAt(0, QColor("#355872"))
        g.setColorAt(0.6, QColor("#2E4C8E"))
        g.setColorAt(1, QColor("#3533CD"))
        p.fillRect(r, g)
        for cx, cy, rad, c, a in ((r.width() - 80, r.height() + 10, 200, "#F4B3CD", 130),
                                  (r.width() - 40, -20, 170, "#A8E9EC", 100)):
            rg = QRadialGradient(QPointF(cx, cy), rad)
            col = QColor(c)
            col.setAlpha(a)
            rg.setColorAt(0, col)
            col.setAlpha(0)
            rg.setColorAt(1, col)
            p.fillRect(r, rg)
        for i, s in enumerate((150, 230, 310)):
            c = QColor(Color.AQUA)
            c.setAlphaF(0.35 - i * 0.09)
            p.setPen(QPen(c, 1))
            p.drawEllipse(QPointF(r.width() - 55, 40), s / 2, s / 2)


class DashboardPage(Page):
    def __init__(self, controller: DashboardController, batches: BatchController, user: User, navigate,
                 window_getter):
        super().__init__(f"Selamat pagi, {user.name}")
        self._ctrl = controller
        self._batches = batches
        self._win = window_getter
        self.actions.addWidget(SearchField("Cari kode batch", 300))
        self.live = LiveIndicator()
        self.actions.addWidget(self.live)
        self.actions.addWidget(UserChip(user.name, user.role, user.initials))

        s = self._ctrl.stats()
        active = self._ctrl.active_batch()
        row1 = AdaptiveRow(breakpoint=1280)
        if active is not None:
            hero = BatchHero(active, self._ctrl.active_batch_started(), lambda: navigate("laporan"),
                             lambda: confirm_close_batch(self._win(), active.code,
                                                         lambda: self._batches.close(active.code)))
            row1.add(hero, 5)
        grid = ResponsiveGrid(220, 4, 16, steps=(4, 2, 1))
        grid.add(StatCard("blue", "package", "Total output hari ini", fmt.num(s["output"]), "kaleng",
                          s["output_delta"], f"sejak pukul {s['output_since']}", "trend-up"))
        grid.add(StatCard("indigo", "check-circle", "Kaleng OK", fmt.num(s["ok"]), "kaleng",
                          fmt.pct(s["ok_percent"]), "dari total inspeksi"))
        grid.add(StatCard("pink", "warning", "Kaleng NG", fmt.num(s["ng"]), "kaleng",
                          fmt.pct(s["ng_percent"]), f"batas toleransi {NG_TOLERANCE_PERCENT:g}%",
                          highlight_value=True))
        grid.add(StatCard("amber", "activity", "Kejadian produksi", str(s["events"]), "kejadian",
                          f"{s['events_reject']} REJECT", "dicatat otomatis"))
        row1.add(grid, 6)
        self.body.addWidget(row1)

        row2 = AdaptiveRow(breakpoint=1200)
        left_w = QWidget()
        left = vbox(16, (0, 0, 0, 0), left_w)
        chart_card = Card((20, 16, 20, 14), 8)
        head = hbox(16)
        col = vbox(2)
        col.addWidget(text("Output per jam", Type.TITLE))
        col.addWidget(text(f"Batch {active.code if active else '-'}, kaleng OK dan NG setiap jam", Type.CAPTION,
                           Color.TEXT_TERTIARY))
        head.addLayout(col, 1)
        for label, color in (("OK", Color.CHART_OK), ("NG", Color.CHART_NG)):
            head.addWidget(_legend(label, color))
        chart_card.layout_.addLayout(head)
        hours, current = self._ctrl.output_per_hour()
        chart_card.add(StackedBarChart(hours, current), 1)
        left.addWidget(chart_card, 1)
        left.addWidget(self._today_batches(navigate))
        row2.add(left_w, 1)
        row2.add(self._alerts(navigate), 0, fixed_width=420)
        self.body.addWidget(row2, 1)

        self._seconds = 2
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        # FR-20: data refreshes every 5 seconds (mock: only the indicator changes)
        self._seconds = 0 if self._seconds >= 5 else self._seconds + 1
        self.live.set_text("Diperbarui baru saja" if self._seconds == 0 else f"Diperbarui {self._seconds} detik lalu")

    def _today_batches(self, navigate) -> Card:
        card = Card((0, 14, 0, 4), 2)
        ph = PanelHeader("Batch hari ini", "Status inspeksi diperbarui setiap 5 detik", "Kelola batch")
        ph.layout().setContentsMargins(20, 0, 12, 6)
        ph.action_clicked.connect(lambda: navigate("batch"))
        card.add(ph)
        for b, badge in self._ctrl.today_batches():
            row = QFrame()
            row.setObjectName("Row")
            row.setStyleSheet(f"QFrame#Row {{ border: none; border-top: 1px solid {Color.BORDER}; }}")
            lay = hbox(20, (20, 10, 20, 10), row)
            c1 = vbox(0)
            c1.addWidget(text(b.code, Type.BODY_STRONG))
            c1.addWidget(text(b.product, Type.CAPTION, Color.TEXT_TERTIARY))
            w1 = QWidget()
            w1.setLayout(c1)
            w1.setFixedWidth(170)
            lay.addWidget(w1)
            c2 = vbox(0)
            c2.addWidget(text(fmt.num(b.output), Type.BODY_STRONG, align=Qt.AlignmentFlag.AlignRight))
            c2.addWidget(text("output", Type.CAPTION, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignRight))
            lay.addLayout(c2)
            frac = b.ng_percent / NG_TOLERANCE_PERCENT
            tone = "pink" if frac > 1 else "indigo"
            lay.addWidget(ProgressBar("NG", fmt.pct(b.ng_percent), frac, tone,
                                      suffix=f"batas {NG_TOLERANCE_PERCENT:g}%",
                                      marker=1.0 if frac > 1 else None), 1)
            badge_box = hbox(0)
            badge_box.addStretch(1)
            badge_box.addWidget(Badge(badge))
            w = QWidget()
            w.setLayout(badge_box)
            w.setFixedWidth(100)
            lay.addWidget(w)
            card.add(row)
        return card

    def _alerts(self, navigate) -> Card:
        card = Card((10, 16, 10, 12), 4)
        a = self._ctrl.alert_summary()
        ph = PanelHeader("Alert kemasan cacat", f"{a['ng_30min']} kaleng NG dalam 30 menit terakhir",
                         "Lihat semua")
        ph.layout().setContentsMargins(10, 0, 0, 6)
        ph.action_clicked.connect(lambda: navigate("alert"))
        card.add(ph)
        top = QFrame()
        top.setObjectName("Top")
        top.setStyleSheet(
            "QFrame#Top { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(168,233,236,0.28),"
            f" stop:0.55 rgba(244,179,205,0.16), stop:1 #FFFFFF); border: 1px solid {Color.BORDER}; border-radius: 14px; }}"
        )
        tl = hbox(10, (14, 10, 14, 10), top)
        col = vbox(0)
        col.addWidget(text("Skor anomali tertinggi", Type.CAPTION, Color.TEXT_SECONDARY))
        col.addWidget(text(f"{a['top_batch']}, pukul {a['top_time']}", Type.BODY_STRONG))
        tl.addLayout(col, 1)
        tl.addWidget(text(fmt.score(a["top_score"]), Type.TITLE, TONES["pink"].ink))
        card.add(top)
        for i, al in enumerate(self._ctrl.alerts(6)):
            row = AlertRow(al.batch, f"Pukul {al.time}", fmt.score(al.score), al.defect, highlight=i == 0)
            row.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            card.add(row)
        card.layout_.addStretch(1)
        more = Button("Buka semua alert", "outline")
        more.clicked.connect(lambda: navigate("alert"))
        card.add(more)
        return card


def _legend(label: str, color: str) -> QWidget:
    w = QWidget()
    lay = hbox(6, (0, 0, 0, 0), w)
    sw = QFrame()
    sw.setFixedSize(10, 10)
    sw.setStyleSheet(f"background: {color}; border-radius: 3px;")
    lay.addWidget(sw)
    lay.addWidget(text(label, Type.CAPTION, Color.TEXT_SECONDARY))
    return w
