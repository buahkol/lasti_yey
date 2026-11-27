"""Pop-ups shared by several pages: photo viewer and close-batch confirmation."""

import os
from datetime import date, timedelta

from PyQt6.QtWidgets import QFileDialog, QFrame, QLabel, QSizePolicy, QWidget

from .. import formatting as fmt
from ..assets import pixmap
from ..components import (
    Badge, Button, CanPhoto, Checkbox, IconButton, InputField, ModalCard, Option, Overlay, ProgressBar, RadioOption,
    add_shadow, bind_select, hbox, show_status, text, toast, vbox,
)
from ...models import Alert
from ...reports import batch_report_pdf, date_recap_pdf
from ..theme import TONES, Color, Type


def open_photo_viewer(window: QWidget, alert: Alert, show_folder: bool = True) -> Overlay:
    """Full photo of one inspected can (OK or NG) with score details (FR-23, FR-31)."""
    batch, time, score, threshold, defect = alert.batch, alert.time, alert.score, alert.threshold, alert.defect
    product = alert.product
    card = QFrame()
    card.setObjectName("Viewer")
    card.setStyleSheet("QFrame#Viewer { background: #FFFFFF; border-radius: 24px; }")
    add_shadow(card, "pop")
    lay = hbox(0, (0, 0, 0, 0), card)

    left = QFrame()
    left.setObjectName("ViewerLeft")
    left.setStyleSheet(f"QFrame#ViewerLeft {{ background: {Color.BRAND_STRONG}; border-top-left-radius: 24px;"
                       " border-bottom-left-radius: 24px; }")
    l_lay = vbox(12, (20, 20, 20, 20), left)
    photo = CanPhoto(defect, (16, 16, 16, 16), inspection_id=alert.inspection_id)
    photo.setFixedSize(720, 510)
    l_lay.addWidget(photo)
    row = hbox(8)
    if alert.inspection_id and photo.has_real_photo():
        caption = "Foto dari kamera inspeksi" + (", skor di atas ambang" if alert.result == "NG" else ", lolos inspeksi")
    else:
        caption = ("Lingkaran menandai area skor anomali tertinggi" if alert.result == "NG"
                   else "Kaleng lolos inspeksi")
    row.addWidget(text(caption, Type.CAPTION, "rgba(255,255,255,0.6)"))
    row.addStretch(1)
    row.addWidget(text("640 x 480 piksel, ESP32-S3 + OV5640", Type.CAPTION, "rgba(255,255,255,0.6)"))
    l_lay.addLayout(row)
    lay.addWidget(left)

    right = vbox(16, (24, 24, 24, 24))
    top = hbox(8)
    is_ng = alert.result == "NG"
    top.addWidget(Badge(alert.result))
    top.addStretch(1)
    close = IconButton("x", "Tutup", "soft")
    top.addWidget(close)
    right.addLayout(top)
    head = vbox(2)
    head.addWidget(text(batch, Type.DISPLAY))
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    when = (f"{alert.timestamp.day} {months[alert.timestamp.month - 1]} {alert.timestamp.year}, pukul {time}"
            if alert.timestamp else f"Pukul {time}")
    if alert.inspection_id:
        when = f"Inspeksi nomor {alert.inspection_id}, {when}"
    head.addWidget(text(when, Type.CAPTION, Color.TEXT_TERTIARY))
    right.addLayout(head)
    score_box = QFrame()
    score_box.setObjectName("Score")
    score_box.setStyleSheet(
        "QFrame#Score { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(168,233,236,0.28),"
        f" stop:0.55 rgba(244,179,205,0.16), stop:1 #FFFFFF); border: 1px solid {Color.BORDER}; border-radius: 16px; }}"
    )
    sb = vbox(0, (16, 14, 16, 14), score_box)
    gap = score - threshold
    thr = fmt.threshold(threshold)
    gap_text = (f"Melewati ambang {thr} sebesar {fmt.threshold(gap)}" if is_ng
                else f"Di bawah ambang {thr} sebesar {fmt.threshold(-gap)}")
    bar = ProgressBar("Skor anomali", f"{score:.2f}".replace(".", ","), score, "pink" if is_ng else "indigo",
                      "dari 1,00", gap_text)
    bar.set_value_size(19)
    sb.addWidget(bar)
    right.addWidget(score_box)
    info = vbox(0)
    for k, v in (("Produk", product), ("Ambang batas", thr),
                 ("Versi model", alert.model_version or "-"), ("Kejadian", "REJECT oleh AI" if is_ng else "Tidak ada"),
                 ("LED reject", "Menyala 2 detik" if is_ng else "Tidak menyala")):
        r = QFrame()
        r.setObjectName("KV")
        r.setStyleSheet(f"QFrame#KV {{ border: none; border-bottom: 1px solid {Color.BORDER}; }}")
        rl = hbox(8, (0, 10, 0, 10), r)
        rl.addWidget(text(k, Type.BODY, Color.TEXT_SECONDARY), 1)
        rl.addWidget(text(v, Type.BODY_STRONG))
        info.addWidget(r)
    right.addLayout(info)
    right.addStretch(1)
    folder = Button("Buka folder foto batch" if show_folder else "Tutup", "outline", "md",
                    "folder" if show_folder else None)
    folder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    right.addWidget(folder)
    holder = QWidget()
    holder.setFixedWidth(380)
    holder.setLayout(right)
    lay.addWidget(holder)

    overlay = Overlay(window, card).open()
    close.clicked.connect(overlay.close_overlay)
    if show_folder:
        folder.clicked.connect(lambda: (overlay.close_overlay(), window.open_batch("riwayat", batch)))
    else:
        folder.clicked.connect(overlay.close_overlay)
    return overlay


