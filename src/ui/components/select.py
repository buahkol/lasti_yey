"""Searchable dropdown used for every picker in the app.

SelectPopup opens below an anchor with a search box and a list of options.
Typing filters the list (label and caption), arrow keys move the highlight,
Enter picks and Esc closes. With allow_custom the typed text can be used as a
new value, for example a production event type that is not in the list.
"""

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QLabel, QLineEdit, QScrollArea, QWidget

from ..assets import pixmap
from ..theme import Color, Type
from .base import add_shadow, hbox, text, vbox

_ROW_H = 44
_MAX_ROWS = 7


@dataclass
class Option:
    value: object
    label: str
    caption: str = ""


class _Row(QFrame):
    def __init__(self, option: Option | None, selected: bool, custom_text: str = ""):
        super().__init__()
        self.option = option
        self.custom_text = custom_text
        self.setObjectName("OptRow")
        self.setFixedHeight(_ROW_H if not (option and option.caption) else _ROW_H + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = hbox(10, (12, 0, 12, 0), self)
        if option is None:
            ic = QLabel()
            ic.setPixmap(pixmap("plus", Color.PRIMARY, 16))
            lay.addWidget(ic)
            lay.addWidget(text(f"Gunakan “{custom_text}”", Type.BODY_STRONG, Color.PRIMARY), 1)
        else:
            col = vbox(1)
            col.addStretch(1)
            col.addWidget(text(option.label, Type.BODY_STRONG if selected else Type.BODY))
            if option.caption:
                col.addWidget(text(option.caption, Type.CAPTION, Color.TEXT_TERTIARY))
            col.addStretch(1)
            lay.addLayout(col, 1)
            if selected:
                ic = QLabel()
                ic.setPixmap(pixmap("check", Color.PRIMARY, 16))
                lay.addWidget(ic)
        self.set_active(False)

    def set_active(self, on: bool) -> None:
        bg = Color.BRAND_SOFT if on else "transparent"
        self.setStyleSheet(f"QFrame#OptRow {{ background: {bg}; border-radius: 10px; }}")


class SelectPopup(QFrame):
    """Floating, searchable list of options. Emits picked(value) or custom(text)."""

    picked = pyqtSignal(object)
    custom = pyqtSignal(str)

    def __init__(self, options: list, current=None, placeholder: str = "Cari", allow_custom: bool = False,
                 empty_text: str = "Tidak ada yang cocok", initial_query: str = "", parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.options = [o if isinstance(o, Option) else Option(*o) for o in options]
        self.current = current
        self.allow_custom = allow_custom
        self.empty_text = empty_text
        self._rows: list[_Row] = []
        self._active = -1

        outer = vbox(0, (8, 8, 8, 8), self)
        self.card = QFrame()
        self.card.setObjectName("SelectCard")
        self.card.setStyleSheet(f"QFrame#SelectCard {{ background: {Color.SURFACE}; border: 1px solid {Color.BORDER};"
                                " border-radius: 16px; }")
        add_shadow(self.card, "pop")
        outer.addWidget(self.card)
        lay = vbox(6, (8, 8, 8, 8), self.card)

        search = QFrame()
        search.setObjectName("SelectSearch")
        search.setFixedHeight(40)
        search.setStyleSheet(f"QFrame#SelectSearch {{ background: {Color.SUBTLE}; border: 1px solid {Color.BORDER};"
                             " border-radius: 12px; }")
        s_lay = hbox(8, (12, 0, 12, 0), search)
        ic = QLabel()
        ic.setPixmap(pixmap("search", Color.ICON, 16))
        s_lay.addWidget(ic)
        self.edit = QLineEdit(initial_query)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setStyleSheet("QLineEdit { background: transparent; border: none; }")
        self.edit.textChanged.connect(lambda _: self._fill())
        self.edit.installEventFilter(self)
        s_lay.addWidget(self.edit, 1)
        lay.addWidget(search)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        self.list_host = QWidget()
        self.list_lay = vbox(2, (0, 0, 0, 0), self.list_host)
        self.scroll.setWidget(self.list_host)
        lay.addWidget(self.scroll)
        self._fill()

    # filtering -----------------------------------------------------------
    def _fill(self) -> None:
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        q = self.edit.text().strip()
        ql = q.lower()
        matches = [o for o in self.options if ql in o.label.lower() or ql in o.caption.lower()]
        self._rows = []
        exact = any(o.label.lower() == ql for o in self.options)
        if self.allow_custom and q and not exact:
            self._rows.append(_Row(None, False, q))
        for o in matches:
            self._rows.append(_Row(o, o.value == self.current))
        for r in self._rows:
            r.mousePressEvent = lambda _e, row=r: self._choose(row)  # noqa: B023
            r.enterEvent = lambda _e, row=r: self._set_active(self._rows.index(row))  # noqa: B023
            self.list_lay.addWidget(r)
        if not self._rows:
            empty = text(self.empty_text, Type.BODY, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignCenter)
            empty.setFixedHeight(_ROW_H)
            self.list_lay.addWidget(empty)
        self.list_lay.addStretch(1)
        heights = sum(r.height() + 2 for r in self._rows[:_MAX_ROWS]) or _ROW_H
        self.scroll.setFixedHeight(heights)
        self._active = -1
        self._set_active(0 if self._rows else -1)
        self._fit()

    def _fit(self) -> None:
        """Shrink or grow the popup to the filtered list, keeping it attached to its anchor."""
        self.card.layout().activate()
        self.layout().activate()
        bottom = self.geometry().bottom()
        height = self.sizeHint().height()
        self.setFixedHeight(height)
        if getattr(self, "_above", False):
            self.move(self.x(), bottom - height + 1)

    def _set_active(self, index: int) -> None:
        if 0 <= self._active < len(self._rows):
            self._rows[self._active].set_active(False)
        self._active = index
        if 0 <= index < len(self._rows):
            self._rows[index].set_active(True)
            self.scroll.ensureWidgetVisible(self._rows[index], 0, 4)

    def _choose(self, row: _Row) -> None:
        if row.option is None:
            self.custom.emit(row.custom_text)
        else:
            self.picked.emit(row.option.value)
        self.close()

    def eventFilter(self, obj, e):  # noqa: N802
        if obj is self.edit and e.type() == QEvent.Type.KeyPress:
            key = e.key()
            if key == Qt.Key.Key_Down and self._rows:
                self._set_active(min(len(self._rows) - 1, self._active + 1))
                return True
            if key == Qt.Key.Key_Up and self._rows:
                self._set_active(max(0, self._active - 1))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if 0 <= self._active < len(self._rows):
                    self._choose(self._rows[self._active])
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, e)

    # placement -------------------------------------------------------------
    def popup_below(self, anchor: QWidget, min_width: int = 300) -> "SelectPopup":
        self.setFixedWidth(max(anchor.width(), min_width) + 16)
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(-8, anchor.height() - 2))
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self._above = pos.y() + self.height() > area.bottom()
        if self._above:
            pos = anchor.mapToGlobal(QPoint(-8, -self.height() + 2))
        pos.setX(max(area.left(), min(pos.x(), area.right() - self.width())))
        self.move(pos)
        self.show()
        self.edit.setFocus()
        return self


