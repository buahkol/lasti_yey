from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QWidget

from ...controllers import ShipmentController
from ...models import Batch
from .. import formatting as fmt
from ..assets import pixmap
from ..components import (
    AdaptiveRow, Badge, Button, Card, Checkbox, DataTable, InputField, PanelHeader, TableFooter, hbox, show_status,
    text, toast, two_line, vbox,
)
from ..shell import Page
from ..theme import TONES, Color, Type


def _chips(codes: list) -> QWidget:
    w = QWidget()
    lay = hbox(6, (0, 0, 0, 0), w)
    for code in codes:
        chip = QFrame()
        chip.setObjectName("Chip")
        chip.setStyleSheet(f"QFrame#Chip {{ background: {Color.SUBTLE}; border: 1px solid {Color.BORDER};"
                           " border-radius: 14px; }")
        c_lay = hbox(6, (8, 3, 10, 3), chip)
        icon = QLabel()
        icon.setPixmap(pixmap("layers", Color.TEXT_SECONDARY, 14))
        c_lay.addWidget(icon)
        c_lay.addWidget(text(code, Type.LABEL))
        lay.addWidget(chip)
    return w


class _BatchOption(QFrame):
    def __init__(self, batch: Batch, on_change):
        super().__init__()
        self.batch = batch
        self.setObjectName("Opt")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = vbox(4, (14, 10, 14, 10), self)
        top = hbox(8)
        self.check = Checkbox(batch.code)
        self.check.toggled.connect(lambda _: (self._style(), on_change()))
        top.addWidget(self.check)
        top.addStretch(1)
        top.addWidget(Badge(batch.inspection))
        lay.addLayout(top)
        caption = text(f"{batch.product}, {fmt.num(batch.ok_count)} kaleng OK", Type.CAPTION, Color.TEXT_TERTIARY)
        caption.setContentsMargins(30, 0, 0, 0)
        lay.addWidget(caption)
        self._style()

    def _style(self) -> None:
        t = TONES["indigo"]
        on = self.check.isChecked()
        self.setStyleSheet(f"QFrame#Opt {{ background: {t.soft if on else Color.SURFACE};"
                           f" border: 1px solid {t.mid if on else Color.BORDER}; border-radius: 14px; }}")

    def mouseReleaseEvent(self, e):
        if not self.check.geometry().contains(e.position().toPoint()):
            self.check.toggle()
        super().mouseReleaseEvent(e)


