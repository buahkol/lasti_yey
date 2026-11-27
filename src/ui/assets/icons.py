"""Line icons (24px grid, 1.75 stroke) rendered to any colour and size.

Shapes follow the Lucide icon set (ISC licence), same as the Figma
"Icons" frame.
"""

from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


def _p(d: str) -> str:
    return f'<path d="{d}"/>'


def _c(x, y, r) -> str:
    return f'<circle cx="{x}" cy="{y}" r="{r}"/>'


def _r(x, y, w, h, rx) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>'


ICONS = {
    "dashboard": [_r(3, 3, 7, 9, 1.5), _r(14, 3, 7, 5, 1.5), _r(14, 12, 7, 9, 1.5), _r(3, 16, 7, 5, 1.5)],
    "package": [_p("M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"), _p("M12 22V12"), _p("M3.29 7 12 12l8.71-5"), _p("m7.5 4.27 9 5.15")],
    "layers": [_p("M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"), _p("M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"), _p("M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17")],
    "bell": [_p("M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"), _p("M10.3 21a1.94 1.94 0 0 0 3.4 0")],
    "report": [_p("M3 3v18h18"), _p("M18 17V9"), _p("M13 17V5"), _p("M8 17v-3")],
    "activity": [_p("M22 12h-4l-3 9L9 3l-3 9H2")],
    "truck": [_p("M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"), _p("M15 18H9"), _p("M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"), _c(17, 18, 2), _c(7, 18, 2)],
    "history": [_p("M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"), _p("M3 3v5h5"), _p("M12 7v5l4 2")],
    "logout": [_p("M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"), _p("m16 17 5-5-5-5"), _p("M21 12H9")],
    "search": [_c(11, 11, 7.5), _p("m21 21-4.3-4.3")],
    "refresh": [_p("M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"), _p("M21 3v5h-5"), _p("M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"), _p("M8 16H3v5")],
    "chevron-right": [_p("m9 18 6-6-6-6")],
    "chevron-left": [_p("m15 18-6-6 6-6")],
    "chevron-down": [_p("m6 9 6 6 6-6")],
    "plus": [_p("M5 12h14"), _p("M12 5v14")],
    "x": [_p("M18 6 6 18"), _p("m6 6 12 12")],
    "check": [_p("M20 6 9 17l-5-5")],
    "warning": [_p("m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"), _p("M12 9v4"), _p("M12 17h.01")],
    "download": [_p("M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"), _p("m7 10 5 5 5-5"), _p("M12 15V3")],
    "calendar": [_r(3, 4, 18, 18, 2), _p("M16 2v4"), _p("M8 2v4"), _p("M3 10h18")],
    "folder": [_p("M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0"
                  "-2 2v13a2 2 0 0 0 2 2Z")],
    "image": [_r(3, 3, 18, 18, 2), _c(9, 9, 2), _p("m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21")],
    "lock": [_r(3, 11, 18, 11, 2), _p("M7 11V7a5 5 0 0 1 10 0v4")],
    "user": [_p("M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"), _c(12, 7, 4)],
    "filter": [_p("M22 3H2l8 9.46V19l4 2v-8.54L22 3z")],
    "more": [_c(12, 12, 1), _c(19, 12, 1), _c(5, 12, 1)],
    "edit": [_p("M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z")],
    "expand": [_p("M8 3H5a2 2 0 0 0-2 2v3"), _p("M21 8V5a2 2 0 0 0-2-2h-3"), _p("M3 16v3a2 2 0 0 0 2 2h3"), _p("M16 21h3a2 2 0 0 0 2-2v-3")],
    "wifi": [_p("M12 20h.01"), _p("M2 8.82a15 15 0 0 1 20 0"), _p("M5 12.859a10 10 0 0 1 14 0"), _p("M8.5 16.429a5 5 0 0 1 7 0")],
    "eye": [_p("M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"), _c(12, 12, 3)],
    "eye-off": [_p("M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"), _p("M14.084 14.158a3 3 0 0 1-4.242-4.242"), _p("M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"), _p("m2 2 20 20")],
    "check-circle": [_c(12, 12, 10), _p("m9 12 2 2 4-4")],
    "x-circle": [_c(12, 12, 10), _p("m15 9-6 6"), _p("m9 9 6 6")],
    "trend-down": [_p("M22 17 13.5 8.5 8.5 13.5 2 7"), _p("M16 17h6v-6")],
    "trend-up": [_p("M22 7 13.5 15.5 8.5 10.5 2 17"), _p("M16 7h6v6")],
    "camera": [_p("M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"), _c(12, 13, 3)],
    "clock": [_c(12, 12, 10), _p("M12 6v6l4 2")],
    "file": [_p("M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"), _p("M14 2v4a2 2 0 0 0 2 2h4"), _p("M16 13H8"), _p("M16 17H8"), _p("M10 9H8")],
    "shield": [_p("M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"), _p("m9 12 2 2 4-4")],
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = "".join(ICONS[name])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    ).encode()


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#56718A", size: int = 20, stroke: float = 1.75, dpr: float = 2.0) -> QPixmap:
    """Render an icon to a transparent pixmap (HiDPI aware)."""
    renderer = QSvgRenderer(QByteArray(_svg(name, color, stroke)))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = "#56718A", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))
