import sys

from PyQt6.QtWidgets import QApplication

import config
from gui.review_page import ReviewPage


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_populate_lut_combo_defaults_to_no_lut(monkeypatch, tmp_path):
    _app()
    (tmp_path / "HotelMatze.cube").write_text("LUT", encoding="utf-8")
    monkeypatch.setattr("gui.review_page.LUTS_DIR", str(tmp_path))
    config.set_value("lut_path", "HotelMatze.cube")

    page = ReviewPage()
    try:
        page._populate_lut_combo()

        assert page.lut_combo.currentIndex() == 0
        assert page.lut_combo.currentText() == "Kein LUT"
        assert config.get("lut_path") == ""
    finally:
        # ReviewPage owns a PeakVideoPreview LUTWorker QThread; without
        # cleanup it is destroyed while running -> Qt abort at teardown.
        page.cleanup()
