"""Application flow: login page, then the main window with the Desktop P1 pages."""

import gc
import os
import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ..controllers import Controllers
from ..models import User
from ..services import ApiError, ServerUnavailable, SessionExpired
from .components import toast
from .components.photo import set_photo_loader
from .pages.alert import AlertPage
from .pages.batch import BatchPage
from .pages.dashboard import DashboardPage
from .pages.kejadian import KejadianPage
from .pages.laporan import LaporanPage
from .pages.login import LoginPage
from .pages.produk import ProdukPage
from .pages.riwayat import RiwayatPage
from .shell import AppWindow
from .theme import apply_theme
from .theme.scale import choose_scale


class SiMonProApp:
    """Wires the MVC layers: services and controllers are created once and shared by every page."""

    def __init__(self):
        self.controllers = Controllers.create()
        # real camera photos from the server; sample mode keeps the painted placeholders
        set_photo_loader(self.controllers.api.photo if self.controllers.api else None)
        self.login = LoginPage(self.controllers.auth)
        self.login.login_success.connect(self._open_main)
        self.window: AppWindow | None = None

    def start(self) -> None:
        self.login.showMaximized()

    def _open_main(self, user: User) -> None:
        c = self.controllers
        win = AppWindow()
        win.user = user  # printed on PDF reports
        getter = lambda: win  # noqa: E731
        win.add_page("dashboard", DashboardPage(c.dashboard, c.batches, user, win.go, getter))
        win.add_page("produk", ProdukPage(c.products, getter))
        laporan = LaporanPage(c.reports, getter)
        win.add_page("batch", BatchPage(c.batches, getter, lambda code: (win.go("laporan"), laporan.show_batch(code)),
                                        c.reports))
        win.add_page("alert", AlertPage(c.alerts, getter))
        win.add_page("laporan", laporan)
        win.add_page("kejadian", KejadianPage(c.events, getter))
        win.add_page("riwayat", RiwayatPage(c.history, getter))
        win.logout_requested.connect(self._logout)
        win.go("dashboard")
        win.showMaximized()
        self.window = win
        self.login.hide()
        toast(win, "success", "Berhasil masuk", f"Selamat bekerja, {user.name}.")

    def handle_error(self, exc: BaseException) -> bool:
        """Show a server problem to the operator instead of letting Qt abort. True when handled."""
        target = self.window or self.login
        if isinstance(exc, SessionExpired):
            self._logout()
            toast(self.login, "info", "Sesi berakhir", "Silakan masuk kembali.")
            return True
        if isinstance(exc, ServerUnavailable):
            toast(target, "error", "Server tidak terhubung", str(exc))
            return True
        if isinstance(exc, ApiError):
            toast(target, "error", "Permintaan ditolak server", exc.message)
            return True
        return False

    def _logout(self) -> None:
        self.controllers.auth.logout()
        if self.window:
            self.window.close()
            self.window.deleteLater()
            self.window = None
        self.login.reset()
        self.login.showMaximized()


def _create_app(argv: list) -> QApplication:
    """Create the QApplication with a UI scale that fits the current screen.

    The screen size is only known once a QApplication exists, so the first
    instance measures the screen and is replaced when a smaller scale is needed.
    """
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if "QT_SCALE_FACTOR" in os.environ:
        return QApplication(argv)
    probe = QApplication(argv)
    area = probe.primaryScreen().availableGeometry()
    scale = choose_scale(area.width(), area.height())
    if scale == 1.0:
        return probe
    del probe
    gc.collect()
    os.environ["QT_SCALE_FACTOR"] = f"{scale:g}"
    return QApplication(argv)


def run(argv: list | None = None) -> int:
    app = _create_app(argv or sys.argv)
    app.setApplicationName("SiMonPro")
    apply_theme(app)
    simonpro = SiMonProApp()

    def excepthook(exc_type, exc, tb):
        # PyQt6 aborts on an exception that escapes a slot; server errors become a message instead
        try:
            if simonpro.handle_error(exc):
                return
        except Exception:  # noqa: BLE001
            pass
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = excepthook
    simonpro.start()
    return app.exec()
