"""Batch (FR-05, FR-06, FR-27): list with filters, date range, create and close batch."""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QFrame, QMenu, QSizePolicy, QWidget

from ...controllers import BatchController
from ...controllers.batch_controller import FILTERS
from ...controllers.rules import NG_TOLERANCE_PERCENT
from .. import formatting as fmt
from ..components import (
    AdaptiveRow, Badge, Button, DataTable, DatePicker, IconButton, InputField, ModalCard, Overlay, ProgressBar, SearchField,
    SegmentedTabs, format_range, hbox, show_status, text, two_line, vbox,
)
from ..shell import Page
from ..theme import Color, Type
from .common import confirm_close_batch, open_export_pdf

_MENU_STYLE = (f"QMenu {{ background: #FFFFFF; border: 1px solid {Color.BORDER}; border-radius: 12px; padding: 6px; }}"
               "QMenu::item { padding: 8px 14px; border-radius: 8px; }"
               f"QMenu::item:selected {{ background: {Color.BRAND_SOFT}; color: {Color.TEXT_PRIMARY}; }}")


class BatchPage(Page):
    def __init__(self, controller: BatchController, window_getter, open_report=None):
        super().__init__("Batch")
        self._ctrl = controller
        self._win = window_getter
        self._open_report = open_report
        self.filter_key = None
        self.sku = None
        self.page_index = 0
        self.range = (QDate(2026, 11, 23), QDate(2026, 11, 25))

        self.search = SearchField("Cari kode batch", 260)
        self.search.edit.textChanged.connect(lambda _: self._reset_page())
        self.actions.addWidget(self.search)
        self.date_btn = Button(format_range(*self.range), "outline", "md", "calendar")
        self.date_btn.clicked.connect(self._pick_date)
        self.actions.addWidget(self.date_btn)
        create = Button("Buat batch", "primary", "md", "plus")
        create.clicked.connect(lambda: self._create_dialog())
        self.actions.addWidget(create)

        bar = AdaptiveRow(spacing=12)
        self.tabs = SegmentedTabs([(label, "0") for label, _ in FILTERS])
        self.tabs.changed.connect(self._on_tab)
        bar.add(self.tabs, 0, align=Qt.AlignmentFlag.AlignLeft)
        bar.add_stretch()
        tools = QWidget()
        t_lay = hbox(12, (0, 0, 0, 0), tools)
        self.product_btn = Button("Semua produk", "outline", "md", "filter")
        self.product_btn.clicked.connect(self._product_menu)
        t_lay.addWidget(self.product_btn)
        export = Button("Ekspor PDF", "secondary", "md", "download")
        export.clicked.connect(lambda: open_export_pdf(self._win()))
        t_lay.addWidget(export)
        bar.add(tools, 0, align=Qt.AlignmentFlag.AlignLeft)
        self.body.addWidget(bar)

        self.table = DataTable(
            [("Kode batch", 10, "L"), ("Produk", 16, "L"), ("Waktu", 11, "L", None, 1180), ("Output", 7, "R"),
             ("Persentase NG", 17, "F", 32), ("Batch", 9, "L"), ("Inspeksi", 9, "L"), ("", 11, "R", 0)],
            row_padding=10)
        footer = QFrame()
        footer.setObjectName("Foot")
        footer.setStyleSheet(f"QFrame#Foot {{ border: none; border-top: 1px solid {Color.BORDER}; }}")
        self._footer = hbox(6, (20, 10, 16, 10), footer)
        self.footer_label = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        self._footer.addWidget(self.footer_label, 1)
        self._pager = QWidget()
        self._pager_lay = hbox(6, (0, 0, 0, 0), self._pager)
        self._footer.addWidget(self._pager)
        self.table.add_footer(footer)
        self.body.addWidget(self.table, 1)
        self._render()

    def on_show(self) -> None:
        self._render()

    # data ----------------------------------------------------------------
    def _filters(self) -> dict:
        return {"sku": self.sku, "query": self.search.edit.text(),
                "start": self.range[0].toPyDate(), "end": self.range[1].toPyDate()}

    def _render(self) -> None:
        filters = self._filters()
        self.tabs.set_counts(self._ctrl.tab_counts(**filters))
        rows = self._ctrl.search(self.filter_key, **filters)
        pages = self._ctrl.page_count(rows)
        self.page_index = min(self.page_index, pages - 1)
        shown = self._ctrl.page(rows, self.page_index)
        self.table.clear_rows()
        for b in shown:
            frac = b.ng_percent / NG_TOLERANCE_PERCENT
            tone = "pink" if frac > 1 else ("blue" if frac > 0.8 else "indigo")
            bar = ProgressBar("NG", fmt.pct(b.ng_percent), frac, tone, marker=1.0 if frac > 1 else None)
            if b.running:
                action = Button("Tutup batch", "outline", "sm", "lock")
                action.clicked.connect(lambda _=False, code=b.code: self._close(code))
            else:
                action = QWidget()
                a = hbox(2, (0, 0, 0, 0), action)
                report = IconButton("report", "Lihat laporan", "ghost", 34, Color.ICON)
                report.clicked.connect(lambda _=False, code=b.code: self._show_report(code))
                a.addWidget(report)
                dl = IconButton("download", "Ekspor PDF", "ghost", 34, Color.ICON)
                dl.clicked.connect(lambda _=False, code=b.code, p=b.product: open_export_pdf(self._win(), code, p))
                a.addWidget(dl)
                a.addWidget(IconButton("more", "Lainnya", "ghost", 34, Color.ICON))
            self.table.add_row([two_line(b.code, b.sku), text(b.product, Type.BODY),
                                two_line(b.start_label, b.duration, strong=False),
                                text(fmt.num(b.output), Type.BODY_STRONG), bar,
                                Badge(b.status), Badge(b.inspection), action])
        total = len(self._ctrl.search(None, **filters))
        self.footer_label.setText(
            f"Menampilkan {len(shown)} dari {total} batch pada {format_range(*self.range)}."
            f" Batas toleransi NG {NG_TOLERANCE_PERCENT:g}%.")
        self._render_pager(pages)

    def _render_pager(self, pages: int) -> None:
        while self._pager_lay.count():
            w = self._pager_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i in range(pages):
            b = Button(str(i + 1), "navy" if i == self.page_index else "outline", "sm")
            b.setFixedWidth(36)
            b.setStyleSheet("QPushButton { padding: 0; border-radius: 10px; }")
            b.clicked.connect(lambda _=False, k=i: self._go_page(k))
            self._pager_lay.addWidget(b)
        nxt = IconButton("chevron-right", "Halaman berikutnya", "outline", 36)
        nxt.setEnabled(self.page_index < pages - 1)
        nxt.clicked.connect(lambda: self._go_page(self.page_index + 1))
        self._pager_lay.addWidget(nxt)

    # actions ---------------------------------------------------------------
    def _go_page(self, index: int) -> None:
        self.page_index = index
        self._render()

    def _reset_page(self) -> None:
        self.page_index = 0
        self._render()

    def _on_tab(self, index: int) -> None:
        self.filter_key = FILTERS[index][1]
        self._reset_page()

    def _product_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_MENU_STYLE)
        for p in [None] + self._ctrl.products():
            act = menu.addAction(p.name if p else "Semua produk")
            act.triggered.connect(lambda _=False, pp=p: self._set_product(pp))
        menu.exec(self.product_btn.mapToGlobal(self.product_btn.rect().bottomLeft()))

    def _set_product(self, product) -> None:
        self.sku = product.sku if product else None
        self.product_btn.setText(f" {product.name if product else 'Semua produk'}")
        self._reset_page()

    def _pick_date(self) -> None:
        picker = DatePicker(*self.range, QDate(2026, 11, 25), self)
        picker.applied.connect(self._set_range)
        picker.popup_below(self.date_btn)

    def _set_range(self, start: QDate, end: QDate) -> None:
        self.range = (start, end)
        self.date_btn.setText(f" {format_range(start, end)}")
        self._reset_page()

    def _show_report(self, code: str) -> None:
        if self._open_report:
            self._open_report(code)

    def _close(self, code: str) -> None:
        def closed():
            self._ctrl.close(code)
            self._render()
        confirm_close_batch(self._win(), code, closed)

    def _create_dialog(self, code: str = "B-2411-04") -> None:
        card = ModalCard(480)
        holder: dict = {}
        card.header("layers", "Buat batch baru", "Batch langsung menerima data setelah disimpan",
                    lambda: holder["o"].close_overlay())
        f_code = InputField("Kode batch", "Contoh: B-2411-04", code, "layers",
                            helper="Format B-TTBB-NN dan harus unik.")
        card.body.addWidget(f_code)
        products = self._ctrl.products()
        chosen = {"p": products[0]}
        f_prod = InputField("Produk", "", products[0].label, "package", trailing="dropdown")
        f_prod.edit.setReadOnly(True)

        def pick_product():
            menu = QMenu(f_prod)
            for p in products:
                act = menu.addAction(p.label)
                act.triggered.connect(lambda _=False, pp=p: (chosen.update(p=pp), f_prod.edit.setText(pp.label)))
            menu.exec(f_prod.field.mapToGlobal(f_prod.field.rect().bottomLeft()))

        f_prod.trailing_clicked.connect(pick_product)
        card.body.addWidget(f_prod)
        info = QFrame()
        info.setObjectName("Info")
        info.setStyleSheet(f"QFrame#Info {{ background: {Color.SUBTLE}; border: 1px solid {Color.BORDER}; border-radius: 14px; }}")
        i_lay = vbox(2, (14, 12, 14, 12), info)
        i_lay.addWidget(text("Langkah berikutnya", Type.BODY_STRONG))
        self._next_label = text("", Type.CAPTION, Color.TEXT_SECONDARY, wrap=True)
        i_lay.addWidget(self._next_label)
        card.body.addWidget(info)

        def update_hint():
            self._next_label.setText(f"Masukkan kode {f_code.value() or 'batch'} ke konfigurasi ESP32-CAM agar foto "
                                     "kaleng tercatat pada batch ini.")
        f_code.edit.textChanged.connect(lambda _: update_hint())
        update_hint()
        row = hbox(10)
        cancel = Button("Batal", "outline")
        save = Button("Buat batch", "primary", "md", "plus")
        for b in (cancel, save):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(b)
        card.body.addLayout(row)
        holder["o"] = Overlay(self._win(), card).open()
        cancel.clicked.connect(holder["o"].close_overlay)

        def submit():
            p = chosen["p"]
            result = self._ctrl.create(f_code.value(), p)
            if result.error == "format":
                f_code.set_error("Format kode batch belum sesuai, contoh B-2411-04.")
                return
            holder["o"].close_overlay()
            value = f_code.value().strip().upper()
            if result.error == "duplicate":
                show_status(self._win(), "failed", "Kode batch sudah digunakan",
                            f"Kode {value} sudah terdaftar. Gunakan kode batch lain, lalu simpan kembali.",
                            [("Batal", "outline", None), ("Ganti kode", "primary", lambda: self._create_dialog(value))])
                return
            self._reset_page()
            show_status(self._win(), "success", "Batch berhasil dibuat",
                        f"Batch {value} untuk produk {p.name} siap menerima data dari ESP32-CAM.",
                        [("Lihat batch", "primary", None)])

        save.clicked.connect(submit)
        f_code.edit.returnPressed.connect(submit)
        f_code.edit.setFocus()
        f_code.edit.selectAll()

