"""Laporan (FR-21, FR-24, FR-25).

Per batch: inspection report with totals, NG per hour, status gauge, events and top scores.
Per tanggal: production recap for a date range with output and NG per day and a table per batch.
"""

from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QMenu, QStackedWidget, QWidget

from ...controllers import ReportController
from ...controllers.report_controller import day_label
from ...controllers.rules import NG_TOLERANCE_PERCENT
from .. import formatting as fmt
from ..assets import pixmap
from ..charts import Gauge, PeakBarChart, StackedBarChart
from ..components import (
    AdaptiveRow, AlertRow, Badge, Button, Card, DataTable, DatePicker, PanelHeader, ResponsiveGrid, SegmentedTabs,
    StatCard, event_kind, format_range, hbox, text, toast, two_line, vbox,
)
from ..shell import Page
from ..theme import TONES, Color, Type
from .common import open_export_pdf, open_photo_viewer

_MENU_STYLE = (f"QMenu {{ background: #FFFFFF; border: 1px solid {Color.BORDER}; border-radius: 12px; padding: 6px; }}"
               "QMenu::item { padding: 8px 14px; border-radius: 8px; }"
               f"QMenu::item:selected {{ background: {Color.BRAND_SOFT}; color: {Color.TEXT_PRIMARY}; }}")
_TODAY = QDate(2026, 11, 25)


def _note(held: bool, message: str) -> QFrame:
    t = TONES["amber"] if held else TONES["green"]
    note = QFrame()
    note.setObjectName("Note")
    note.setStyleSheet(f"QFrame#Note {{ background: {t.soft}; border-radius: 14px; }}")
    n_lay = hbox(10, (12, 10, 12, 10), note)
    ic = QLabel()
    ic.setPixmap(pixmap("warning" if held else "check-circle", t.ink, 18))
    n_lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
    n_lay.addWidget(text(message, Type.CAPTION, t.ink, wrap=True), 1)
    return note


def _chart_head(title: str, caption: str, pill: str | None = None) -> QWidget:
    w = QWidget()
    head = hbox(12, (0, 0, 0, 0), w)
    col = vbox(2)
    col.addWidget(text(title, Type.TITLE))
    col.addWidget(text(caption, Type.CAPTION, Color.TEXT_TERTIARY))
    head.addLayout(col, 1)
    if pill:
        t = TONES["pink"]
        box = QFrame()
        box.setObjectName("Peak")
        box.setStyleSheet(f"QFrame#Peak {{ background: {t.soft}; border: 1px solid {t.mid}; border-radius: 14px; }}")
        p_lay = hbox(6, (10, 4, 12, 4), box)
        ic = QLabel()
        ic.setPixmap(pixmap("trend-up", t.ink, 14))
        p_lay.addWidget(ic)
        p_lay.addWidget(text(pill, Type.CAPTION, t.ink))
        head.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)
    return w


