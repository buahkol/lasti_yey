"""Application flow: login page, then the main window with the Desktop P1 pages."""

import gc
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from .components import toast
from .pages.alert import AlertPage
from .pages.batch import BatchPage
from .pages.dashboard import DashboardPage
from .pages.laporan import LaporanPage
from .pages.login import LoginPage
from .pages.produk import ProdukPage
from .shell import AppWindow
from .theme import apply_theme
from .theme.scale import choose_scale


class SiMonProApp:
    def __init__(self):
        self.login = LoginPage()
        self.login.login_success.connect(self._open_main)
        self.window: AppWindow | None = None

    def start(self) -> None:
        self.login.showMaximized()

    def _open_main(self, user: dict) -> None:
        win = AppWindow()
        getter = lambda: win  # noqa: E731
        win.add_page("dashboard", DashboardPage(win.go, getter))
        win.add_page("produk", ProdukPage(getter))
        win.add_page("batch", BatchPage(getter))
        win.add_page("alert", AlertPage(getter))
        win.add_page("laporan", LaporanPage(getter))
        win.logout_requested.connect(self._logout)
        win.go("dashboard")
        win.showMaximized()
        self.window = win
        self.login.hide()
        toast(win, "success", "Berhasil masuk", f"Selamat bekerja, {user['name']}.")

    def _logout(self) -> None:
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
    simonpro.start()
    return app.exec()
