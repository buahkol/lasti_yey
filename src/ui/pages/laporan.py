"""Laporan inspeksi batch (FR-24, FR-25): totals, NG per hour, status gauge, events and top scores."""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QMenu, QWidget

from .. import mock_data as data
from ..assets import pixmap
from ..charts import Gauge, PeakBarChart
from ..components import (
    AdaptiveRow, AlertRow, Badge, Button, Card, DataTable, DatePicker, PanelHeader, ResponsiveGrid, SegmentedTabs,
    StatCard, format_range,
    hbox, text, toast, vbox,
)
from ..shell import Page
from ..theme import NG_TOLERANCE_PERCENT, TONES, Color, Type
from .common import open_export_pdf, open_photo_viewer


def _event_kind(kind: str) -> QWidget:
    w = QWidget()
    lay = hbox(8, (0, 0, 0, 0), w)
    dot = QFrame()
    dot.setFixedSize(8, 8)
    color = Color.CHART_NG if kind == "REJECT" else TONES["amber"].solid
    dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
    lay.addWidget(dot)
    lay.addWidget(text(kind.replace("_", " "), Type.BODY_STRONG))
    return w


class LaporanPage(Page):
    def __init__(self, window_getter):
        super().__init__("Laporan inspeksi batch")
        self._win = window_getter
        r = data.REPORT
        mode = SegmentedTabs(["Per batch", "Per tanggal"])
        mode.changed.connect(lambda i: i == 1 and toast(self._win(), "info", "Rekap per tanggal",
                                                        "Gunakan pemilih tanggal untuk memilih rentang rekap."))
        self.actions.addWidget(mode)
        self.batch_btn = Button(r["code"], "outline", "md", "layers")
        self.batch_btn.clicked.connect(self._batch_menu)
        self.actions.addWidget(self.batch_btn)
        self.date_btn = Button(r["date"], "outline", "md", "calendar")
        self.date_btn.clicked.connect(self._pick_date)
        self.actions.addWidget(self.date_btn)
        export = Button("Ekspor PDF", "primary", "md", "download")
        export.clicked.connect(lambda: open_export_pdf(self._win(), r["code"], r["product"]))
        self.actions.addWidget(export)

        stats = ResponsiveGrid(190, 5, 16, steps=(5, 3, 2, 1))
        ok_pct = r["ok"] / r["total"] * 100
        loss = r["ng"] * r["unit_price"]
        stats.add(StatCard("blue", "camera", "Total diperiksa", data.num(r["total"]), "kaleng", "100%", r["window"]))
        stats.add(StatCard("indigo", "check-circle", "Kaleng OK", data.num(r["ok"]), "kaleng", data.pct(ok_pct),
                           "dari total"))
        stats.add(StatCard("pink", "warning", "Kaleng NG", data.num(r["ng"]), "kaleng", data.pct(r["ng_percent"]),
                           f"batas {NG_TOLERANCE_PERCENT:g}%", "trend-up", highlight_value=True))
        stats.add(StatCard("amber", "trend-down", "Estimasi kerugian", data.rupiah(loss), "",
                           f"{r['ng']} x {data.rupiah(r['unit_price'])}", ""))
        stats.add(StatCard("blue", "activity", "Kejadian", str(r["events"]), "kejadian",
                           f"{r['events_reject']} REJECT", f"{r['events_manual']} manual"))
        self.body.addWidget(stats)

        row2 = AdaptiveRow(breakpoint=1000)
        chart = Card((20, 18, 20, 16), 12)
        head = hbox(12)
        col = vbox(2)
        col.addWidget(text("Sebaran NG per jam", Type.TITLE))
        peak = max(r["ng_per_hour"], key=lambda x: x[1])
        nxt = f"{int(peak[0][:2]) + 1:02d}.00"
        col.addWidget(text(f"Pola cacat {r['code']}, puncak pukul {peak[0]} sampai {nxt}", Type.CAPTION, Color.TEXT_TERTIARY))
        head.addLayout(col, 1)
        t = TONES["pink"]
        pill = QFrame()
        pill.setObjectName("Peak")
        pill.setStyleSheet(f"QFrame#Peak {{ background: {t.soft}; border: 1px solid {t.mid}; border-radius: 14px; }}")
        p_lay = hbox(6, (10, 4, 12, 4), pill)
        ic = QLabel()
        ic.setPixmap(pixmap("trend-up", t.ink, 14))
        p_lay.addWidget(ic)
        p_lay.addWidget(text(f"Puncak {peak[1]} NG", Type.CAPTION, t.ink))
        head.addWidget(pill, 0, Qt.AlignmentFlag.AlignTop)
        chart.layout_.addLayout(head)
        bar_chart = PeakBarChart(r["ng_per_hour"], 12)
        bar_chart.setMinimumHeight(290)
        chart.add(bar_chart, 1)
        row2.add(chart, 1)
        row2.add(self._status_card(), 0, fixed_width=400)
        self.body.addWidget(row2)

        row3 = AdaptiveRow(breakpoint=1000)
        ph = PanelHeader("Kejadian produksi", f"{r['events']} kejadian, REJECT dicatat otomatis oleh AI", "Lihat kejadian")
        ph.action_clicked.connect(lambda: toast(self._win(), "info", "Halaman Kejadian", "Halaman ini dikerjakan pada Desktop P2."))
        events = DataTable([("Waktu", 10, "L"), ("Jenis", 20, "L"), ("Sumber", 14, "L"), ("Keterangan", 40, "L")],
                           ph, row_padding=10)
        for time, kind, source, note in r["events_list"]:
            events.add_row([text(time, Type.BODY_STRONG), _event_kind(kind), text(source, Type.BODY),
                            text(note, Type.BODY, Color.TEXT_SECONDARY)])
        row3.add(events, 1)
        top = Card((10, 16, 10, 12), 4)
        tph = PanelHeader("Skor NG tertinggi", "Ikut dicetak pada laporan PDF")
        tph.layout().setContentsMargins(10, 0, 0, 6)
        top.add(tph)
        for batch, time, score, defect in r["top_scores"]:
            row = AlertRow(batch, f"Pukul {time}", score, defect)
            alert = (batch, time, float(score.replace(",", ".")), 0.64, defect)
            row.clicked.connect(lambda a=alert: open_photo_viewer(self._win(), a, r["product"]))
            top.add(row)
        top.layout_.addStretch(1)
        row3.add(top, 0, fixed_width=400)
        self.body.addWidget(row3, 1)

    def _status_card(self) -> Card:
        r = data.REPORT
        card = Card((20, 18, 20, 18), 10)
        head = hbox(8)
        head.addWidget(text("Status inspeksi", Type.TITLE), 1)
        held = r["ng_percent"] > NG_TOLERANCE_PERCENT
        head.addWidget(Badge("HOLD" if held else "PASSED"))
        card.layout_.addLayout(head)
        card.add(Gauge(r["ng_percent"], NG_TOLERANCE_PERCENT, 10.0), 0, Qt.AlignmentFlag.AlignHCenter)
        scale = hbox(0)
        scale.addWidget(text("0%", Type.CAPTION, Color.TEXT_TERTIARY))
        scale.addStretch(1)
        scale.addWidget(text("10%", Type.CAPTION, Color.TEXT_TERTIARY))
        card.layout_.addLayout(scale)
        t = TONES["amber"] if held else TONES["green"]
        note = QFrame()
        note.setObjectName("Note")
        note.setStyleSheet(f"QFrame#Note {{ background: {t.soft}; border-radius: 14px; }}")
        n_lay = hbox(10, (12, 10, 12, 10), note)
        ic = QLabel()
        ic.setPixmap(pixmap("warning" if held else "check-circle", t.ink, 18))
        n_lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        gap = f"{r['ng_percent'] - NG_TOLERANCE_PERCENT:.1f}".replace(".", ",")
        msg = (f"NG melewati batas {gap} poin. Batch tetap HOLD dan belum dapat dikirim." if held
               else "NG di bawah batas toleransi. Batch dapat dipilih saat mencatat pengiriman.")
        n_lay.addWidget(text(msg, Type.CAPTION, t.ink, wrap=True), 1)
        card.layout_.addStretch(1)
        card.add(note)
        return card

    def _batch_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: #FFFFFF; border: 1px solid {Color.BORDER}; border-radius: 12px; padding: 6px; }}"
                           f"QMenu::item {{ padding: 8px 14px; border-radius: 8px; }}"
                           f"QMenu::item:selected {{ background: {Color.BRAND_SOFT}; color: {Color.TEXT_PRIMARY}; }}")
        for b in data.BATCHES:
            act = menu.addAction(f"{b['code']}, {b['product']}")
            act.triggered.connect(lambda _=False, code=b["code"]: toast(
                self._win(), "info", f"Laporan {code}", "Data contoh hanya tersedia untuk B-2411-02."))
        menu.exec(self.batch_btn.mapToGlobal(self.batch_btn.rect().bottomLeft()))

    def _pick_date(self) -> None:
        today = QDate(2026, 11, 25)
        picker = DatePicker(today, today, today, self)
        picker.applied.connect(lambda s, e: self.date_btn.setText(f" {format_range(s, e)}"))
        picker.popup_below(self.date_btn)
