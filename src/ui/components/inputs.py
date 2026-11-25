"""Form controls: InputField, SearchField, Checkbox, RadioOption, SegmentedTabs."""

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QButtonGroup, QFrame, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QToolButton, QWidget,
)

from ..assets import icon, pixmap
from ..theme import TONES, Color, Radius, Size, Type, font
from .base import hbox, set_text_color, text, vbox


class InputField(QWidget):
    """Labelled text field with leading icon, optional trailing action and helper text.

    States: default, focus (automatic), error, disabled.
    trailing: None | "password" (eye toggle) | "dropdown" (chevron)
    """

    trailing_clicked = pyqtSignal()

    def __init__(self, label: str, placeholder: str = "", value: str = "", icon_name: str | None = None,
                 trailing: str | None = None, helper: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._error = False
        self._helper_default = helper
        lay = vbox(8, (0, 0, 0, 0), self)
        self.label = text(label, Type.LABEL)
        lay.addWidget(self.label)

        self.field = QFrame()
        self.field.setObjectName("Field")
        self.field.setFixedHeight(Size.INPUT)
        f_lay = hbox(10, (14, 0, 10, 0), self.field)
        self._icon_name = icon_name
        self.icon = QLabel()
        if icon_name:
            self.icon.setPixmap(pixmap(icon_name, Color.ICON, 18))
            f_lay.addWidget(self.icon)
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText(placeholder)
        self.edit.installEventFilter(self)
        f_lay.addWidget(self.edit, 1)

        self.trailing = None
        if trailing:
            self.trailing = QToolButton()
            self.trailing.setProperty("iconStyle", "ghost")
            self.trailing.setFixedSize(30, 30)
            self.trailing.setCursor(Qt.CursorShape.PointingHandCursor)
            if trailing == "password":
                self.edit.setEchoMode(QLineEdit.EchoMode.Password)
                self.trailing.setIcon(icon("eye", Color.ICON, 18))
                self.trailing.setToolTip("Tampilkan kata sandi")
                self.trailing.clicked.connect(self._toggle_password)
            else:
                self.trailing.setIcon(icon("chevron-down", Color.ICON, 18))
                self.trailing.setToolTip("Pilih")
                self.trailing.clicked.connect(self.trailing_clicked)
            f_lay.addWidget(self.trailing)
        lay.addWidget(self.field)

        self.helper = text(helper, Type.CAPTION, Color.TEXT_TERTIARY, wrap=True)
        self.helper.setVisible(bool(helper))
        lay.addWidget(self.helper)
        self._refresh()

    # state ---------------------------------------------------------------
    def set_error(self, message: str | None) -> None:
        self._error = bool(message)
        self.helper.setText(message or self._helper_default)
        self.helper.setVisible(bool(message or self._helper_default))
        set_text_color(self.helper, TONES["pink"].ink if message else Color.TEXT_TERTIARY)
        self._refresh()

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (Qt naming)
        super().setEnabled(enabled)
        self._refresh()

    def value(self) -> str:
        return self.edit.text()

    def _toggle_password(self) -> None:
        hidden = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.trailing.setIcon(icon("eye-off" if hidden else "eye", Color.ICON, 18))

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._refresh()
        return super().eventFilter(obj, event)

    def _refresh(self) -> None:
        focused = self.edit.hasFocus()
        if not self.isEnabled():
            bg, border, width = Color.CANVAS_ALT, Color.BORDER_STRONG, 1
        elif self._error:
            bg, border, width = Color.SURFACE, Color.CHART_NG, 2
        elif focused:
            bg, border, width = Color.SURFACE, Color.BORDER_FOCUS, 2
        else:
            bg, border, width = Color.SURFACE, Color.BORDER_STRONG, 1
        self.field.setStyleSheet(
            f"QFrame#Field {{ background: {bg}; border: {width}px solid {border}; border-radius: {Radius.INPUT}px; }}"
        )
        color = Color.TEXT_SECONDARY if not self.isEnabled() else Color.TEXT_PRIMARY
        self.edit.setStyleSheet(f"color: {color};")


class SearchField(QFrame):
    """Pill search box with keyboard shortcut hint."""

    def __init__(self, placeholder: str = "Cari kode batch", width: int = 300, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Search")
        self.setFixedSize(width, 44)
        self.setStyleSheet(
            f"QFrame#Search {{ background: {Color.SURFACE}; border: 1px solid {Color.BORDER}; border-radius: 22px; }}"
        )
        lay = hbox(10, (16, 0, 8, 0), self)
        ic = QLabel()
        ic.setPixmap(pixmap("search", Color.ICON, 18))
        lay.addWidget(ic)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        lay.addWidget(self.edit, 1)
        hint = text("Ctrl K", Type.CAPTION, Color.TEXT_SECONDARY)
        hint.setFixedHeight(26)
        hint.setStyleSheet(
            f"color: {Color.TEXT_SECONDARY}; background: {Color.CANVAS_ALT}; border-radius: 8px; padding: 3px 8px;"
        )
        lay.addWidget(hint)


class Checkbox(QAbstractButton):
    """20px rounded checkbox with a label."""

    def __init__(self, label: str, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setText(label)
        self.setFont(font(Type.BODY))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        return QSize(20 + 10 + fm.horizontalAdvance(self.text()) + 2, max(22, fm.height()))

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(0.75, (self.height() - 20) / 2 + 0.75, 18.5, 18.5)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Color.PRIMARY))
            p.drawRoundedRect(box, 6, 6)
            p.drawPixmap(int(box.x() + 2.5), int(box.y() + 2.5), pixmap("check", "#FFFFFF", 14, 2.4))
        else:
            p.setPen(QPen(QColor(Color.BORDER_STRONG), 1.5))
            p.setBrush(QColor(Color.SURFACE))
            p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor(Color.TEXT_PRIMARY))
        p.setFont(self.font())
        p.drawText(QRectF(30, 0, self.width() - 30, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class _RadioDot(QWidget):
    def __init__(self, owner: QAbstractButton):
        super().__init__()
        self._owner = owner
        self.setFixedSize(20, 20)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self._owner.isChecked()
        p.setBrush(QColor(Color.SURFACE))
        p.setPen(QPen(QColor(Color.PRIMARY if on else Color.BORDER_STRONG), 6 if on else 1.5))
        inset = 3 if on else 0.75
        p.drawEllipse(QRectF(inset, inset, 20 - 2 * inset, 20 - 2 * inset))


class RadioOption(QAbstractButton):
    """Card-style radio option with title and description."""

    def __init__(self, title: str, description: str = "", checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = hbox(12, (14, 12, 14, 12), self)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._dot = _RadioDot(self)
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignTop)
        col = vbox(2)
        col.addWidget(text(title, Type.BODY_STRONG))
        if description:
            col.addWidget(text(description, Type.CAPTION, Color.TEXT_TERTIARY, wrap=True))
        lay.addLayout(col, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toggled.connect(lambda _: (self._dot.update(), self.update()))

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.layout().sizeHint()

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = TONES["indigo"]
        on = self.isChecked()
        p.setBrush(QColor(t.soft if on else Color.SURFACE))
        p.setPen(QPen(QColor(t.mid if on else Color.BORDER), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 14, 14)


class _TabButton(QPushButton):
    def __init__(self, label: str, count: str | None):
        super().__init__()
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        lay = hbox(8, (14, 0, 14 if count is None else 6, 0), self)
        self._label = text(label, Type.LABEL, Color.TEXT_SECONDARY)
        lay.addWidget(self._label)
        self._count = None
        if count is not None:
            self._count = QLabel(count)
            self._count.setFont(font(Type.CAPTION, weight=700))
            self._count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._count.setFixedHeight(22)
            self._count.setMinimumWidth(22)
            lay.addWidget(self._count)
        self.toggled.connect(self._style)
        self._style(False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.layout().sizeHint().width(), 32)

    def _style(self, on: bool) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background: {Color.BRAND if on else 'transparent'}; border: none; border-radius: 16px; }}"
            + ("" if on else f"QPushButton:hover {{ background: {Color.CANVAS}; }}")
        )
        set_text_color(self._label, "#FFFFFF" if on else Color.TEXT_SECONDARY)
        if self._count:
            bg = TONES["blue"].mid if on else Color.CANVAS_ALT
            fg = Color.TEXT_PRIMARY if on else Color.TEXT_SECONDARY
            self._count.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 11px; padding: 0 7px;")


class SegmentedTabs(QFrame):
    """Pill-shaped tab group. Emits changed(index)."""

    changed = pyqtSignal(int)

    def __init__(self, items: list, current: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Tabs")
        self.setStyleSheet(
            f"QFrame#Tabs {{ background: {Color.SURFACE}; border: 1px solid {Color.BORDER}; border-radius: 19px; }}"
        )
        lay = hbox(2, (3, 3, 3, 3), self)
        self._group = QButtonGroup(self)
        for i, item in enumerate(items):
            label, count = (item, None) if isinstance(item, str) else item
            b = _TabButton(label, count)
            self._group.addButton(b, i)
            lay.addWidget(b)
        self._group.button(current).setChecked(True)
        self._group.idClicked.connect(self.changed)

    def set_counts(self, counts: list) -> None:
        """Update the number chips, for example after a filter changes."""
        for i, count in enumerate(counts):
            button = self._group.button(i)
            if button is not None and button._count is not None:
                button._count.setText(str(count))
