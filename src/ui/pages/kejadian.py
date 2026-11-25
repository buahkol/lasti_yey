from PyQt6.QtWidgets import QButtonGroup, QMenu, QSizePolicy, QWidget

from ...controllers import EventController
from ...controllers.event_controller import MANUAL_KINDS
from ...models import Batch
from ..components import (
    AdaptiveRow, Button, Card, DataTable, InputField, RadioOption, TableFooter, event_kind, hbox, text, toast, vbox,
)
from ..shell import Page
from ..theme import Color, Type
from .batch import _MENU_STYLE


class KejadianPage(Page):
    def __init__(self, controller: EventController, window_getter):
        super().__init__("Kejadian produksi")
        self._ctrl = controller
        self._win = window_getter
        self.page_index = 0
        self._highlight_first = False
        running = sorted(controller.running_batches(), key=lambda b: b.started_at)
        self.code = running[-1].code if running else controller.batches()[0].code

        self.batch_btn = Button(self.code, "outline", "md", "layers")
        self.batch_btn.clicked.connect(self._batch_menu)
        self.actions.addWidget(self.batch_btn)

        body = AdaptiveRow(breakpoint=1180)
        self.table = DataTable([("Waktu", 8, "L"), ("Jenis", 16, "L"), ("Sumber", 10, "L"), ("Keterangan", 40, "L")],
                               row_padding=12)
        self.footer = TableFooter()
        self.footer.page_changed.connect(self._go_page)
        self.table.add_footer(self.footer)
        body.add(self.table, 1)
        body.add(self._form(running[-1] if running else None), 0, fixed_width=400)
        self.body.addWidget(body, 1)
        self._render()

    def on_show(self) -> None:
        self._render()

    def show_batch(self, code: str) -> None:
        batch = self._ctrl.find_batch(code)
        if batch is None:
            return
        self.code = code
        self.batch_btn.setText(f" {code}")
        self.page_index = 0
        if batch.running:
            self._set_form_batch(batch)
        self._render()

    def _render(self) -> None:
        rows = self._ctrl.events(self.code)
        pages = self._ctrl.page_count(rows)
        self.page_index = min(self.page_index, pages - 1)
        shown = self._ctrl.page(rows, self.page_index)
        self.table.clear_rows()
        for i, e in enumerate(shown):
            source_color = Color.TEXT_LINK if e.source == "AI" else Color.TEXT_PRIMARY
            self.table.add_row([text(e.time, Type.BODY_STRONG), event_kind(e.kind),
                                text(e.source, Type.BODY_STRONG, source_color),
                                text(e.note or "-", Type.BODY, Color.TEXT_SECONDARY)],
                               selected=i == 0 and self._highlight_first)
        self._highlight_first = False
        self.table.set_empty(None if rows else f"Belum ada kejadian pada batch {self.code}.")
        self.footer.update_state(f"Menampilkan {len(shown)} dari {len(rows)} kejadian batch {self.code}. "
                                 "REJECT dicatat otomatis setiap kali AI menyatakan kaleng NG.", self.page_index, pages)

    def _go_page(self, index: int) -> None:
        self.page_index = index
        self._render()

    def _batch_menu(self) -> None:
        self._menu(self.batch_btn, self._ctrl.batches(), lambda b: self.show_batch(b.code))

    def _menu(self, anchor: QWidget, batches: list, on_pick) -> None:
        menu = QMenu(anchor)
        menu.setStyleSheet(_MENU_STYLE)
        for b in batches:
            menu.addAction(f"{b.code}, {b.product}").triggered.connect(lambda _=False, bb=b: on_pick(bb))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _form(self, batch: Batch | None) -> Card:
        card = Card((22, 22, 22, 22), 18)
        head = vbox(2)
        head.addWidget(text("Catat kejadian", Type.TITLE))
        head.addWidget(text("Kejadian REJECT sudah dicatat otomatis oleh AI", Type.CAPTION, Color.TEXT_TERTIARY))
        card.layout_.addLayout(head)

        self.f_batch = InputField("Batch", "Pilih batch yang sedang berjalan", "", "layers", trailing="dropdown",
                                  helper="Pilih salah satu batch yang sedang berjalan")
        self.f_batch.edit.setReadOnly(True)
        self.f_batch.trailing_clicked.connect(
            lambda: self._menu(self.f_batch.field, self._ctrl.running_batches(), self._set_form_batch))
        card.add(self.f_batch)
        self._set_form_batch(batch)

        kinds = QWidget()
        k_lay = vbox(8, (0, 0, 0, 0), kinds)
        k_lay.addWidget(text("Jenis kejadian", Type.LABEL))
        self.kind_group = QButtonGroup(self)
        for i, (_, label, desc) in enumerate(MANUAL_KINDS):
            opt = RadioOption(label, desc, i == 0)
            self.kind_group.addButton(opt, i)
            k_lay.addWidget(opt)
        card.add(kinds)

        self.f_note = InputField("Keterangan", "Tulis penyebab dan lama kejadian", "", "edit")
        self.f_note.edit.returnPressed.connect(self._save)
        card.add(self.f_note)
        card.layout_.addStretch(1)

        row = hbox(10)
        cancel = Button("Batal", "outline")
        cancel.clicked.connect(self._reset_form)
        save = Button("Simpan kejadian", "primary", "md", "check")
        save.clicked.connect(self._save)
        for b in (cancel, save):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(b)
        card.layout_.addLayout(row)
        return card

    def _set_form_batch(self, batch: Batch | None) -> None:
        self.form_batch = batch
        self.f_batch.edit.setText(f"{batch.code}, {batch.product}" if batch else "")
        self.f_batch.set_error(None)

    def _reset_form(self) -> None:
        self.f_note.edit.clear()
        self.f_note.set_error(None)
        self.kind_group.button(0).setChecked(True)

    def _save(self) -> None:
        kind = MANUAL_KINDS[self.kind_group.checkedId()][0]
        code = self.form_batch.code if self.form_batch else ""
        result = self._ctrl.record(code, kind, self.f_note.value())
        self.f_batch.set_error(result.errors.get("batch"))
        self.f_note.set_error(result.errors.get("note"))
        if result.event is None:
            return
        self.code = code
        self.batch_btn.setText(f" {code}")
        self.page_index = 0
        self._highlight_first = True
        self._reset_form()
        self._render()
        toast(self._win(), "success", "Kejadian tersimpan",
              f"{kind.replace('_', ' ')} pukul {result.event.time} masuk ke rekap {code}.")
