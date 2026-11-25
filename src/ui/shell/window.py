"""Main window: sidebar + page stack on the gradient page background."""

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QFrame, QScrollArea, QStackedWidget, QWidget

from ..components import hbox, text, vbox
from ..theme import Color, Type
from .sidebar import Sidebar


def paint_page_background(widget: QWidget) -> None:
    """Figma 'Background/Page': grey blue with an aqua glow top right and a faint pink bottom left."""
    p = QPainter(widget)
    r = widget.rect()
    p.fillRect(r, QColor(Color.CANVAS))
    g = QRadialGradient(QPointF(r.width() * 0.95, 0), r.width() * 0.6)
    g.setColorAt(0, QColor(168, 233, 236, 90))
    g.setColorAt(0.5, QColor(199, 201, 246, 38))
    g.setColorAt(1, QColor(241, 244, 248, 0))
    p.fillRect(r, g)
    g2 = QRadialGradient(QPointF(0, r.height()), r.width() * 0.45)
    g2.setColorAt(0, QColor(244, 179, 205, 36))
    g2.setColorAt(1, QColor(241, 244, 248, 0))
    p.fillRect(r, g2)


class Page(QWidget):
    """Base page: caption + Display title on the left, actions on the right, scrollable body."""

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        outer = vbox(0, (0, 0, 0, 0), self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("PageViewport")
        scroll.viewport().setStyleSheet("QWidget#PageViewport { background: transparent; }")
        outer.addWidget(scroll)
        self.content = QWidget()
        self.content.setObjectName("PageContent")
        self.content.setStyleSheet("QWidget#PageContent { background: transparent; }")
        self.content.setMinimumHeight(980)
        scroll.setWidget(self.content)
        self.body = vbox(16, (0, 4, 8, 8), self.content)
        header = hbox(12)
        col = vbox(0)
        self.subtitle = text(subtitle, Type.CAPTION, Color.TEXT_TERTIARY)
        col.addWidget(self.subtitle)
        col.addWidget(text(title, Type.DISPLAY))
        header.addLayout(col, 1)
        self.actions = hbox(12)
        header.addLayout(self.actions)
        self.body.addLayout(header)

    def on_show(self) -> None:
        """Hook called when the page becomes visible (refresh timers, etc.)."""


class AppWindow(QWidget):
    """Top-level window shown after login."""

    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SiMonPro")
        self.setMinimumSize(1280, 760)
        lay = hbox(24, (16, 16, 24, 16), self)
        self.sidebar = Sidebar()
        lay.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")
        lay.addWidget(self.stack, 1)
        self.pages: dict = {}
        self.sidebar.navigate.connect(self.go)
        self.sidebar.logout.connect(self.logout_requested)

    def add_page(self, key: str, page: QWidget) -> None:
        self.pages[key] = page
        self.stack.addWidget(page)

    def go(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            from ..components import toast
            toast(self, "info", "Halaman belum tersedia", "Halaman ini dikerjakan pada Desktop P2.")
            self.sidebar.set_active(self.stack.currentWidget().property("pageKey") or "dashboard")
            return
        page.setProperty("pageKey", key)
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        if hasattr(page, "on_show"):
            page.on_show()

    def paintEvent(self, _):  # noqa: N802
        paint_page_background(self)
