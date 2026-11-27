from PyQt6.QtWidgets import QSizePolicy

from ...controllers import EventController
from ...controllers.event_controller import MANUAL_KINDS, kind_label
from ...models import Batch
from ..components import (
    AdaptiveRow, Button, Card, DataTable, InputField, Option, TableFooter, bind_select, event_kind, hbox, open_select,
    text, toast, vbox,
)
from ..shell import Page
from ..theme import Color, Type


class KejadianPage(Page):
    def __init__(self, controller: EventController, window_getter):
        super().__init__("Kejadian produksi")
        self._ctrl = controller
        self._win = window_getter
        self.page_index = 0
        self._highlight_first = False
        running = sorted(controller.running_batches(), key=lambda b: b.started_at)
        self.code = self._default_code()  # "" on a fresh database without batches

        self.batch_btn = Button(self.code or "Belum ada batch", "outline", "md", "layers")
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

    def _default_code(self) -> str:
        """The newest running batch, else the newest batch, else "" (no batches yet)."""
        running = sorted(self._ctrl.running_batches(), key=lambda b: b.started_at)
        batches = self._ctrl.batches()
        return running[-1].code if running else (batches[0].code if batches else "")

    def on_show(self) -> None:
        if not self.code or self._ctrl.find_batch(self.code) is None:
            self.code = self._default_code()  # the first batch may have been created meanwhile
            self.batch_btn.setText(f" {self.code or 'Belum ada batch'}")
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
        self.table.set_empty(None if rows else (f"Belum ada kejadian pada batch {self.code}." if self.code
                                                 else "Belum ada batch. Buat batch di halaman Batch."))
        self.footer.update_state(f"Menampilkan {len(shown)} dari {len(rows)} kejadian batch {self.code}. "
                                 "REJECT dicatat otomatis setiap kali AI menyatakan kaleng NG.", self.page_index, pages)

    def _go_page(self, index: int) -> None:
        self.page_index = index
        self._render()

    @staticmethod
    def _batch_options(batches: list) -> list:
        return [Option(b.code, b.code, f"{b.product}, {'berjalan' if b.running else b.start_label}") for b in batches]

    def _batch_menu(self) -> None:
        open_select(self.batch_btn, self._batch_options(self._ctrl.batches()), self.show_batch, self.code,
                    "Cari kode batch atau produk")

    def _pick_form_batch(self, code: str) -> None:
        self._set_form_batch(self._ctrl.find_batch(code))

    def _form(self, batch: Batch | None) -> Card:
        card = Card((22, 22, 22, 22), 18)
        head = vbox(2)
        head.addWidget(text("Catat kejadian", Type.TITLE))
        head.addWidget(text("Kejadian REJECT sudah dicatat otomatis oleh AI", Type.CAPTION, Color.TEXT_TERTIARY))
        card.layout_.addLayout(head)

        self.f_batch = InputField("Batch", "Pilih batch yang sedang berjalan", "", "layers", trailing="dropdown",
                                  helper="Pilih salah satu batch yang sedang berjalan")
        self.f_batch.edit.setReadOnly(True)
        bind_select(self.f_batch, lambda: self._batch_options(self._ctrl.running_batches()), self._pick_form_batch,
                    lambda: self.form_batch.code if self.form_batch else None, "Cari batch yang sedang berjalan")
        card.add(self.f_batch)
        self._set_form_batch(batch)

        self.f_kind = InputField("Jenis kejadian", "Pilih atau ketik jenis kejadian", MANUAL_KINDS[0][1], "activity",
                                 trailing="dropdown", helper="Ketik sendiri jika jenisnya tidak ada di daftar")
        bind_select(self.f_kind, lambda: [Option(label, label, desc) for _, label, desc in self._ctrl.kind_suggestions()],
                    self.f_kind.edit.setText, self.f_kind.value, "Cari atau ketik jenis kejadian", allow_custom=True,
                    on_custom=self.f_kind.edit.setText)
        card.add(self.f_kind)

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
        self.f_kind.edit.setText(MANUAL_KINDS[0][1])
        self.f_kind.set_error(None)

    def _save(self) -> None:
        code = self.form_batch.code if self.form_batch else ""
        result = self._ctrl.record(code, self.f_kind.value(), self.f_note.value())
        self.f_batch.set_error(result.errors.get("batch"))
        self.f_kind.set_error(result.errors.get("kind"))
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
              f"{kind_label(result.event.kind)} pukul {result.event.time} masuk ke rekap {code}.")
