"""Batch (FR-05, FR-06, FR-27): list with filters, date range, create and close batch."""

import re

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QFrame, QMenu, QSizePolicy, QWidget

from .. import mock_data as data
from ..components import (
    Badge, Button, DataTable, DatePicker, IconButton, InputField, ModalCard, Overlay, ProgressBar, SearchField,
    SegmentedTabs, format_range, hbox, show_status, text, two_line, vbox,
)
from ..shell import Page
from ..theme import NG_TOLERANCE_PERCENT, Color, Type
from .common import confirm_close_batch, open_export_pdf

_FILTERS = [None, "BERJALAN", "PASSED", "HOLD"]
_CODE = re.compile(r"^B-\d{4}-\d{2}$")


class BatchPage(Page):
    def __init__(self, window_getter):
        super().__init__("Batch", "Buat, pantau, dan tutup batch produksi")
        self._win = window_getter
        self.batches = [dict(b) for b in data.BATCHES]
        self.filter = None
        self.range = (QDate(2026, 11, 23), QDate(2026, 11, 25))

        self.search = SearchField("Cari kode batch", 260)
        self.search.edit.textChanged.connect(lambda _: self._render())
        self.actions.addWidget(self.search)
        self.date_btn = Button(format_range(*self.range), "outline", "md", "calendar")
        self.date_btn.clicked.connect(self._pick_date)
        self.actions.addWidget(self.date_btn)
        create = Button("Buat batch", "primary", "md", "plus")
        create.clicked.connect(self._create_dialog)
        self.actions.addWidget(create)

        bar = hbox(12)
        self.tabs = SegmentedTabs(self._tab_items())
        self.tabs.changed.connect(self._on_tab)
        bar.addWidget(self.tabs)
        bar.addStretch(1)
        self.product_btn = Button("Semua produk", "outline", "md", "filter")
        self.product_btn.clicked.connect(self._product_menu)
        bar.addWidget(self.product_btn)
        export = Button("Ekspor PDF", "secondary", "md", "download")
        export.clicked.connect(lambda: open_export_pdf(self._win()))
        bar.addWidget(export)
        self.body.addLayout(bar)

        self.table = DataTable(
            [("Kode batch", 10, "L"), ("Produk", 15, "L"), ("Waktu", 11, "L"), ("Output", 7, "R"),
             ("Persentase NG", 17, "F", 32), ("Batch", 9, "L"), ("Inspeksi", 9, "L"), ("", 10, "R", 0)],
            row_padding=10)
        footer = QFrame()
        footer.setObjectName("Foot")
        footer.setStyleSheet(f"QFrame#Foot {{ border: none; border-top: 1px solid {Color.BORDER}; }}")
        f_lay = hbox(6, (20, 10, 16, 10), footer)
        self.footer_label = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        f_lay.addWidget(self.footer_label, 1)
        for label, on in (("1", True), ("2", False)):
            b = Button(label, "navy" if on else "outline", "sm")
            b.setFixedWidth(36)
            b.setStyleSheet("QPushButton { padding: 0; border-radius: 10px; }")
            f_lay.addWidget(b)
        f_lay.addWidget(IconButton("chevron-right", "Halaman berikutnya", "outline", 36))
        self.table.add_footer(footer)
        self.body.addWidget(self.table, 1)
        self.product = None
        self._render()

    # data ----------------------------------------------------------------
    def _tab_items(self) -> list:
        count = lambda st: sum(1 for b in self.batches if st in (b["batch"], b["inspection"]))  # noqa: E731
        return [("Semua", str(data.BATCH_TOTAL)), ("Berjalan", str(count("BERJALAN"))),
                ("PASSED", str(count("PASSED") + 4)), ("HOLD", str(count("HOLD") - 1))]

    def _visible(self) -> list:
        q = self.search.edit.text().strip().upper()
        rows = []
        for b in self.batches:
            if self.filter and self.filter not in (b["batch"], b["inspection"]):
                continue
            if self.product and b["product"] != self.product:
                continue
            if q and q not in b["code"]:
                continue
            rows.append(b)
        return rows

    def _render(self) -> None:
        self.table.clear_rows()
        rows = self._visible()
        for b in rows:
            frac = b["ng_percent"] / NG_TOLERANCE_PERCENT
            tone = "pink" if frac > 1 else ("blue" if frac > 0.8 else "indigo")
            bar = ProgressBar("NG", data.pct(b["ng_percent"]), frac, tone, marker=1.0 if frac > 1 else None)
            if b["batch"] == "BERJALAN":
                action = Button("Tutup batch", "outline", "sm", "lock")
                action.clicked.connect(lambda _=False, code=b["code"]: self._close(code))
            else:
                action = QWidget()
                a = hbox(2, (0, 0, 0, 0), action)
                a.addWidget(IconButton("report", "Lihat laporan", "ghost", 34, Color.ICON))
                dl = IconButton("download", "Ekspor PDF", "ghost", 34, Color.ICON)
                dl.clicked.connect(lambda _=False, code=b["code"], p=b["product"]: open_export_pdf(self._win(), code, p))
                a.addWidget(dl)
                a.addWidget(IconButton("more", "Lainnya", "ghost", 34, Color.ICON))
            self.table.add_row([two_line(b["code"], b["sku"]), text(b["product"], Type.BODY),
                                two_line(b["start"], b["duration"], strong=False),
                                text(data.num(b["output"]), Type.BODY_STRONG), bar,
                                Badge(b["batch"]), Badge(b["inspection"]), action])
        self.footer_label.setText(
            f"Menampilkan {len(rows)} dari {data.BATCH_TOTAL} batch pada {format_range(*self.range)}."
            f" Batas toleransi NG {NG_TOLERANCE_PERCENT:g}%.")

    # actions ---------------------------------------------------------------
    def _on_tab(self, index: int) -> None:
        self.filter = _FILTERS[index]
        self._render()

    def _product_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: #FFFFFF; border: 1px solid {Color.BORDER}; border-radius: 12px; padding: 6px; }}"
                           f"QMenu::item {{ padding: 8px 14px; border-radius: 8px; }}"
                           f"QMenu::item:selected {{ background: {Color.BRAND_SOFT}; color: {Color.TEXT_PRIMARY}; }}")
        for name in [None] + [p["name"] for p in data.PRODUCTS]:
            act = menu.addAction(name or "Semua produk")
            act.triggered.connect(lambda _=False, n=name: self._set_product(n))
        menu.exec(self.product_btn.mapToGlobal(self.product_btn.rect().bottomLeft()))

    def _set_product(self, name) -> None:
        self.product = name
        self.product_btn.setText(f" {name or 'Semua produk'}")
        self._render()

    def _pick_date(self) -> None:
        picker = DatePicker(*self.range, QDate(2026, 11, 25), self)
        picker.applied.connect(self._set_range)
        picker.popup_below(self.date_btn)

    def _set_range(self, start: QDate, end: QDate) -> None:
        self.range = (start, end)
        self.date_btn.setText(f" {format_range(start, end)}")
        self._render()

    def _close(self, code: str) -> None:
        def closed():
            for b in self.batches:
                if b["code"] == code:
                    b["batch"] = "DITUTUP"
                    b["inspection"] = "HOLD" if b["ng_percent"] > NG_TOLERANCE_PERCENT else "PASSED"
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
        products = list(data.PRODUCTS)
        chosen = {"p": products[0]}
        f_prod = InputField("Produk", "", f"{products[0]['name']} ({products[0]['sku']})", "package", trailing="dropdown")
        f_prod.edit.setReadOnly(True)

        def pick_product():
            menu = QMenu(f_prod)
            for p in products:
                act = menu.addAction(f"{p['name']} ({p['sku']})")
                act.triggered.connect(lambda _=False, pp=p: (chosen.update(p=pp),
                                                             f_prod.edit.setText(f"{pp['name']} ({pp['sku']})")))
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
            value = f_code.value().strip().upper()
            if not _CODE.match(value):
                f_code.set_error("Format kode batch belum sesuai, contoh B-2411-04.")
                return
            holder["o"].close_overlay()
            if any(b["code"] == value for b in self.batches):
                show_status(self._win(), "failed", "Kode batch sudah digunakan",
                            f"Kode {value} sudah terdaftar. Gunakan kode batch lain, lalu simpan kembali.",
                            [("Batal", "outline", None), ("Ganti kode", "primary", lambda: self._create_dialog(value))])
                return
            p = chosen["p"]
            self.batches.insert(0, {"code": value, "sku": p["sku"], "product": p["name"], "start": "25 Nov, baru saja",
                                    "duration": "berjalan 0 menit", "output": 0, "ng_percent": 0.0,
                                    "batch": "BERJALAN", "inspection": "HOLD"})
            self._render()
            show_status(self._win(), "success", "Batch berhasil dibuat",
                        f"Batch {value} untuk produk {p['name']} siap menerima data dari ESP32-CAM.",
                        [("Lihat batch", "primary", None)])

        save.clicked.connect(submit)
        f_code.edit.returnPressed.connect(submit)
        f_code.edit.setFocus()
        f_code.edit.selectAll()

