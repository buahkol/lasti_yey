"""Date range picker popup (Figma "Date Picker")."""

from PyQt6.QtCore import QDate, QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QAbstractButton, QFrame, QGridLayout, QPushButton, QWidget

from ..theme import TONES, Color, Type, font
from .base import add_shadow, hbox, text, vbox
from .buttons import Button, IconButton

MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember"]
MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def format_range(start: QDate, end: QDate) -> str:
    """'23 sampai 25 Nov 2026' or '25 Nov 2026'."""
    if start == end:
        return f"{start.day()} {MONTHS_SHORT[start.month() - 1]} {start.year()}"
    if start.month() == end.month() and start.year() == end.year():
        return f"{start.day()} sampai {end.day()} {MONTHS_SHORT[end.month() - 1]} {end.year()}"
    return (f"{start.day()} {MONTHS_SHORT[start.month() - 1]} sampai "
            f"{end.day()} {MONTHS_SHORT[end.month() - 1]} {end.year()}")


class _Day(QAbstractButton):
    def __init__(self, picker: "DatePicker"):
        super().__init__()
        self.picker = picker
        self.date = QDate()
        self.setFixedSize(44, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(font(Type.BODY))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(44, 38)

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pk, d = self.picker, self.date
        t = TONES["indigo"]
        start, end = pk.start, pk.end or pk.start
        in_month = d.month() == pk.month.month()
        in_range = start.isValid() and start <= d <= end
        is_end = d in (start, end)
        if in_range and start != end:
            r = QRectF(0, 1, 44, 36)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.soft))
            if d == start:
                r = QRectF(4, 1, 40, 36)
            if d == end:
                r = QRectF(0, 1, 40, 36)
            p.drawRoundedRect(r, 12 if is_end else 0, 12 if is_end else 0)
            if d == start:
                p.drawRect(QRectF(24, 1, 20, 36))
            if d == end:
                p.drawRect(QRectF(0, 1, 20, 36))
        if is_end and in_range:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Color.PRIMARY))
            p.drawRoundedRect(QRectF(4, 1, 36, 36), 12, 12)
        elif self.underMouse() and d <= pk.today:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Color.CANVAS))
            p.drawRoundedRect(QRectF(4, 1, 36, 36), 12, 12)
        future = d > pk.today
        if is_end and in_range:
            color, weight = "#FFFFFF", 600
        elif not in_month or future:
            color, weight = Color.TEXT_TERTIARY, 400
        elif in_range:
            color, weight = t.ink, 500
        else:
            color, weight = Color.TEXT_PRIMARY, 400
        p.setFont(font(Type.BODY, weight=weight))
        c = QColor(color)
        if future:
            c.setAlphaF(0.6)
        p.setPen(c)
        p.drawText(QRectF(0, 0, 44, 38), Qt.AlignmentFlag.AlignCenter, str(d.day()))
        if d == pk.today:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Color.PINK if is_end else Color.MAGENTA))
            p.drawEllipse(QRectF(20, 30, 4, 4))


class DatePicker(QFrame):
    """Popup calendar for choosing a date range. Emits applied(start, end)."""

    applied = pyqtSignal(QDate, QDate)

    def __init__(self, start: QDate, end: QDate, today: QDate | None = None, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.today = today or QDate.currentDate()
        self.start, self.end = start, end
        self.month = QDate(end.year(), end.month(), 1)
        outer = vbox(0, (16, 12, 16, 24), self)
        card = QFrame()
        card.setObjectName("Picker")
        card.setStyleSheet(
            f"QFrame#Picker {{ background: #FFFFFF; border: 1px solid {Color.BORDER}; border-radius: 20px; }}"
        )
        add_shadow(card, "pop")
        outer.addWidget(card)
        lay = vbox(12, (18, 18, 18, 16), card)

        presets = hbox(6)
        for label, days in (("Hari ini", 1), ("3 hari", 3), ("7 hari", 7), ("30 hari", 30)):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(font(Type.CAPTION, weight=600))
            b.setStyleSheet(
                f"QPushButton {{ background: {Color.CANVAS}; color: {Color.TEXT_SECONDARY}; border: none;"
                f" border-radius: 13px; padding: 5px 11px; }}"
                f"QPushButton:hover {{ background: {TONES['indigo'].soft}; color: {TONES['indigo'].ink}; }}"
            )
            b.clicked.connect(lambda _=False, n=days: self._preset(n))
            presets.addWidget(b)
        presets.addStretch(1)
        lay.addLayout(presets)

        nav = hbox(0)
        prev = IconButton("chevron-left", "Bulan sebelumnya", "ghost", 32)
        prev.clicked.connect(lambda: self._shift(-1))
        nav.addWidget(prev)
        self.month_label = text("", Type.HEADING, align=Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.month_label, 1)
        nxt = IconButton("chevron-right", "Bulan berikutnya", "ghost", 32)
        nxt.clicked.connect(lambda: self._shift(1))
        nav.addWidget(nxt)
        lay.addLayout(nav)

        grid = QGridLayout()
        grid.setSpacing(0)
        grid.setVerticalSpacing(2)
        for i, d in enumerate(DAYS):
            grid.addWidget(text(d, Type.CAPTION, Color.TEXT_TERTIARY, align=Qt.AlignmentFlag.AlignCenter), 0, i)
        self.cells = []
        for r in range(6):
            for c in range(7):
                cell = _Day(self)
                cell.clicked.connect(lambda _=False, w=cell: self._pick(w.date))
                grid.addWidget(cell, r + 1, c)
                self.cells.append(cell)
        lay.addLayout(grid)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Color.BORDER};")
        lay.addWidget(sep)
        foot = hbox(8)
        col = vbox(0)
        col.addWidget(text("Rentang dipilih", Type.CAPTION, Color.TEXT_TERTIARY))
        self.range_label = text("", Type.BODY_STRONG)
        col.addWidget(self.range_label)
        foot.addLayout(col, 1)
        cancel = Button("Batal", "outline", "sm")
        cancel.clicked.connect(self.close)
        foot.addWidget(cancel)
        ok = Button("Terapkan", "primary", "sm")
        ok.clicked.connect(self._apply)
        foot.addWidget(ok)
        lay.addLayout(foot)
        self._render()

    def popup_below(self, anchor: QWidget) -> None:
        """Show right-aligned under the anchor widget."""
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height()))
        self.move(pos.x() - self.width() + 16, pos.y() - 4)
        self.show()

    def _preset(self, days: int) -> None:
        self.end = self.today
        self.start = self.today.addDays(-(days - 1))
        self.month = QDate(self.end.year(), self.end.month(), 1)
        self._render()

    def _shift(self, months: int) -> None:
        self.month = self.month.addMonths(months)
        self._render()

    def _pick(self, d: QDate) -> None:
        if d > self.today:
            return
        if self.end is not None or not self.start.isValid():
            self.start, self.end = d, None
        elif d < self.start:
            self.start, self.end = d, self.start
        else:
            self.end = d
        self._render()

    def _apply(self) -> None:
        self.applied.emit(self.start, self.end or self.start)
        self.close()

    def _render(self) -> None:
        self.month_label.setText(f"{MONTHS[self.month.month() - 1]} {self.month.year()}")
        first = self.month.addDays(-(self.month.dayOfWeek() - 1))
        for i, cell in enumerate(self.cells):
            cell.date = first.addDays(i)
            cell.update()
        self.range_label.setText(format_range(self.start, self.end or self.start).replace(f" {self.today.year()}", ""))
