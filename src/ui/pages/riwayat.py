"""Riwayat (FR-30, FR-31): the photo of every inspected can, OK and NG, as one folder per batch.

The page opens on a grid of batch folders. Clicking a folder shows its photos,
filtered by OK or NG and split into pages; clicking a photo opens the viewer.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QStackedWidget, QWidget

from ...controllers import HistoryController, PhotoFolder
from ...controllers.history_controller import FILTERS, PAGE_SIZE
from ..assets import pixmap
from ..components import (
    Badge, Button, CanPhoto, DefectCard, IconButton, ResponsiveGrid, SearchField, SegmentedTabs, hbox, text, vbox,
)
from ..shell import Page
from ..theme import Color, Type
from .common import open_photo_viewer

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _num(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _date(dt) -> str:
    return f"{dt.day} {_MONTHS[dt.month - 1]} {dt.year}"


class _FolderCard(QFrame):
    """One batch folder: a preview of the latest photos, batch code, product, date and OK/NG counts."""

    clicked = pyqtSignal(str)

    def __init__(self, folder: PhotoFolder):
        super().__init__()
        self.code = folder.batch.code
        self.setObjectName("Folder")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style(False)
        lay = vbox(12, (12, 12, 12, 14), self)

        preview = QFrame()
        preview.setObjectName("Preview")
        preview.setFixedHeight(128)
        preview.setStyleSheet(f"QFrame#Preview {{ background: {Color.SUBTLE}; border-radius: 14px; }}")
        p_lay = hbox(6, (6, 6, 6, 6), preview)
        shown = folder.preview[:3]
        if shown:
            for a in shown:
                photo = CanPhoto(a.defect, (10, 10, 10, 10), inspection_id=a.inspection_id)
                photo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                p_lay.addWidget(photo, 1)
            for _ in range(3 - len(shown)):
                p_lay.addStretch(1)
        else:
            empty = vbox(6)
            empty.addStretch(1)
            ic = QLabel()
            ic.setPixmap(pixmap("folder", Color.TEXT_TERTIARY, 28))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.addWidget(ic)
            empty.addWidget(text("Belum ada foto", Type.CAPTION, Color.TEXT_TERTIARY,
                                 align=Qt.AlignmentFlag.AlignCenter))
            empty.addStretch(1)
            p_lay.addLayout(empty, 1)
        lay.addWidget(preview)

        head = hbox(8, (4, 0, 4, 0))
        ic = QLabel()
        ic.setPixmap(pixmap("folder", Color.PRIMARY, 18))
        head.addWidget(ic)
        head.addWidget(text(folder.batch.code, Type.HEADING), 1)
        b = folder.batch
        head.addWidget(Badge(b.status if b.running else b.inspection))
        lay.addLayout(head)
        meta = vbox(2, (4, 0, 4, 0))
        meta.addWidget(text(b.product, Type.BODY, Color.TEXT_SECONDARY))
        meta.addWidget(text(f"{_date(b.started_at)}, {_num(folder.count)} foto ({_num(folder.ok)} OK, "
                            f"{_num(folder.ng)} NG)", Type.CAPTION, Color.TEXT_TERTIARY))
        lay.addLayout(meta)

    def _style(self, hover: bool) -> None:
        border = Color.BORDER_STRONG if hover else Color.BORDER
        self.setStyleSheet(f"QFrame#Folder {{ background: {Color.SURFACE}; border: 1px solid {border};"
                           " border-radius: 18px; }")

    def enterEvent(self, e):  # noqa: N802
        self._style(True)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        self._style(False)
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.code)
        super().mouseReleaseEvent(e)


class RiwayatPage(Page):
    def __init__(self, controller: HistoryController, window_getter):
        super().__init__("Riwayat")
        self._ctrl = controller
        self._win = window_getter
        self.code: str | None = None
        self.filter = None
        self.page_index = 0

        self.search = SearchField("Cari kode batch atau produk", 280)
        self.search.edit.textChanged.connect(lambda _: self._render_folders())
        self.actions.addWidget(self.search)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self.body.addWidget(self.stack, 1)

        # folder list -----------------------------------------------------
        self.list_view = QWidget()
        l_lay = vbox(12, (0, 0, 0, 0), self.list_view)
        self.list_caption = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        l_lay.addWidget(self.list_caption)
        self.folder_grid = ResponsiveGrid(260, 4, 16, steps=(4, 3, 2, 1))
        l_lay.addWidget(self.folder_grid)
        self.list_empty = text("", Type.BODY, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignCenter)
        self.list_empty.setContentsMargins(0, 48, 0, 48)
        l_lay.addWidget(self.list_empty)
        l_lay.addStretch(1)
        self.stack.addWidget(self.list_view)

        # inside a folder ---------------------------------------------------
        self.folder_view = QWidget()
        f_lay = vbox(14, (0, 0, 0, 0), self.folder_view)
        crumb = hbox(10)
        back = Button("Semua folder", "outline", "sm", "chevron-left")
        back.clicked.connect(self.show_folders)
        crumb.addWidget(back)
        ic = QLabel()
        ic.setPixmap(pixmap("folder", Color.PRIMARY, 20))
        crumb.addWidget(ic)
        self.folder_title = text("", Type.TITLE)
        crumb.addWidget(self.folder_title)
        self.folder_badge = QWidget()
        self.folder_badge_lay = hbox(0, (0, 0, 0, 0), self.folder_badge)
        crumb.addWidget(self.folder_badge)
        crumb.addStretch(1)
        f_lay.addLayout(crumb)
        self.folder_caption = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        f_lay.addWidget(self.folder_caption)
        bar = hbox(12)
        self.tabs = SegmentedTabs([(label, "0") for label, _ in FILTERS])
        self.tabs.changed.connect(self._set_filter)
        bar.addWidget(self.tabs)
        bar.addStretch(1)
        self.page_label = text("", Type.CAPTION, Color.TEXT_SECONDARY)
        bar.addWidget(self.page_label)
        self.prev_btn = IconButton("chevron-left", "Halaman sebelumnya", "outline", 36)
        self.prev_btn.clicked.connect(lambda: self._go_page(self.page_index - 1))
        bar.addWidget(self.prev_btn)
        self.next_btn = IconButton("chevron-right", "Halaman berikutnya", "outline", 36)
        self.next_btn.clicked.connect(lambda: self._go_page(self.page_index + 1))
        bar.addWidget(self.next_btn)
        f_lay.addLayout(bar)
        self.photo_grid = ResponsiveGrid(220, 5, 16, steps=(5, 4, 3, 2, 1))
        f_lay.addWidget(self.photo_grid)
        self.folder_empty = text("Belum ada foto untuk filter ini.", Type.BODY, Color.TEXT_TERTIARY,
                                 align=Qt.AlignmentFlag.AlignCenter)
        self.folder_empty.setContentsMargins(0, 48, 0, 48)
        f_lay.addWidget(self.folder_empty)
        f_lay.addStretch(1)
        self.stack.addWidget(self.folder_view)

        self._render_folders()

    def on_show(self) -> None:
        if self.code:
            self.show_batch(self.code)
        else:
            self._render_folders()

    # folder list ---------------------------------------------------------
    def show_folders(self) -> None:
        self.code = None
        self.search.setVisible(True)
        self._render_folders()
        self.stack.setCurrentIndex(0)

    def _render_folders(self) -> None:
        query = self.search.edit.text()
        folders = self._ctrl.folders(query)
        self.folder_grid.clear()
        for f in folders:
            card = _FolderCard(f)
            card.clicked.connect(self.show_batch)
            self.folder_grid.add(card)
        photos = sum(f.count for f in folders)
        self.list_caption.setText(f"{len(folders)} folder batch, {_num(photos)} foto kaleng OK dan NG. Foto disimpan "
                                  "tanpa batas waktu untuk menelusuri batch saat ada keluhan.")
        self.list_empty.setVisible(not folders)
        self.list_empty.setText(f"Tidak ada batch yang cocok dengan “{query.strip()}”.")

    # inside a folder -------------------------------------------------------
    def show_batch(self, code: str) -> None:
        """Open the photo folder of one batch, for example from the photo viewer."""
        folder = self._ctrl.folder(code)
        if folder is None:
            self.show_folders()
            return
        if folder.batch.code != self.code:
            self.filter, self.page_index = None, 0
            self.tabs.set_current(0)
        self.code = folder.batch.code
        self.search.setVisible(False)
        b = folder.batch
        self.folder_title.setText(b.code)
        while self.folder_badge_lay.count():
            w = self.folder_badge_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.folder_badge_lay.addWidget(Badge(b.status if b.running else b.inspection))
        self.folder_caption.setText(f"{b.product} ({b.sku}), dimulai {_date(b.started_at)} pukul "
                                    f"{b.started_at:%H.%M}. Foto setiap kaleng yang diperiksa, terbaru di atas.")
        self.tabs.set_counts([_num(n) for n in self._ctrl.counts(b.code)])
        self._render_photos()
        self.stack.setCurrentIndex(1)

    def _set_filter(self, index: int) -> None:
        self.filter = FILTERS[index][1]
        self.page_index = 0
        self._render_photos()

    def _go_page(self, index: int) -> None:
        self.page_index = index
        self._render_photos()

    def _render_photos(self) -> None:
        photos, pages, total = self._ctrl.photos(self.code, self.filter, self.page_index)
        self.page_index = max(0, min(self.page_index, pages - 1))
        self.photo_grid.clear()
        for a in photos:
            card = DefectCard(a.batch, f"{a.timestamp.day} {_MONTHS[a.timestamp.month - 1]}, {a.time}", a.score,
                              a.threshold, a.defect, result=a.result, inspection_id=a.inspection_id)
            card.clicked.connect(lambda al=a: open_photo_viewer(self._win(), al, show_folder=False))
            self.photo_grid.add(card)
        self.folder_empty.setVisible(not photos)
        first = self.page_index * PAGE_SIZE + 1 if photos else 0
        self.page_label.setText(f"{_num(first)} sampai {_num(first + len(photos) - 1 if photos else 0)} "
                                f"dari {_num(total)} foto")
        self.prev_btn.setEnabled(self.page_index > 0)
        self.next_btn.setEnabled(self.page_index < pages - 1)
