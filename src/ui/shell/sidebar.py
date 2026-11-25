"""Collapsible sidebar (240 px expanded, 80 px collapsed)."""

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QBoxLayout, QButtonGroup, QFrame, QLabel, QPushButton, QSizePolicy, QWidget

from ..assets import logo_pixmap, pixmap
from ..components import IconButton, hbox, set_text_color, text, vbox
from ..theme import TONES, Color, Size, Type, font

NAV_MAIN = [("dashboard", "Dashboard", "dashboard"), ("produk", "Produk", "package"),
            ("batch", "Batch", "layers"), ("alert", "Alert", "bell"), ("laporan", "Laporan", "report")]
NAV_OTHER = [("kejadian", "Kejadian", "activity"), ("pengiriman", "Pengiriman", "truck"),
             ("riwayat", "Riwayat dan klaim", "history")]


class NavButton(QPushButton):
    def __init__(self, key: str, label: str, icon_name: str, count: str | None = None, danger: bool = False):
        super().__init__()
        self.key, self.label_text, self.icon_name, self.danger = key, label, icon_name, danger
        self.setCheckable(not danger)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)
        self.setToolTip(label)
        lay = hbox(12, (14, 0, 12, 0), self)
        self.icon = QLabel()
        self.icon.setFixedSize(20, 20)
        lay.addWidget(self.icon)
        self.label = text(label, Type.LABEL)
        self.label.setFont(font(Type.LABEL, size=15))
        lay.addWidget(self.label, 1)
        self.count = None
        if count:
            self.count = QLabel(count, self)
            self.count.setFont(font(Type.CAPTION, weight=700))
            self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.count.setFixedHeight(20)
            self.count.setMinimumWidth(20)
            self.count.setStyleSheet(f"background: {Color.MAGENTA}; color: #FFFFFF; border-radius: 10px; padding: 0 6px;")
            lay.addWidget(self.count)
        self.collapsed = False
        self.toggled.connect(lambda _: self._style())
        self._style()

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        self.label.setVisible(not collapsed)
        m = self.layout()
        if collapsed:
            self.setFixedSize(48, 48)
            m.setContentsMargins(14, 0, 0, 0)
        else:
            self.setMinimumSize(0, 46)
            self.setMaximumSize(16777215, 46)
            m.setContentsMargins(14, 0, 12, 0)
        if self.count:
            if collapsed:
                m.removeWidget(self.count)
                self.count.move(28, 2)
                self.count.show()
                self.count.raise_()
            else:
                m.addWidget(self.count)

    def _style(self) -> None:
        on = self.isChecked()
        if self.danger:
            t = TONES["pink"]
            bg, fg, border, hover = t.soft, t.ink, t.mid, t.mid
        elif on:
            bg, fg, border, hover = Color.SIDEBAR_ACTIVE, "#FFFFFF", Color.SIDEBAR_ACTIVE, Color.SIDEBAR_ACTIVE
        else:
            bg, fg, border, hover = "transparent", Color.SIDEBAR_TEXT, "transparent", "rgba(53,88,114,0.07)"
        self.setStyleSheet(
            f"NavButton {{ background: {bg}; border: 1px solid {border}; border-radius: 14px; }}"
            f"NavButton:hover {{ background: {hover}; }}"
        )
        set_text_color(self.label, fg)
        self.label.setFont(font(Type.LABEL, size=15, weight=700 if on else 600))
        icon_color = fg if (on or self.danger) else Color.SIDEBAR_ICON
        self.icon.setPixmap(pixmap(self.icon_name, icon_color, 20))


