"""App shell: window, sidebar and page base."""

from .sidebar import NavButton, Sidebar
from .window import AppWindow, Page, paint_page_background

__all__ = ["AppWindow", "Page", "Sidebar", "NavButton", "paint_page_background"]