def confirm_close_batch(window: QWidget, code: str, on_closed=None) -> None:
    """Confirmation before closing a batch (FR-06)."""

    def done():
        toast(window, "success", f"Batch {code} ditutup",
              "Status akhir dihitung dari persentase NG terhadap batas toleransi.")
        if on_closed:
            on_closed()

    show_status(window, "confirm", f"Tutup batch {code}?",
                "Batch yang ditutup tidak lagi menerima data inspeksi. Status akhir ditentukan dari persentase NG.",
                [("Batal", "outline", None), ("Tutup batch", "danger", done)])



_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
_BATCH_PARTS = [("summary", "Ringkasan OK, NG, persentase NG, dan status", True),
                ("chart", "Grafik dan tabel sebaran NG per jam", True),
                ("loss", "Estimasi kerugian", True),
                ("events", "Daftar kejadian produksi", True),
                ("top_scores", "Skor NG tertinggi (tanpa foto)", False)]
_RECAP_PARTS = [("summary", "Ringkasan OK, NG, persentase NG, dan status batch", True),
                ("chart", "Grafik output per hari", True),
                ("loss", "Estimasi kerugian", True),
                ("table", "Tabel rekap per batch", True)]


def _default_folder() -> str:
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    return downloads if os.path.isdir(downloads) else os.path.expanduser("~")


def ask_save_path(window: QWidget, suggested: str) -> str:
    """Ask where to save the PDF. Returns an empty string when cancelled."""
    path, _ = QFileDialog.getSaveFileName(window, "Simpan laporan PDF", os.path.join(_default_folder(), suggested),
                                          "Dokumen PDF (*.pdf)")
    if path and not path.lower().endswith(".pdf"):
        path += ".pdf"
    return path


def _range_label(start: date, end: date) -> str:
    if start == end:
        return f"{start.day} {_MONTHS_SHORT[start.month - 1]} {start.year}"
    return f"{start.day} {_MONTHS_SHORT[start.month - 1]} sampai {end.day} {_MONTHS_SHORT[end.month - 1]} {end.year}"


