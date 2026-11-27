"""The app must open on a fresh database: products from the seed, but no batches, events or inspections.

Regression: the Kejadian page took ``batches()[0]`` and the main window never opened after login.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.controllers import Controllers  # noqa: E402


def _empty_controllers() -> Controllers:
    c = Controllers.create(use_api=False)
    batches = c.batches._batches  # the shared sample BatchService
    batches._batches.clear()
    c.events._events._events.clear()
    return c


def test_main_window_opens_without_batches():
    from PyQt6.QtWidgets import QApplication

    from src.ui.app import SiMonProApp
    from src.ui.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    simonpro = SiMonProApp()
    simonpro.controllers = _empty_controllers()
    user, error = simonpro.controllers.auth.login("operasional", "simonpro")
    assert error is None
    simonpro._build_main(user)  # raises if a page cannot cope with zero batches
    win = simonpro.window
    for key in ("dashboard", "produk", "batch", "alert", "laporan", "kejadian", "riwayat"):
        win.go(key)
        win.pages[key].refresh()
        app.processEvents()
    assert win.pages["kejadian"].code == ""
    win.close()
