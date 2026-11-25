"""Pop-ups shared by several pages: photo viewer and close-batch confirmation."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QWidget

from ..assets import pixmap
from ..components import (
    Badge, Button, CanPhoto, Checkbox, IconButton, InputField, ModalCard, Overlay, ProgressBar, RadioOption,
    add_shadow, hbox, show_status, text, toast, vbox,
)
from ..theme import TONES, Color, Type, font


def open_photo_viewer(window: QWidget, alert: tuple, product: str = "Sarden saus tomat 155 g") -> Overlay:
    """Full photo of one NG can with score details (FR-23)."""
    batch, time, score, threshold, defect = alert
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
    photo = CanPhoto(defect, (16, 16, 16, 16))
    photo.setFixedSize(720, 510)
    l_lay.addWidget(photo)
    row = hbox(8)
    seg = QFrame()
    seg.setObjectName("Seg")
    seg.setStyleSheet("QFrame#Seg { background: #22394D; border-radius: 18px; }")
    s_lay = hbox(2, (3, 3, 3, 3), seg)
    btns = []
    for label, on in (("Foto asli", False), ("Peta anomali", True)):
        b = QPushButton(label)
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setChecked(on)
        b.setFont(font(Type.LABEL))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("QPushButton { color: rgba(255,255,255,0.7); background: transparent; border: none;"
                        " border-radius: 15px; padding: 6px 12px; }"
                        f"QPushButton:checked {{ background: #FFFFFF; color: {Color.TEXT_PRIMARY}; }}")
        s_lay.addWidget(b)
        btns.append(b)
    btns[0].toggled.connect(lambda on: photo.set_heatmap(not on))
    row.addWidget(seg)
    row.addStretch(1)
    row.addWidget(text("640 x 480 piksel, ESP32-CAM", Type.CAPTION, "rgba(255,255,255,0.6)"))
    l_lay.addLayout(row)
    lay.addWidget(left)

    right = vbox(16, (24, 24, 24, 24))
    top = hbox(8)
    top.addWidget(Badge("NG"))
    top.addStretch(1)
    close = IconButton("x", "Tutup", "soft")
    top.addWidget(close)
    right.addLayout(top)
    head = vbox(2)
    head.addWidget(text(batch, Type.DISPLAY))
    head.addWidget(text(f"Inspeksi nomor 412, pukul {time}", Type.CAPTION, Color.TEXT_TERTIARY))
    right.addLayout(head)
    score_box = QFrame()
    score_box.setObjectName("Score")
    score_box.setStyleSheet(
        "QFrame#Score { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(168,233,236,0.28),"
        f" stop:0.55 rgba(244,179,205,0.16), stop:1 #FFFFFF); border: 1px solid {Color.BORDER}; border-radius: 16px; }}"
    )
    sb = vbox(0, (16, 14, 16, 14), score_box)
    gap = score - threshold
    bar = ProgressBar("Skor anomali", f"{score:.2f}".replace(".", ","), score, "pink", "dari 1,00",
                      f"Melewati ambang {threshold:.2f} sebesar {gap:.2f}".replace(".", ","))
    bar.set_value_size(22)
    sb.addWidget(bar)
    right.addWidget(score_box)
    info = vbox(0)
    for k, v in (("Produk", product), ("Ambang batas", f"{threshold:.2f}".replace(".", ",")),
                 ("Versi model", "pc-v2.1"), ("Kejadian", "REJECT oleh AI"), ("LED reject", "Menyala 2 detik")):
        r = QFrame()
        r.setObjectName("KV")
        r.setStyleSheet(f"QFrame#KV {{ border: none; border-bottom: 1px solid {Color.BORDER}; }}")
        rl = hbox(8, (0, 10, 0, 10), r)
        rl.addWidget(text(k, Type.BODY, Color.TEXT_SECONDARY), 1)
        rl.addWidget(text(v, Type.BODY_STRONG))
        info.addWidget(r)
    right.addLayout(info)
    right.addStretch(1)
    nav = hbox(8)
    nav.addWidget(IconButton("chevron-left", "Alert sebelumnya", "outline", 44))
    nav.addWidget(IconButton("chevron-right", "Alert berikutnya", "outline", 44))
    hist = Button("Buka riwayat batch", "primary", "md", "history")
    hist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    nav.addWidget(hist)
    right.addLayout(nav)
    holder = QWidget()
    holder.setFixedWidth(380)
    holder.setLayout(right)
    lay.addWidget(holder)

    overlay = Overlay(window, card).open()
    close.clicked.connect(overlay.close_overlay)
    hist.clicked.connect(lambda: (overlay.close_overlay(),
                                  toast(window, "info", "Riwayat dan klaim", "Halaman ini dikerjakan pada Desktop P2.")))
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



def open_export_pdf(window: QWidget, batch_code: str = "B-2411-02", product: str = "Sarden saus cabai 155 g",
                    date_label: str = "25Nov2026") -> Overlay:
    """Export dialog for the batch inspection report or the production recap (FR-21, FR-25)."""

    card = ModalCard(560)
    holder: dict = {}
    card.header("file", "Ekspor laporan PDF", "Pilih jenis laporan dan isi yang akan dicetak",
                lambda: holder["o"].close_overlay())
    card.body.addWidget(text("Jenis laporan", Type.OVERLINE, Color.TEXT_TERTIARY))
    radios = hbox(10)
    r1 = RadioOption("Inspeksi batch", "Ringkasan OK dan NG, grafik NG per jam, estimasi kerugian", True)
    r2 = RadioOption("Rekap per tanggal", "Output, OK, NG, dan kejadian dalam rentang tanggal")
    radios.addWidget(r1, 1)
    radios.addWidget(r2, 1)
    card.body.addLayout(radios)
    batch = InputField("Batch", "", f"{batch_code}, {product}", "layers", trailing="dropdown")
    card.body.addWidget(batch)
    card.body.addWidget(text("Isi laporan", Type.OVERLINE, Color.TEXT_TERTIARY))
    box = QFrame()
    box.setObjectName("Checks")
    box.setStyleSheet(f"QFrame#Checks {{ background: {Color.SUBTLE}; border: 1px solid {Color.BORDER}; border-radius: 14px; }}")
    b_lay = vbox(10, (14, 14, 14, 14), box)
    for label, on in (("Ringkasan OK, NG, dan persentase NG", True), ("Grafik sebaran NG per jam", True),
                      ("Estimasi kerugian", True), ("Foto kaleng NG dengan skor tertinggi", True),
                      ("Daftar kejadian produksi", False)):
        b_lay.addWidget(Checkbox(label, on))
    card.body.addWidget(box)
    t = TONES["indigo"]
    file_row = QFrame()
    file_row.setObjectName("File")
    file_row.setStyleSheet(f"QFrame#File {{ background: {t.soft}; border-radius: 12px; }}")
    f_lay = hbox(10, (12, 10, 12, 10), file_row)
    f_lay.addWidget(_pix_label(pixmap("file", t.ink, 18)))
    col = vbox(0)
    file_name = text(f"Laporan_{batch_code}_{date_label}.pdf", Type.BODY_STRONG, t.ink)
    col.addWidget(file_name)
    col.addWidget(text("3 halaman, sekitar 1,2 MB", Type.CAPTION, t.ink))
    f_lay.addLayout(col, 1)
    card.body.addWidget(file_row)

    def switch(per_batch: bool):
        batch.setVisible(per_batch)
        file_name.setText(f"Laporan_{batch_code}_{date_label}.pdf" if per_batch else f"Rekap_Produksi_{date_label}.pdf")
        card.adjustSize()
        holder["o"]._center()

    r1.toggled.connect(lambda on: switch(on))
    row = hbox(10)
    cancel = Button("Batal", "outline")
    export = Button("Ekspor PDF", "primary", "md", "download")
    for b in (cancel, export):
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(b)
    card.body.addLayout(row)
    holder["o"] = Overlay(window, card).open()
    cancel.clicked.connect(holder["o"].close_overlay)

    def do_export():
        name = file_name.text()
        holder["o"].close_overlay()
        toast(window, "success", "PDF berhasil disimpan", f"{name} tersimpan di folder Unduhan.")

    export.clicked.connect(do_export)
    return holder["o"]


def _pix_label(pm) -> QWidget:
    lab = QLabel()
    lab.setPixmap(pm)
    lab.setStyleSheet("background: transparent;")
    return lab
