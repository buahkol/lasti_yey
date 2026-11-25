"""Application flow: login page, then the main window with the Desktop P1 pages."""

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


def run(argv: list | None = None) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv or sys.argv)
    app.setApplicationName("SiMonPro")
    apply_theme(app)
    simonpro = SiMonProApp()
    simonpro.start()
    return app.exec()