def open_export_pdf(window: QWidget, reports, batch_code: str | None = None, start: date | None = None,
                    end: date | None = None, per_date: bool = False) -> Overlay:
    """Export the batch inspection report or the production recap as a PDF (FR-21, FR-25).

    reports is the ReportController; the PDF itself is written by src/reports/pdf_export.py.
    Photos are never included in the report.
    """
    batches = reports.batches()
    by_code = {b.code: b for b in batches}
    code = batch_code if batch_code in by_code else (batches[0].code if batches else "")
    today = reports.today()
    start = start or today - timedelta(days=2)
    end = end or today
    state = {"code": code, "per_date": per_date}

    card = ModalCard(560)
    holder: dict = {}
    card.header("file", "Ekspor laporan PDF", "Pilih jenis laporan dan isi yang akan dicetak",
                lambda: holder["o"].close_overlay())
    card.body.addWidget(text("Jenis laporan", Type.OVERLINE, Color.TEXT_TERTIARY))
    radios = hbox(10)
    r1 = RadioOption("Inspeksi batch", "Hasil satu batch, grafik NG per jam", not per_date)
    r2 = RadioOption("Rekap per tanggal", "Semua batch dalam rentang tanggal", per_date)
    radios.addWidget(r1, 1)
    radios.addWidget(r2, 1)
    card.body.addLayout(radios)

    batch = InputField("Batch", "", "", "layers", trailing="dropdown")
    batch.edit.setReadOnly(True)

    def batch_text(c: str) -> str:
        b = by_code.get(c)
        return f"{c}, {b.product}" if b else c

    batch.edit.setText(batch_text(code))

    def pick(c):
        state["code"] = c
        batch.edit.setText(batch_text(c))
        batch.set_error(None)
        refresh()

    bind_select(batch, lambda: [Option(b.code, b.code, f"{b.product}, {b.start_label}") for b in batches], pick,
                lambda: state["code"], "Cari kode batch atau produk")
    card.body.addWidget(batch)
    period = InputField("Rentang tanggal", "", _range_label(start, end), "calendar",
                        helper="Ubah rentang dari pemilih tanggal di halaman Laporan atau Batch")
    period.edit.setReadOnly(True)
    card.body.addWidget(period)

    card.body.addWidget(text("Isi laporan", Type.OVERLINE, Color.TEXT_TERTIARY))
    boxes = {}
    for mode, parts in (("batch", _BATCH_PARTS), ("recap", _RECAP_PARTS)):
        box = QFrame()
        box.setObjectName("Checks")
        box.setStyleSheet(f"QFrame#Checks {{ background: {Color.SUBTLE}; border: 1px solid {Color.BORDER};"
                          " border-radius: 14px; }")
        b_lay = vbox(10, (14, 14, 14, 14), box)
        checks = {}
        for key, label, on in parts:
            checks[key] = Checkbox(label, on)
            b_lay.addWidget(checks[key])
        boxes[mode] = (box, checks)
        card.body.addWidget(box)

    t = TONES["indigo"]
    file_row = QFrame()
    file_row.setObjectName("File")
    file_row.setStyleSheet(f"QFrame#File {{ background: {t.soft}; border-radius: 12px; }}")
    f_lay = hbox(10, (12, 10, 12, 10), file_row)
    f_lay.addWidget(_pix_label(pixmap("file", t.ink, 18)))
    col = vbox(0)
    file_name = text("", Type.BODY_STRONG, t.ink)
    col.addWidget(file_name)
    col.addWidget(text("PDF ukuran A4, tanpa foto kaleng", Type.CAPTION, t.ink))
    f_lay.addLayout(col, 1)
    card.body.addWidget(file_row)

    def suggested_name() -> str:
        if state["per_date"]:
            tag = f"{start:%d}{_MONTHS_SHORT[start.month - 1]}" + ("" if start == end else
                                                                    f"-{end:%d}{_MONTHS_SHORT[end.month - 1]}")
            return f"Rekap_Produksi_{tag}{end.year}.pdf"
        return f"Laporan_Inspeksi_{state['code']}.pdf"

    def refresh():
        per = state["per_date"]
        batch.setVisible(not per)
        period.setVisible(per)
        boxes["batch"][0].setVisible(not per)
        boxes["recap"][0].setVisible(per)
        file_name.setText(suggested_name())
        card.adjustSize()
        if "o" in holder:
            holder["o"]._center()

    def switch(per_batch: bool):
        state["per_date"] = not per_batch
        refresh()

    r1.toggled.connect(switch)
    row = hbox(10)
    cancel = Button("Batal", "outline")
    export = Button("Ekspor PDF", "primary", "md", "download")
    for b in (cancel, export):
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(b)
    card.body.addLayout(row)
    refresh()
    holder["o"] = Overlay(window, card).open()
    cancel.clicked.connect(holder["o"].close_overlay)

    def do_export():
        per = state["per_date"]
        checks = boxes["recap" if per else "batch"][1]
        sections = tuple(k for k, c in checks.items() if c.isChecked())
        if not sections:
            toast(window, "error", "Isi laporan kosong", "Centang minimal satu bagian yang akan dicetak.")
            return
        report = None if per else reports.batch_report(state["code"])
        if not per and report is None:
            batch.set_error("Data inspeksi batch ini belum tersedia. Pilih batch lain.")
            refresh()
            return
        path = ask_save_path(window, suggested_name())
        if not path:
            return
        user = getattr(window, "user", None)
        printed_by = user.name if user else "Operasional"
        try:
            if per:
                date_recap_pdf(path, reports.date_recap(start, end), sections, printed_by)
            else:
                batch_report_pdf(path, report, sections, printed_by)
        except OSError as e:
            toast(window, "error", "PDF gagal disimpan", f"File tidak dapat ditulis: {e.strerror or e}.")
            return
        holder["o"].close_overlay()
        toast(window, "success", "PDF berhasil disimpan", f"{os.path.basename(path)} tersimpan di "
                                                          f"{os.path.dirname(path)}.")

    export.clicked.connect(do_export)
    return holder["o"]


def _pix_label(pm) -> QWidget:
    lab = QLabel()
    lab.setPixmap(pm)
    lab.setStyleSheet("background: transparent;")
    return lab
