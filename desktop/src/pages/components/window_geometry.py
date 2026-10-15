"""Use logical screen coordinates, including Windows DPI scaling."""
from PySide6.QtWidgets import QApplication


def fit_window_to_screen(window, preferred_width, preferred_height):
    screen = window.screen() or QApplication.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    width = min(preferred_width, int(available.width() * 0.94))
    height = min(preferred_height, int(available.height() * 0.94))
    window.setMinimumSize(0, 0)
    window.resize(width, height)
    window.move(available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2)