class PengirimanPage(Page):
    def __init__(self, controller: ShipmentController, window_getter):
        super().__init__("Pengiriman")
        self._ctrl = controller
        self._win = window_getter
        self._highlight_first = False
        self.options: list[_BatchOption] = []

        body = AdaptiveRow(breakpoint=1180)
        self.table = DataTable(
            [("No. pesanan", 12, "L"), ("Kode batch", 24, "L"), ("Jumlah kaleng", 10, "R"), ("Dicatat pada", 12, "L")],
            PanelHeader("Daftar pengiriman", "Setiap pengiriman tercatat bersama kode batch asalnya"), row_padding=12)
        self.footer = TableFooter()
        self.table.add_footer(self.footer)
        body.add(self.table, 1)
        body.add(self._form(), 0, fixed_width=440)
        self.body.addWidget(body, 1)
        self._render()

    def on_show(self) -> None:
        self._render()
        self._fill_options()

    def _render(self) -> None:
        rows = self._ctrl.shipments()
        self.table.clear_rows()
        for i, s in enumerate(rows):
            self.table.add_row([text(s.order_id, Type.BODY_STRONG), _chips(s.batch_codes),
                                text(fmt.num(s.quantity), Type.BODY_STRONG),
                                two_line(fmt.day(s.created_at, year=True), f"pukul {s.created_at:%H.%M}", strong=False)],
                               selected=i == 0 and self._highlight_first)
        self._highlight_first = False
        self.table.set_empty(None if rows else "Belum ada pengiriman yang dicatat.")
        self.footer.update_state(f"Menampilkan {len(rows)} pengiriman. Batch berstatus HOLD ditolak oleh server.", 0, 1)

    def _form(self) -> Card:
        card = Card((22, 22, 22, 22), 16)
        head = vbox(2)
        head.addWidget(text("Catat pengiriman", Type.TITLE))
        head.addWidget(text("Pilih batch asal kaleng untuk pesanan ini", Type.CAPTION, Color.TEXT_TERTIARY))
        card.layout_.addLayout(head)

        self.f_order = InputField("Nomor pesanan", "Contoh: PO-2611-018", "", "file")
        card.add(self.f_order)

        label_row = hbox(8)
        label_row.addWidget(text("Batch yang dikirim", Type.LABEL), 1)
        label_row.addWidget(text("hanya PASSED", Type.CAPTION, Color.TEXT_TERTIARY))
        card.layout_.addLayout(label_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(220)
        scroll.viewport().setStyleSheet("background: transparent;")
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self._options_lay = vbox(8, (0, 0, 0, 0), holder)
        scroll.setWidget(holder)
        card.add(scroll, 1)
        self.batch_error = text("", Type.CAPTION, TONES["pink"].ink)
        self.batch_error.hide()
        card.add(self.batch_error)
        self._fill_options()

        self.f_qty = InputField("Jumlah kaleng", "Contoh: 1.200", "", "package")
        self.f_qty.edit.returnPressed.connect(self._save)
        card.add(self.f_qty)

        row = hbox(10)
        cancel = Button("Batal", "outline")
        cancel.clicked.connect(self._reset_form)
        save = Button("Simpan pengiriman", "primary", "md", "check")
        save.clicked.connect(self._save)
        for b in (cancel, save):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(b)
        card.layout_.addLayout(row)
        return card

    def _chosen(self) -> list[str]:
        return [o.batch.code for o in self.options if o.check.isChecked()]

    def _fill_options(self, drop: tuple = ()) -> None:
        keep = set(self._chosen()) - set(drop)
        while self._options_lay.count():
            item = self._options_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.options = []
        for b in self._ctrl.passed_batches():
            opt = _BatchOption(b, lambda: self._set_batch_error(None))
            opt.check.setChecked(b.code in keep)
            self._options_lay.addWidget(opt)
            self.options.append(opt)
        if not self.options:
            self._options_lay.addWidget(text("Belum ada batch berstatus PASSED.", Type.BODY, Color.TEXT_TERTIARY))
        self._options_lay.addStretch(1)

    def _set_batch_error(self, message: str | None) -> None:
        self.batch_error.setText(message or "")
        self.batch_error.setVisible(bool(message))

    def _reset_form(self) -> None:
        for f in (self.f_order, self.f_qty):
            f.edit.clear()
            f.set_error(None)
        for o in self.options:
            o.check.setChecked(False)
        self._set_batch_error(None)

    def _save(self) -> None:
        result = self._ctrl.submit(self.f_order.value(), self._chosen(), self.f_qty.value())
        self.f_order.set_error(result.errors.get("order"))
        self.f_qty.set_error(result.errors.get("quantity"))
        self._set_batch_error(result.errors.get("batches"))
        if result.hold_batches:
            show_status(self._win(), "failed", "Pengiriman ditolak",
                        f"Server menolak pengiriman ini karena memuat batch berstatus HOLD: "
                        f"{', '.join(result.hold_batches)}. Hapus batch tersebut dari pengiriman, lalu simpan kembali.",
                        [("Batal", "outline", None),
                         ("Ubah pilihan batch", "primary", lambda: self._fill_options(result.hold_batches))])
            return
        s = result.shipment
        if s is None:
            return
        self._highlight_first = True
        self._reset_form()
        self._render()
        toast(self._win(), "success", "Pengiriman tersimpan",
              f"{s.order_id} berisi {len(s.batch_codes)} batch PASSED, total {fmt.num(s.quantity)} kaleng.")
