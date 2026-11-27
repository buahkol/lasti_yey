"""Produk (FR-04, FR-18): availability per product, product list and edit form."""

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from ...controllers import ProductController
from ...models import Product
from .. import formatting as fmt
from ..assets import pixmap
from ..components import (
    AdaptiveRow, Badge, Button, Card, DataTable, DatePicker, IconButton, InputField, PanelHeader, ProgressBar,
    ResponsiveGrid, format_range, hbox, text, toast, vbox,
)
from ..shell import Page
from ..theme import TONES, Color, Type


class AvailabilityCard(Card):
    def __init__(self, product: Product, highlight: bool = False):
        super().__init__((18, 18, 18, 18), 10)
        if highlight:
            self.setStyleSheet(
                "QFrame#Card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(168,233,236,0.28),"
                " stop:0.55 rgba(244,179,205,0.16), stop:1 #FFFFFF); border: 1px solid rgba(168,233,236,0.6);"
                " border-radius: 20px; }"
            )
        t = TONES["blue"]
        top = hbox(10)
        chip = QLabel()
        chip.setFixedSize(38, 38)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(pixmap("package", t.ink, 20))
        chip.setStyleSheet(f"background: {t.soft}; border: 1px solid {t.mid}; border-radius: 12px;")
        top.addWidget(chip)
        col = vbox(0)
        col.addWidget(text(product.name, Type.BODY_STRONG))
        col.addWidget(text(product.sku, Type.CAPTION, Color.TEXT_TERTIARY))
        top.addLayout(col, 1)
        self.layout_.addLayout(top)
        row = hbox(6)
        row.addWidget(text(fmt.num(product.ok_today), Type.DISPLAY), 0, Qt.AlignmentFlag.AlignBottom)
        row.addWidget(text("kaleng OK", Type.LABEL, Color.TEXT_TERTIARY), 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        self.layout_.addLayout(row)
        self.add(ProgressBar("Rasio OK", fmt.pct(product.ok_ratio), product.ok_ratio / 100, "indigo",
                             caption=f"Diperbarui {product.updated}"))


class ProdukPage(Page):
    def __init__(self, controller: ProductController, window_getter):
        super().__init__("Produk")
        self._ctrl = controller
        self._win = window_getter
        self.products = self._ctrl.products()
        self.current: int | None = None
        self.creating = False
        self.date_btn = Button("Hari ini, 25 Nov 2026", "outline", "md", "calendar")
        self.date_btn.clicked.connect(self._pick_date)
        self.actions.addWidget(self.date_btn)
        add = Button("Tambah produk", "primary", "md", "plus")
        add.clicked.connect(self._new)
        self.actions.addWidget(add)

        body = AdaptiveRow(breakpoint=1180)
        left_w = QWidget()
        left = vbox(16, (0, 0, 0, 0), left_w)
        cards = ResponsiveGrid(230, 3, 16, steps=(3, 1))
        for i, p in enumerate(self.products):
            cards.add(AvailabilityCard(p, highlight=i == 0))
        left.addWidget(cards)
        self.table = DataTable(
            [("SKU", 12, "L"), ("Nama produk", 22, "L"), ("Harga", 12, "R"), ("Ambang", 9, "R"),
             ("Status", 14, "L"), ("", 8, "R", 0)],
            PanelHeader("Daftar produk", f"{len(self.products)} SKU terdaftar"), row_padding=12)
        self.table.row_clicked.connect(self._load)
        self._fill_table()
        left.addWidget(self.table, 1)
        body.add(left_w, 1)
        self.form = self._form()
        body.add(self.form, 0, fixed_width=400)
        self.body.addWidget(body, 1)
        self.form.hide()

    def _fill_table(self) -> None:
        self.table.clear_rows()
        for i, p in enumerate(self.products):
            actions = QWidget()
            a_lay = hbox(2, (0, 0, 0, 0), actions)
            edit = IconButton("edit", "Ubah produk", "ghost", 34, Color.ICON)
            edit.clicked.connect(lambda _=False, k=i: self._load(k))
            a_lay.addWidget(edit)
            self.table.add_row([text(p.sku, Type.BODY_STRONG), text(p.name, Type.BODY),
                                text(fmt.rupiah(p.price), Type.BODY_STRONG),
                                text(fmt.score(p.threshold), Type.BODY_STRONG),
                                Badge(p.status), actions], selected=i == self.current)

    def _form(self) -> Card:
        card = Card((22, 22, 22, 22), 18)
        head = hbox(8)
        col = vbox(2)
        self.form_title = text("Ubah produk", Type.TITLE)
        col.addWidget(self.form_title)
        self.form_caption = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        col.addWidget(self.form_caption)
        head.addLayout(col, 1)
        close = IconButton("x", "Tutup formulir", "soft")
        close.clicked.connect(self._close_form)
        head.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        card.layout_.addLayout(head)
        self.f_sku = InputField("SKU", "Contoh: SDN-TMT-155", "", "package",
                                helper="SKU tidak dapat diubah setelah dipakai batch.")
        self.f_name = InputField("Nama produk", "Contoh: Sarden saus tomat 155 g", "", "edit")
        self.f_price = InputField("Harga satuan (Rp)", "Contoh: 12.500", "", "report",
                                  helper="Dipakai untuk menghitung estimasi kerugian.")
        for f in (self.f_sku, self.f_name, self.f_price):
            card.add(f)
        note = QFrame()
        note.setObjectName("Note")
        t = TONES["indigo"]
        note.setStyleSheet(f"QFrame#Note {{ background: {t.soft}; border-radius: 14px; }}")
        n_lay = hbox(10, (14, 12, 14, 12), note)
        ic = QLabel()
        ic.setPixmap(pixmap("shield", t.ink, 18))
        n_lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        n_lay.addWidget(text("Ambang batas dan versi model diatur oleh tim AI melalui program terpisah.",
                             Type.CAPTION, t.ink, wrap=True), 1)
        card.add(note)
        card.layout_.addStretch(1)
        row = hbox(10)
        cancel = Button("Batal", "outline")
        cancel.clicked.connect(self._close_form)
        save = Button("Simpan perubahan", "primary")
        save.clicked.connect(self._save)
        for b in (cancel, save):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(b)
        card.layout_.addLayout(row)
        return card

    def _close_form(self) -> None:
        self.form.hide()
        self.current = None
        self.creating = False
        self.table.select(-1)
        for f in (self.f_sku, self.f_name, self.f_price):
            f.set_error(None)

    def _load(self, index: int) -> None:
        self.current = index
        self.creating = False
        self.form.show()
        p = self.products[index]
        self.table.select(index)
        self.form_title.setText("Ubah produk")
        self.form_caption.setText(f"{p.sku}, dipakai oleh {p.batch_count} batch")
        self.f_sku.edit.setText(p.sku)
        self.f_sku.setEnabled(False)
        self.f_name.edit.setText(p.name)
        self.f_price.edit.setText(fmt.num(p.price))
        for f in (self.f_name, self.f_price):
            f.set_error(None)

    def _new(self) -> None:
        self.current = None
        self.creating = True
        self.form.show()
        self.table.select(-1)
        self.form_title.setText("Tambah produk")
        self.form_caption.setText("Produk baru muncul di pilihan saat membuat batch")
        for f in (self.f_sku, self.f_name, self.f_price):
            f.edit.clear()
            f.set_error(None)
        self.f_sku.setEnabled(True)
        self.f_sku.edit.setFocus()

    def _save(self) -> None:
        is_new = self.creating
        for f in (self.f_sku, self.f_name, self.f_price):
            f.set_error(None)
        product, errors = self._ctrl.save(self.f_sku.value(), self.f_name.value(), self.f_price.value(), is_new)
        fields = {"sku": self.f_sku, "name": self.f_name, "price": self.f_price}
        for key, message in errors.items():
            fields[key].set_error(message)
        if product is None:
            return
        self.products = self._ctrl.products()
        self._fill_table()
        self._close_form()
        toast(self._win(), "success", "Produk tersimpan", f"Perubahan {product.sku} berhasil disimpan.")

    def _pick_date(self) -> None:
        picker = DatePicker(QDate(2026, 11, 25), QDate(2026, 11, 25), QDate(2026, 11, 25), self)
        picker.applied.connect(lambda s, e: self.date_btn.setText(
            "Hari ini, 25 Nov 2026" if s == e == QDate(2026, 11, 25) else format_range(s, e)))
        picker.popup_below(self.date_btn)
