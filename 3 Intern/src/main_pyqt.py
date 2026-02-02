# main_pyqt.py - PeakCut Entry Point (PyQt6 Version)

import sys
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.apple_style import get_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