def open_select(anchor: QWidget, options: list, on_pick, current=None, placeholder: str = "Cari",
                allow_custom: bool = False, on_custom=None, initial_query: str = "",
                min_width: int = 300) -> SelectPopup:
    """Open a SelectPopup below anchor and call on_pick(value) or on_custom(text)."""
    popup = SelectPopup(options, current, placeholder, allow_custom, initial_query=initial_query, parent=anchor)
    popup.picked.connect(on_pick)
    if on_custom is not None:
        popup.custom.connect(on_custom)
    return popup.popup_below(anchor, min_width)


def bind_select(field, options_fn, on_pick, current_fn=None, placeholder: str = "Cari", allow_custom: bool = False,
                on_custom=None) -> None:
    """Make an InputField with trailing="dropdown" open a SelectPopup.

    Read-only fields open the list on any click; editable fields open it from the chevron
    and keep free typing in the field itself.
    """

    def show():
        open_select(field.field, options_fn(), on_pick, current_fn() if current_fn else None, placeholder,
                    allow_custom, on_custom, "", field.field.width())

    field.trailing_clicked.connect(show)

    class _Opener(QWidget):
        def eventFilter(self, obj, e):  # noqa: N802
            if e.type() == QEvent.Type.MouseButtonPress and field.edit.isReadOnly():
                show()
                return True
            return False

    opener = _Opener(field)
    field.edit.installEventFilter(opener)
    if field.edit.isReadOnly():
        field.edit.setCursor(Qt.CursorShape.PointingHandCursor)
