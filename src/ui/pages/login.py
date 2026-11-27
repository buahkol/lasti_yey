"""Login page (FR-01): navy background, centred form card."""

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QWidget

from ...controllers import AuthController
from ..assets import logo_pixmap
from ..components import Button, Checkbox, InputField, add_shadow, hbox, text, toast, vbox
from ..theme import TONES, Color, Type


class LoginPage(QWidget):
    login_success = pyqtSignal(object)  # models.User

    def __init__(self, controller: AuthController):
        super().__init__()
        self._ctrl = controller
        self.setWindowTitle("SiMonPro, Masuk")
        self.setMinimumSize(900, 600)
        root = vbox(0, (56, 44, 56, 28), self)

        brand = hbox(12)
        logo = QLabel()
        logo.setPixmap(logo_pixmap("#FFFFFF", 44))
        brand.addWidget(logo)
        col = vbox(0)
        col.addWidget(text("SiMonPro", Type.TITLE, "#FFFFFF"))
        col.addWidget(text("Pencatatan produksi dan inspeksi kaleng sarden", Type.CAPTION, "rgba(255,255,255,0.72)"))
        brand.addLayout(col)
        brand.addStretch(1)
        root.addLayout(brand)
        root.addStretch(1)

        center = hbox(0)
        center.addStretch(1)
        center.addWidget(self._card())
        center.addStretch(1)
        root.addLayout(center)
        root.addStretch(1)
        root.addWidget(text("Prototipe Deliverable 3, II3120 Kelompok 06", Type.CAPTION,
                            "rgba(255,255,255,0.6)", align=Qt.AlignmentFlag.AlignCenter))

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(480)
        card.setStyleSheet("QFrame#LoginCard { background: #FFFFFF; border-radius: 28px; }")
        add_shadow(card, "pop")
        lay = vbox(0, (40, 36, 40, 32), card)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(Color.BRAND, 46))
        lay.addWidget(logo)
        lay.addSpacing(20)
        lay.addWidget(text("Masuk ke SiMonPro", Type.DISPLAY))
        lay.addSpacing(6)
        lay.addWidget(text("Gunakan akun Operasional yang telah terdaftar.", Type.BODY, Color.TEXT_SECONDARY))
        lay.addSpacing(26)
        self.username = InputField("Nama pengguna", "Masukkan nama pengguna", "", "user")
        lay.addWidget(self.username)
        lay.addSpacing(16)
        self.password = InputField("Kata sandi", "Masukkan kata sandi", "", "lock", trailing="password")
        lay.addWidget(self.password)
        lay.addSpacing(14)
        self.remember = Checkbox("Ingat nama pengguna", True)
        lay.addWidget(self.remember)
        lay.addSpacing(26)
        self.submit = Button("Masuk", "navy")
        self.submit.setFixedHeight(48)
        self.submit.setStyleSheet("QPushButton { min-height: 46px; max-height: 46px; border-radius: 24px; }")
        self.submit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.submit.clicked.connect(self._submit)
        lay.addWidget(self.submit)
        lay.addSpacing(18)
        status = hbox(8)
        status.addStretch(1)
        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {TONES['green'].solid}; border-radius: 4px;")
        status.addWidget(dot)
        status.addWidget(text("Server lokal terhubung (192.168.1.10)", Type.CAPTION, Color.TEXT_SECONDARY))
        status.addStretch(1)
        lay.addLayout(status)
        for f in (self.username, self.password):
            f.edit.returnPressed.connect(self._submit)
        return card

    def reset(self) -> None:
        self.password.edit.clear()
        self.username.set_error(None)
        self.password.set_error(None)
        if not self.remember.isChecked():
            self.username.edit.clear()

    def _submit(self) -> None:
        user, error = self._ctrl.login(self.username.value(), self.password.value())
        if user is not None:
            self.username.set_error(None)
            self.password.set_error(None)
            self.login_success.emit(user)
            return
        self.username.set_error("")
        self.password.set_error(error)
        toast(self, "error", "Gagal masuk", "Periksa kembali nama pengguna dan kata sandi.")

    def paintEvent(self, _):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor("#355872"))
        g.setColorAt(0.6, QColor("#2E4C8E"))
        g.setColorAt(1, QColor("#3533CD"))
        p.fillRect(self.rect(), g)
        for cx, cy, r, c, a in ((w * 0.85, h * 0.85, w * 0.3, "#F4B3CD", 110),
                                (w * 0.02, h * 0.0, w * 0.28, "#A8E9EC", 85),
                                (w * 0.88, h * 0.1, w * 0.25, "#5C61E4", 120)):
            rg = QRadialGradient(QPointF(cx, cy), r)
            col = QColor(c)
            col.setAlpha(a)
            rg.setColorAt(0, col)
            col.setAlpha(0)
            rg.setColorAt(1, col)
            p.fillRect(self.rect(), rg)
        for cx, cy, sizes in ((w * 0.89, h * 0.76, (260, 400, 540, 680)), (w * 0.06, h * 0.11, (220, 340))):
            for i, s in enumerate(sizes):
                c = QColor(Color.AQUA)
                c.setAlphaF(max(0.06, 0.28 - i * 0.07))
                p.setPen(QPen(c, 1))
                p.drawEllipse(QRectF(cx - s / 2, cy - s / 2, s, s))
