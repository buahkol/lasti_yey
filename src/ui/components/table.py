"""DataTable: header row + clickable rows built from widgets (keeps badges and progress bars inline)."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QSizePolicy, QWidget

from ..theme import TONES, Color, Type
from .base import add_shadow, hbox, text, vbox


class _Row(QFrame):
    clicked = pyqtSignal()

    def __init__(self, header: bool = False):
        super().__init__()
        self.setObjectName("TRow")
        self.header = header
        self.selected = False
        if not header:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style()

    def set_selected(self, on: bool) -> None:
        self.selected = on
        self._style()

    def _style(self) -> None:
        if self.header:
            self.setStyleSheet(f"QFrame#TRow {{ background: {Color.SUBTLE}; border: none; }}")
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
        self._lay = vbox(0, (0, 16 if title else 4, 0, 4), self)
        if title is not None:
            title.layout().setContentsMargins(20, 0, 16, 10)
            self._lay.addWidget(title)
        self._head = _Row(header=True)
        self._fill(self._head, [text(c[0], Type.OVERLINE, Color.TEXT_TERTIARY) for c in columns], 9)
        self._lay.addWidget(self._head)
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
        self._lay.insertWidget(self._lay.indexOf(self._end), row)
        self.rows.append(row)
        return row

    def select(self, index: int) -> None:
        for i, r in enumerate(self.rows):
            r.set_selected(i == index)

    def clear_rows(self) -> None:
        for r in self.rows:
            r.deleteLater()
        self.rows = []

    def add_footer(self, widget: QWidget) -> None:
        self._lay.addWidget(widget)


def two_line(primary: str, secondary: str, strong: bool = True) -> QWidget:
    w = QWidget()
    lay = vbox(1, (0, 0, 0, 0), w)
    lay.addWidget(text(primary, Type.BODY_STRONG if strong else Type.BODY))
    lay.addWidget(text(secondary, Type.CAPTION, Color.TEXT_TERTIARY))
    return w
