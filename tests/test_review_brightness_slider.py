import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from gui.review_page import ResettableBrightnessSlider


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class _Event:
    def __init__(self):
        self.accepted = False

    def button(self):
        return Qt.MouseButton.LeftButton

    def accept(self):
        self.accepted = True


def test_brightness_slider_double_click_resets_to_zero():
    _app()
    slider = ResettableBrightnessSlider(Qt.Orientation.Horizontal)
    slider.setRange(-100, 100)
    slider.setValue(42)
    event = _Event()

    slider.mouseDoubleClickEvent(event)

    assert slider.value() == 0
    assert event.accepted is True
