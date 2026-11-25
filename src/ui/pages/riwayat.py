from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QStackedWidget, QWidget

from ...controllers import HistoryController
from ...controllers.history_controller import RESULT_FILTERS, History
from ...models import Inspection
from .. import formatting as fmt
from ..assets import pixmap
from ..components import (
    AdaptiveRow, Badge, Button, CanPhoto, Card, DataTable, IconButton, ProgressBar, SearchField, SegmentedTabs,
    TableFooter, hbox, text, two_line, vbox,
)
from ..shell import Page
from ..theme import TONES, Color, Type

NG_TAB = 2


class _Message(Card):
    def __init__(self):
        super().__init__((40, 40, 40, 40), 16)
        self.layout_.addStretch(1)
        self.icon = QLabel()
        self.icon.setFixedSize(80, 80)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add(self.icon, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = text("", Type.TITLE)
        self.add(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body = text("", Type.BODY, Color.TEXT_SECONDARY, wrap=True, align=Qt.AlignmentFlag.AlignCenter)
        self.body.setFixedWidth(480)
        self.add(self.body, 0, Qt.AlignmentFlag.AlignHCenter)
        self.layout_.addStretch(1)

    def show_message(self, icon_name: str, tone: str, title: str, body: str) -> None:
        t = TONES[tone]
        self.icon.setPixmap(pixmap(icon_name, t.ink, 36))
        self.icon.setStyleSheet(f"background: {t.soft}; border: 1px solid {t.mid}; border-radius: 40px;")
        self.title.setText(title)
        self.body.setText(body)
        self.body.setFixedHeight(self.body.heightForWidth(self.body.width()))


class _ScoreBox(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Score")
        lay = vbox(0, (16, 14, 16, 14), self)
        self.bars = {tone: ProgressBar("Skor anomali", "", 0, tone) for tone in ("pink", "green")}
        for bar in self.bars.values():
            lay.addWidget(bar)

    def show_score(self, inspection: Inspection) -> None:
        tone = "pink" if inspection.is_ng else "green"
        t = TONES[tone]
        self.setStyleSheet(f"QFrame#Score {{ background: {t.soft}; border: 1px solid {t.mid}; border-radius: 16px; }}")
        for name, bar in self.bars.items():
            bar.setVisible(name == tone)
        self.bars[tone].set_value(fmt.score(inspection.score), inspection.score)


class RiwayatPage(Page):
    def __init__(self, controller: HistoryController, window_getter):
        super().__init__("Riwayat dan klaim")
        self._ctrl = controller
        self._win = window_getter
        self.history: History | None = None
        self.filter_index = NG_TAB
        self.page_index = 0
        self.shown: list[Inspection] = []
        self.selected: Inspection | None = None

        self.search = SearchField("Masukkan kode batch", 320)
        self.search.edit.returnPressed.connect(self._search)
        self.actions.addWidget(self.search)
        find = Button("Cari batch", "primary", "md", "search")
        find.clicked.connect(self._search)
        self.actions.addWidget(find)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self.message = _Message()
        self.stack.addWidget(self.message)
        self.stack.addWidget(self._result_view())
        self.body.addWidget(self.stack, 1)
        self.message.show_message("search", "indigo", "Cari riwayat inspeksi",
                                  "Masukkan kode batch dari keluhan customer, lalu tekan Cari batch.")

    def show_batch(self, code: str) -> None:
        self.search.edit.setText(code)
        self._search()

    def _search(self) -> None:
        code = self._ctrl.normalize(self.search.edit.text())
        if not code:
            self.search.edit.setFocus()
            return
        self.search.edit.setText(code)
        self.history = self._ctrl.find(code)
        if self.history is None:
            self.message.show_message("x-circle", "pink", "Data inspeksi tidak tersedia",
                                      f"Kode {code} belum terdaftar, atau batch ini belum punya data inspeksi. "
                                      "Periksa kembali kode pada kemasan atau dokumen keluhan customer.")
            self.stack.setCurrentIndex(0)
            return
        self.tabs.set_current(NG_TAB)
        self.filter_index, self.page_index, self.selected = NG_TAB, 0, None
        self.stack.setCurrentIndex(1)
        self._render()

    def _result_view(self) -> QWidget:
        view = AdaptiveRow(breakpoint=1180)
        head = QWidget()
        h_lay = hbox(12, (0, 0, 0, 0), head)
        col = vbox(2)
        col.addWidget(text("Riwayat inspeksi", Type.TITLE))
        col.addWidget(text("Diurutkan dari yang terbaru. Pilih baris untuk melihat foto kaleng.", Type.CAPTION,
                           Color.TEXT_TERTIARY))
        h_lay.addLayout(col, 1)
        self.tabs = SegmentedTabs([(label, "0") for label, _ in RESULT_FILTERS], NG_TAB)
        self.tabs.changed.connect(self._on_filter)
        h_lay.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignVCenter)
        self.table = DataTable([("No. inspeksi", 10, "L"), ("Waktu", 10, "L"), ("Hasil", 8, "L"),
                                ("Skor anomali", 30, "F", 32), ("Foto", 5, "R", 0)], head, row_padding=10)
        self.table.row_clicked.connect(lambda i: self._select(self.shown[i]))
        self.footer = TableFooter()
        self.footer.page_changed.connect(self._go_page)
        self.table.add_footer(self.footer)
        view.add(self.table, 1)
        view.add(self._photo_panel(), 0, fixed_width=440)
        return view

    def _render(self) -> None:
        h = self.history
        self.tabs.set_counts([fmt.num(h.total), fmt.num(h.ok), fmt.num(h.ng)])
        result = RESULT_FILTERS[self.filter_index][1]
        rows = self._ctrl.filtered(h, result)
        pages = self._ctrl.page_count(rows)
        self.page_index = min(self.page_index, pages - 1)
        self.shown = self._ctrl.page(rows, self.page_index)
        if self.selected not in self.shown:
            self.selected = self.shown[0] if self.shown else None
        self.table.clear_rows()
        for r in self.shown:
            on = r is self.selected
            photo = IconButton("image", "Lihat foto", "soft" if on else "outline", 36)
            photo.clicked.connect(lambda _=False, rr=r: self._select(rr))
            self.table.add_row([text(f"#{fmt.num(r.inspection_id)}", Type.BODY_STRONG),
                                two_line(fmt.day(r.timestamp), f"{r.timestamp:%H.%M.%S}", strong=False),
                                Badge(r.result),
                                ProgressBar("Skor", fmt.score(r.score), r.score, "pink" if r.is_ng else "green"),
                                photo], selected=on)
        kind = f"kaleng {result}" if result else "inspeksi"
        self.table.set_empty(None if rows else f"Tidak ada {kind} pada batch {h.code}.")
        self.footer.update_state(f"Menampilkan {len(self.shown)} dari {fmt.num(len(rows))} {kind} batch {h.code}.",
                                 self.page_index, pages)
        self._show_photo()

    def _on_filter(self, index: int) -> None:
        self.filter_index, self.page_index, self.selected = index, 0, None
        self._render()

    def _go_page(self, index: int) -> None:
        self.page_index, self.selected = index, None
        self._render()

    def _select(self, inspection: Inspection) -> None:
        self.selected = inspection
        self._render()

    def _photo_panel(self) -> Card:
        card = Card((22, 22, 22, 22), 16)
        head = hbox(8)
        col = vbox(2)
        col.addWidget(text("Foto kaleng", Type.TITLE))
        self.photo_caption = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        col.addWidget(self.photo_caption)
        head.addLayout(col, 1)
        self.photo_badge = Badge("NG")
        head.addWidget(self.photo_badge, 0, Qt.AlignmentFlag.AlignTop)
        card.layout_.addLayout(head)
        self.photo = CanPhoto("dent", (16, 16, 16, 16))
        self.photo.setFixedHeight(280)
        card.add(self.photo)
        self.score = _ScoreBox()
        card.add(self.score)
        card.layout_.addStretch(1)
        return card

    def _show_photo(self) -> None:
        r = self.selected
        for w in (self.photo, self.photo_badge, self.score):
            w.setVisible(r is not None)
        if r is None:
            self.photo_caption.setText("Belum ada inspeksi yang dipilih")
            return
        self.photo_caption.setText(
            f"Inspeksi #{fmt.num(r.inspection_id)}, {fmt.day(r.timestamp, year=True)} pukul {r.timestamp:%H.%M.%S}")
        self.photo_badge.set_status(r.result)
        self.photo.defect = r.defect
        self.photo.set_heatmap(r.is_ng)
        self.score.show_score(r)