class LaporanPage(Page):
    def __init__(self, controller: ReportController, window_getter):
        super().__init__("Laporan inspeksi batch")
        self._ctrl = controller
        self._win = window_getter
        self.code = "B-2411-02"
        self.range = (QDate(2026, 11, 23), _TODAY)

        self.mode = SegmentedTabs(["Per batch", "Per tanggal"])
        self.mode.changed.connect(self._set_mode)
        self.actions.addWidget(self.mode)
        self.batch_btn = Button(self.code, "outline", "md", "layers")
        self.batch_btn.clicked.connect(self._batch_menu)
        self.actions.addWidget(self.batch_btn)
        self.date_btn = Button("", "outline", "md", "calendar")
        self.date_btn.clicked.connect(self._pick_date)
        self.actions.addWidget(self.date_btn)
        export = Button("Ekspor PDF", "primary", "md", "download")
        export.clicked.connect(self._export)
        self.actions.addWidget(export)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self.body.addWidget(self.stack, 1)
        self.batch_view = QWidget()
        self.recap_view = QWidget()
        self.stack.addWidget(self.batch_view)
        self.stack.addWidget(self.recap_view)
        self._render_batch()
        self._render_recap()
        self._set_mode(0)

    # mode and navigation ---------------------------------------------------
    def _set_mode(self, index: int) -> None:
        per_date = index == 1
        self.stack.setCurrentIndex(index)
        self.title.setText("Rekap produksi per tanggal" if per_date else "Laporan inspeksi batch")
        self.batch_btn.setVisible(not per_date)
        if per_date:
            self.date_btn.setText(f" {format_range(*self.range)}")
        else:
            report = self._ctrl.batch_report(self.code)
            self.date_btn.setText(f" {report['date']}" if report else " 25 Nov 2026")
        self.date_btn.setEnabled(per_date)
        self.date_btn.setToolTip("" if per_date else "Tanggal mengikuti batch yang dipilih")

    def show_batch(self, code: str) -> None:
        """Open the report of one batch, for example from the Batch page."""
        if self._ctrl.batch_report(code) is None:
            toast(self._win(), "info", f"Laporan {code} belum tersedia",
                  "Data inspeksi batch ini belum ada di data contoh. Laporan B-2411-02 ditampilkan.")
        else:
            self.code = code
            self.batch_btn.setText(f" {code}")
            self._render_batch()
        self.mode.set_current(0)
        self._set_mode(0)

    def _export(self) -> None:
        if self.stack.currentIndex() == 1:
            start, end = self.range
            label = f"{start.toString('ddMMM')}_{end.toString('ddMMMyyyy')}"
            open_export_pdf(self._win(), date_label=label, per_date=True)
        else:
            report = self._ctrl.batch_report(self.code)
            open_export_pdf(self._win(), self.code, report["product"] if report else "")

    def _batch_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        for b in self._ctrl.batches():
            act = menu.addAction(f"{b.code}, {b.product}")
            act.triggered.connect(lambda _=False, code=b.code: self.show_batch(code))
        menu.exec(self.batch_btn.mapToGlobal(self.batch_btn.rect().bottomLeft()))

    def _pick_date(self) -> None:
        picker = DatePicker(*self.range, _TODAY, self)
        picker.applied.connect(self._set_range)
        picker.popup_below(self.date_btn)

    def _set_range(self, start: QDate, end: QDate) -> None:
        self.range = (start, end)
        self.date_btn.setText(f" {format_range(start, end)}")
        self._render_recap()

    @staticmethod
    def _reset(host: QWidget):
        old = host.layout()
        if old is not None:
            QWidget().setLayout(old)  # move the old layout and its widgets away so they are deleted
        return vbox(16, (0, 0, 0, 0), host)

    # per batch -------------------------------------------------------------
    def _render_batch(self) -> None:
        lay = self._reset(self.batch_view)
        r = self._ctrl.batch_report(self.code)
        if r is None:
            return
        stats = ResponsiveGrid(190, 5, 16, steps=(5, 3, 2, 1))
        stats.add(StatCard("blue", "camera", "Total diperiksa", fmt.num(r["total"]), "kaleng", "100%", r["window"]))
        stats.add(StatCard("indigo", "check-circle", "Kaleng OK", fmt.num(r["ok"]), "kaleng", fmt.pct(r["ok_percent"]),
                           "dari total"))
        stats.add(StatCard("pink", "warning", "Kaleng NG", fmt.num(r["ng"]), "kaleng", fmt.pct(r["ng_percent"]),
                           f"batas {NG_TOLERANCE_PERCENT:g}%", "trend-up", highlight_value=True))
        stats.add(StatCard("amber", "trend-down", "Estimasi kerugian", fmt.rupiah(r["loss"]), "",
                           f"{r['ng']} x {fmt.rupiah(r['unit_price'])}", ""))
        stats.add(StatCard("blue", "activity", "Kejadian", str(r["events"]), "kejadian",
                           f"{r['events_reject']} REJECT", f"{r['events_manual']} manual"))
        lay.addWidget(stats)

        row2 = AdaptiveRow(breakpoint=1000)
        chart = Card((20, 18, 20, 16), 12)
        peak = max(r["ng_per_hour"], key=lambda x: x[1])
        nxt = f"{int(peak[0][:2]) + 1:02d}.00"
        chart.add(_chart_head("Sebaran NG per jam", f"Pola cacat {r['code']}, puncak pukul {peak[0]} sampai {nxt}",
                              f"Puncak {peak[1]} NG"))
        bar_chart = PeakBarChart(r["ng_per_hour"], 12)
        bar_chart.setMinimumHeight(290)
        chart.add(bar_chart, 1)
        row2.add(chart, 1)
        row2.add(self._status_card(r), 0, fixed_width=400)
        lay.addWidget(row2)

        row3 = AdaptiveRow(breakpoint=1000)
        ph = PanelHeader("Kejadian produksi", f"{r['events']} kejadian, REJECT dicatat otomatis oleh AI", "Lihat kejadian")
        ph.action_clicked.connect(lambda: self._win().open_batch("kejadian", self.code))
        events = DataTable([("Waktu", 10, "L"), ("Jenis", 20, "L"), ("Sumber", 14, "L"), ("Keterangan", 40, "L")],
                           ph, row_padding=10)
        for e in r["events_list"]:
            events.add_row([text(e.time, Type.BODY_STRONG), event_kind(e.kind), text(e.source, Type.BODY),
                            text(e.note, Type.BODY, Color.TEXT_SECONDARY)])
        row3.add(events, 1)
        top = Card((10, 16, 10, 12), 4)
        tph = PanelHeader("Skor NG tertinggi", "Ikut dicetak pada laporan PDF")
        tph.layout().setContentsMargins(10, 0, 0, 6)
        top.add(tph)
        for al in r["top_scores"]:
            row = AlertRow(al.batch, f"Pukul {al.time}", fmt.score(al.score), al.defect)
            row.clicked.connect(lambda a=al: open_photo_viewer(self._win(), a))
            top.add(row)
        top.layout_.addStretch(1)
        row3.add(top, 0, fixed_width=400)
        lay.addWidget(row3, 1)

    def _status_card(self, r: dict) -> Card:
        card = Card((20, 18, 20, 18), 10)
        head = hbox(8)
        head.addWidget(text("Status inspeksi", Type.TITLE), 1)
        held = r["held"]
        head.addWidget(Badge("HOLD" if held else "PASSED"))
        card.layout_.addLayout(head)
        card.layout_.addStretch(1)
        card.add(Gauge(r["ng_percent"], NG_TOLERANCE_PERCENT, 10.0), 0, Qt.AlignmentFlag.AlignHCenter)
        gap = f"{r['ng_percent'] - NG_TOLERANCE_PERCENT:.1f}".replace(".", ",")
        msg = (f"NG melewati batas {gap} poin. Batch tetap HOLD dan belum dapat dikirim." if held
               else "NG di bawah batas toleransi. Batch dapat dipilih saat mencatat pengiriman.")
        card.layout_.addStretch(1)
        card.add(_note(held, msg))
        return card

    # per tanggal -----------------------------------------------------------
    def _render_recap(self) -> None:
        lay = self._reset(self.recap_view)
        start: date = self.range[0].toPyDate()
        end: date = self.range[1].toPyDate()
        r = self._ctrl.date_recap(start, end)
        period = f"{day_label(r['start'])} sampai {day_label(r['end'])}"

        stats = ResponsiveGrid(190, 5, 16, steps=(5, 3, 2, 1))
        stats.add(StatCard("blue", "camera", "Total diperiksa", fmt.num(r["total"]), "kaleng",
                           f"{r['batch_count']} batch", period))
        stats.add(StatCard("indigo", "check-circle", "Kaleng OK", fmt.num(r["ok"]), "kaleng",
                           fmt.pct(100 - r["ng_percent"]) if r["total"] else "0,0%", "dari total"))
        stats.add(StatCard("pink", "warning", "Kaleng NG", fmt.num(r["ng"]), "kaleng", fmt.pct(r["ng_percent"]),
                           f"batas {NG_TOLERANCE_PERCENT:g}%", highlight_value=True))
        stats.add(StatCard("amber", "trend-down", "Estimasi kerugian", fmt.rupiah(r["loss"]), "",
                           f"{fmt.num(r['ng'])} kaleng NG", ""))
        stats.add(StatCard("blue", "layers", "Batch PASSED", str(r["passed"]), "batch",
                           f"{r['hold']} HOLD", f"{r['running']} berjalan"))
        lay.addWidget(stats)

        row2 = AdaptiveRow(breakpoint=1000)
        chart = Card((20, 18, 20, 16), 12)
        per_day = r["per_day"]
        busiest = max(range(len(per_day)), key=lambda i: per_day[i][1] + per_day[i][2]) if per_day else 0
        top_total = max((ok + ng for _, ok, ng in per_day), default=0)
        max_value = max(1000, -(-top_total // 1000) * 1000)
        head_row = hbox(12)
        head_row.addWidget(_chart_head("Output per hari", f"Kaleng OK dan NG, {period}"), 1)
        for label, color in (("OK", Color.CHART_OK), ("NG", Color.CHART_NG)):
            head_row.addWidget(_legend(label, color), 0, Qt.AlignmentFlag.AlignTop)
        chart.layout_.addLayout(head_row)
        day_chart = StackedBarChart(per_day, busiest, max_value, title_prefix="")
        day_chart.setMinimumHeight(290)
        chart.add(day_chart, 1)
        row2.add(chart, 1)

        side = Card((20, 18, 20, 18), 10)
        side.add(text("Persentase NG rentang ini", Type.TITLE))
        side.add(Gauge(r["ng_percent"], NG_TOLERANCE_PERCENT, 10.0), 0, Qt.AlignmentFlag.AlignHCenter)
        scale = hbox(0)
        scale.addWidget(text("0%", Type.CAPTION, Color.TEXT_TERTIARY))
        scale.addStretch(1)
        scale.addWidget(text("10%", Type.CAPTION, Color.TEXT_TERTIARY))
        side.layout_.addLayout(scale)
        side.layout_.addStretch(1)
        if r["hold"]:
            msg = f"{r['hold']} batch ditutup dengan status HOLD dan belum dapat dikirim. Periksa daftar di bawah."
        else:
            msg = "Semua batch yang sudah ditutup berstatus PASSED dan dapat dipilih saat mencatat pengiriman."
        side.add(_note(r["hold"] > 0, msg))
        row2.add(side, 0, fixed_width=400)
        lay.addWidget(row2)

        ph = PanelHeader("Rekap per batch", f"{r['batch_count']} batch dimulai pada {period}")
        table = DataTable([("Kode batch", 11, "L"), ("Produk", 17, "L"), ("Mulai", 10, "L", None, 1100),
                           ("Output", 8, "R"), ("OK", 8, "R"), ("NG", 7, "R"), ("Persentase NG", 9, "R"),
                           ("Inspeksi", 10, "L"), ("Kerugian", 10, "R", 0)], ph, row_padding=10)
        for row in r["rows"]:
            b = row["batch"]
            over = b.ng_percent > NG_TOLERANCE_PERCENT
            table.add_row([two_line(b.code, b.sku), text(b.product, Type.BODY),
                           text(b.start_label, Type.BODY), text(fmt.num(b.output), Type.BODY_STRONG),
                           text(fmt.num(row["ok"]), Type.BODY), text(fmt.num(row["ng"]), Type.BODY),
                           text(fmt.pct(b.ng_percent), Type.BODY_STRONG, TONES["pink"].ink if over else Color.TEXT_PRIMARY),
                           Badge(b.status if b.running else b.inspection), text(fmt.rupiah(row["loss"]), Type.BODY)])
        if not r["rows"]:
            empty = text("Tidak ada batch pada rentang tanggal ini. Pilih rentang lain.", Type.BODY,
                         Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignCenter)
            empty.setContentsMargins(0, 24, 0, 24)
            table.add_footer(empty)
        lay.addWidget(table, 1)


def _legend(label: str, color: str) -> QWidget:
    w = QWidget()
    lay = hbox(6, (0, 0, 0, 0), w)
    sw = QFrame()
    sw.setFixedSize(10, 10)
    sw.setStyleSheet(f"background: {color}; border-radius: 3px;")
    lay.addWidget(sw)
    lay.addWidget(text(label, Type.CAPTION, Color.TEXT_SECONDARY))
    return w
