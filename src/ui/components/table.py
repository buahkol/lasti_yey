"""DataTable: header row + clickable rows built from widgets (keeps badges and progress bars inline)."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QSizePolicy, QWidget

from ..theme import TONES, Color, Radius, Type
from .base import add_shadow, hbox, text, vbox
from .buttons import IconButton


class _Row(QFrame):
    clicked = pyqtSignal()

    def __init__(self, header: bool = False, round_top: bool = False):
        super().__init__()
        self.setObjectName("TRow")
        self.header = header
        self.round_top = round_top
        self.selected = False
        if not header:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style()

    def set_selected(self, on: bool) -> None:
        self.selected = on
        self._style()

    def _style(self) -> None:
        if self.header:
            radius = f"border-top-left-radius: {Radius.CARD}px; border-top-right-radius: {Radius.CARD}px;" \
                if self.round_top else ""
            self.setStyleSheet(f"QFrame#TRow {{ background: {Color.SUBTLE}; border: none; {radius} }}")
            return
        bg = "rgba(238,239,253,0.7)" if self.selected else "transparent"
        self.setStyleSheet(
            f"QFrame#TRow {{ background: {bg}; border: none; border-top: 1px solid {Color.BORDER}; }}"
            f"QFrame#TRow:hover {{ background: {TONES['blue'].soft}; }}"
        )

    def mouseReleaseEvent(self, e):  # noqa: N802
        if not self.header:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class DataTable(QFrame):
    """Table whose columns share the width by weight, so every row lines up and gaps stay even.

    columns: list of (title, weight, align L | R | F (fill), optional right padding,
    optional hide_below). A weight of None counts as 2. Weights are relative,
    for example 3 for a product name and 1 for a short number. A column with
    hide_below is hidden while the table is narrower than that many pixels.
    """

    row_clicked = pyqtSignal(int)

    def __init__(self, columns: list, title: QWidget | None = None, row_padding: int = 10):
        super().__init__()
        self.setObjectName("Card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        add_shadow(self)
        self.columns = columns
        self.row_padding = row_padding
        self.rows: list = []
        self._lay = vbox(0, (0, 16 if title else 0, 0, 4), self)
        if title is not None:
            title.layout().setContentsMargins(20, 0, 16, 10)
            self._lay.addWidget(title)
        self._head = _Row(header=True, round_top=title is None)
        self._fill(self._head, [text(c[0], Type.LABEL, Color.TEXT_TERTIARY) for c in columns], 9)
        self._lay.addWidget(self._head)
        self._empty = text("", Type.BODY, Color.TEXT_TERTIARY)
        self._empty.setContentsMargins(20, 18, 16, 18)
        self._empty.hide()
        self._lay.addWidget(self._empty)
        self._end = QWidget()
        self._lay.addWidget(self._end, 1)

    def _fill(self, row: _Row, cells: list, pad: int) -> None:
        lay = hbox(0, (20, pad, 16, pad), row)
        row.boxes = []
        for (title, weight, align, *rest), cell in zip(self.columns, cells):
            box = QWidget()
            box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            right_pad = rest[0] if rest and rest[0] is not None else (24 if align == "R" else 16)
            row.boxes.append(box)
            b_lay = hbox(8, (0, 0, right_pad, 0), box)
            if isinstance(cell, str):
                cell = text(cell, Type.BODY)
            if align == "R":
                b_lay.addStretch(1)
                b_lay.addWidget(cell)
            elif align == "F" and not row.header:
                b_lay.addWidget(cell, 1)
            else:
                b_lay.addWidget(cell)
                b_lay.addStretch(1)
            lay.addWidget(box, weight or 2)
        self._apply_hidden(row)

    def _apply_hidden(self, row: _Row) -> None:
        width = self.width()
        for col, box in zip(self.columns, row.boxes):
            hide_below = col[4] if len(col) > 4 else None
            box.setVisible(not (hide_below and width < hide_below))

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        for row in [self._head] + self.rows:
            self._apply_hidden(row)

    def add_row(self, cells: list, selected: bool = False) -> _Row:
        row = _Row()
        self._fill(row, cells, self.row_padding)
        self._apply_hidden(row)
        row.set_selected(selected)
        idx = len(self.rows)
        row.clicked.connect(lambda: self.row_clicked.emit(idx))
        self._lay.insertWidget(self._lay.indexOf(self._empty), row)
        self.rows.append(row)
        return row

    def select(self, index: int) -> None:
        for i, r in enumerate(self.rows):
            r.set_selected(i == index)

    def clear_rows(self) -> None:
        for r in self.rows:
            r.deleteLater()
        self.rows = []

    def set_empty(self, message: str | None) -> None:
        self._empty.setText(message or "")
        self._empty.setVisible(bool(message))

    def add_footer(self, widget: QWidget) -> None:
        self._lay.addWidget(widget)


def two_line(primary: str, secondary: str, strong: bool = True) -> QWidget:
    w = QWidget()
    lay = vbox(1, (0, 0, 0, 0), w)
    lay.addWidget(text(primary, Type.BODY_STRONG if strong else Type.BODY))
    lay.addWidget(text(secondary, Type.CAPTION, Color.TEXT_TERTIARY))
    return w


class TableFooter(QFrame):
    page_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("Foot")
        self.setStyleSheet(f"QFrame#Foot {{ border: none; border-top: 1px solid {Color.BORDER}; }}")
        lay = hbox(6, (20, 10, 16, 10), self)
        self.caption = text("", Type.CAPTION, Color.TEXT_TERTIARY)
        self.caption.setWordWrap(True)
        lay.addWidget(self.caption, 1)
        self.prev = IconButton("chevron-left", "Halaman sebelumnya", "outline", 36)
        self.next = IconButton("chevron-right", "Halaman berikutnya", "outline", 36)
        lay.addWidget(self.prev)
        lay.addWidget(self.next)
        self.index = 0
        self.prev.clicked.connect(lambda: self.page_changed.emit(self.index - 1))
        self.next.clicked.connect(lambda: self.page_changed.emit(self.index + 1))

    def update_state(self, caption: str, index: int, pages: int) -> None:
        self.caption.setText(caption)
        self.index = index
        self.prev.setEnabled(index > 0)
        self.next.setEnabled(index < pages - 1)
        self.prev.setVisible(pages > 1)
        self.next.setVisible(pages > 1)
