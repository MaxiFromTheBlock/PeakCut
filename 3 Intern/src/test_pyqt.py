# test_pyqt.py - Test PyQt6 with Apple styling

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt

from gui.apple_style import get_stylesheet, COLORS


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut PyQt Test")
        self.setMinimumSize(400, 200)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Title label
        title = QLabel("PeakCut PyQt Migration")
        title.setProperty("class", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Success button (primary style)
        button = QPushButton("PeakCut PyQt funktioniert!")
        button.setProperty("class", "primary")
        button.setMinimumWidth(250)
        button.clicked.connect(self.on_click)
        layout.addWidget(button)

        # Secondary button
        close_btn = QPushButton("Fenster schließen")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def on_click(self):
        print("PyQt6 funktioniert!")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet())

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
