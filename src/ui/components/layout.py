"""Responsive layout helpers (Tailwind style breakpoints for Qt widgets)."""

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QBoxLayout, QGridLayout, QSizePolicy, QWidget

_MAX = 16777215


class AdaptiveRow(QWidget):
    """Lays children out side by side, or stacks them when the row gets narrow.

    breakpoint: minimum width for the side by side layout. When None the row
    stacks as soon as the children's preferred widths no longer fit.
    Children added with fixed_width keep that width only while side by side and
    stretch to the full width when stacked.
    """

    def __init__(self, breakpoint: int | None = None, spacing: int = 16, stack_spacing: int | None = None):
        super().__init__()
        self.breakpoint = breakpoint
        self._spacing = spacing
        self._stack_spacing = spacing if stack_spacing is None else stack_spacing
        self._lay = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(spacing)
        self._items: list = []  # (widget, stretch, fixed_width, align)
        self.stacked = False

    def add(self, widget: QWidget, stretch: int = 0, fixed_width: int | None = None, align=None) -> QWidget:
        self._items.append((widget, stretch, fixed_width, align))
        if fixed_width:
            widget.setFixedWidth(fixed_width)
        if align is not None:
            self._lay.addWidget(widget, stretch, align)
        else:
            self._lay.addWidget(widget, stretch)
        return widget

    def add_stretch(self) -> None:
        self._lay.addStretch(1)

    def _fits(self, width: int) -> bool:
        if self.breakpoint is not None:
            return width >= self.breakpoint
        need = sum((fw or w.sizeHint().width()) for w, _, fw, _ in self._items)
        need += self._spacing * max(0, len(self._items) - 1)
        return width >= need

    def _apply(self, stacked: bool) -> None:
        if stacked == self.stacked:
            return
        self.stacked = stacked
        self._lay.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)
        self._lay.setSpacing(self._stack_spacing if stacked else self._spacing)
        for w, _, fw, _ in self._items:
            if fw:
                if stacked:
                    w.setMinimumWidth(0)
                    w.setMaximumWidth(_MAX)
                else:
                    w.setFixedWidth(fw)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        # Report the stacked width so a narrow window can shrink the row and trigger stacking.
        widths = [w.minimumSizeHint().width() for w, _, fw, _ in self._items if not fw]
        return QSize(max(widths, default=0), super().minimumSizeHint().height())

    def resizeEvent(self, e):  # noqa: N802
        self._apply(not self._fits(e.size().width()))
        super().resizeEvent(e)


class ResponsiveGrid(QWidget):
    """Equal width columns; the column count drops as the grid gets narrower.

    steps limits the allowed column counts, for example (4, 2, 1) so four
    stat cards never end up as a row of three plus one.
    """

    def __init__(self, min_item_width: int, max_columns: int, spacing: int = 16, steps: tuple | None = None):
        super().__init__()
        self.min_item_width = min_item_width
        self.max_columns = max_columns
        self.steps = sorted(steps or range(1, max_columns + 1), reverse=True)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)
        self._spacing = spacing
        self._widgets: list = []
        self._columns = max_columns
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def add(self, widget: QWidget) -> QWidget:
        self._widgets.append(widget)
        self._place()
        return widget

    def clear(self) -> None:
        for w in self._widgets:
            self._grid.removeWidget(w)
            w.deleteLater()
        self._widgets = []

    def _place(self) -> None:
        for w in self._widgets:
            self._grid.removeWidget(w)
        for i, w in enumerate(self._widgets):
            self._grid.addWidget(w, i // self._columns, i % self._columns)
        for c in range(self.max_columns):
            self._grid.setColumnStretch(c, 1 if c < self._columns else 0)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.min_item_width, super().minimumSizeHint().height())

    def resizeEvent(self, e):  # noqa: N802
        cols = (e.size().width() + self._spacing) // (self.min_item_width + self._spacing)
        cols = next((c for c in self.steps if c <= cols), self.steps[-1])
        if cols != self._columns:
            self._columns = cols
            self._place()
        super().resizeEvent(e)