class Sidebar(QFrame):
    navigate = pyqtSignal(str)
    logout = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setStyleSheet(
            "QFrame#Sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF,"
            f" stop:0.6 #F6F5FF, stop:1 #F2F1FD); border: 1px solid {Color.BORDER}; border-radius: 24px; }}"
        )
        self.setFixedWidth(Size.SIDEBAR_EXPANDED)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.collapsed = False
        lay = vbox(4, (16, 20, 16, 16), self)

        brand = hbox(10, (4, 0, 0, 0))
        self.logo = QLabel()
        self.logo.setPixmap(logo_pixmap(Color.BRAND, 36))
        brand.addWidget(self.logo)
        self.brand_text = QWidget()
        bt = vbox(0, (0, 0, 0, 0), self.brand_text)
        bt.addWidget(text("SiMonPro", Type.TITLE))
        bt.addWidget(text("Kaleng sarden", Type.CAPTION, Color.TEXT_TERTIARY))
        brand.addWidget(self.brand_text, 1)
        self.toggle = IconButton("chevron-left", "Ciutkan sidebar", "soft", 36, Color.ICON)
        self.toggle.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        brand.addWidget(self.toggle)
        self.brand = brand
        lay.addLayout(brand)
        lay.addSpacing(18)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict = {}
        self.section_labels = []
        self.dividers = []
        for title, items in (("Operasional", NAV_MAIN), ("Lainnya", NAV_OTHER)):
            lab = text(title, Type.OVERLINE, Color.TEXT_TERTIARY)
            lab.setContentsMargins(14, 10, 0, 6)
            lay.addWidget(lab)
            self.section_labels.append(lab)
            div = QFrame()
            div.setFixedSize(32, 1)
            div.setStyleSheet(f"background: {Color.BORDER};")
            div.hide()
            lay.addWidget(div, 0, Qt.AlignmentFlag.AlignHCenter)
            self.dividers.append(div)
            for key, label, ic in items:
                b = NavButton(key, label, ic, "7" if key == "alert" else None)
                b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
                self.group.addButton(b)
                self.buttons[key] = b
                lay.addWidget(b)
        lay.addStretch(1)

        self.device = QFrame()
        self.device.setObjectName("Device")
        self.device.setStyleSheet(
            "QFrame#Device { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(168,233,236,0.35),"
            f" stop:0.55 rgba(244,179,205,0.2), stop:1 #FFFFFF); border: 1px solid {Color.BORDER}; border-radius: 16px; }}"
        )
        d_lay = vbox(4, (14, 12, 14, 12), self.device)
        row = hbox(8)
        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {TONES['green'].solid}; border-radius: 4px;")
        row.addWidget(dot)
        self.device_title = text("ESP32-CAM terhubung", Type.LABEL)
        row.addWidget(self.device_title, 1)
        d_lay.addLayout(row)
        self.device_caption = text("IP 192.168.1.42\n0,8 detik per kaleng", Type.CAPTION, Color.TEXT_TERTIARY)
        d_lay.addWidget(self.device_caption)
        lay.addWidget(self.device)
        self.device_icon = QLabel()
        self.device_icon.setFixedSize(48, 48)
        self.device_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_icon.setPixmap(pixmap("wifi", TONES["green"].solid, 20))
        self.device_icon.setToolTip("ESP32-CAM terhubung, IP 192.168.1.42")
        self.device_icon.setStyleSheet(self.device.styleSheet().replace("QFrame#Device", "QLabel"))
        self.device_icon.hide()
        lay.addWidget(self.device_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(8)
        self.logout_btn = NavButton("logout", "Keluar", "logout", danger=True)
        self.logout_btn.clicked.connect(self.logout)
        lay.addWidget(self.logout_btn)

        self._anim = QParallelAnimationGroup(self)
        for prop in (b"minimumWidth", b"maximumWidth"):
            a = QPropertyAnimation(self, prop)
            a.setDuration(200)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.addAnimation(a)
        self._anim.finished.connect(self._after_anim)

    def set_active(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        start = self.width()
        end = Size.SIDEBAR_COLLAPSED if collapsed else Size.SIDEBAR_EXPANDED
        if collapsed:
            self._apply_collapsed(True)
        for i in range(self._anim.animationCount()):
            a = self._anim.animationAt(i)
            a.setStartValue(start)
            a.setEndValue(end)
        self._anim.start()

    def _after_anim(self) -> None:
        if not self.collapsed:
            self._apply_collapsed(False)
        self.setFixedWidth(Size.SIDEBAR_COLLAPSED if self.collapsed else Size.SIDEBAR_EXPANDED)

    def _apply_collapsed(self, c: bool) -> None:
        self.brand_text.setVisible(not c)
        self.brand.setDirection(QBoxLayout.Direction.TopToBottom if c else QBoxLayout.Direction.LeftToRight)
        self.brand.setAlignment(Qt.AlignmentFlag.AlignHCenter if c else Qt.AlignmentFlag.AlignLeft)
        self.toggle.set_icon("chevron-right" if c else "chevron-left", Color.ICON)
        self.toggle.setToolTip("Lebarkan sidebar" if c else "Ciutkan sidebar")
        for lab in self.section_labels:
            lab.setVisible(not c)
        for div in self.dividers:
            div.setVisible(c)
        for b in list(self.buttons.values()) + [self.logout_btn]:
            b.set_collapsed(c)
            self.layout().setAlignment(b, Qt.AlignmentFlag.AlignHCenter if c else Qt.AlignmentFlag(0))
        self.device.setVisible(not c)
        self.device_icon.setVisible(c)
        self.layout().setContentsMargins(16, 20, 16, 16)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.width(), 800)
