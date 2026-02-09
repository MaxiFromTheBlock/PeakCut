# main_pyqt.py - PeakCut Entry Point (PyQt6 Version)

import sys
import os
import fcntl

from PyQt6.QtWidgets import QApplication, QMessageBox

from gui.main_window import MainWindow
from gui.apple_style import get_stylesheet

LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp", "peakcut.lock")

# Module-level reference prevents GC from closing the file and releasing the lock
_lock_fp = None


def main():
    global _lock_fp

    # Ensure temp dir exists
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    # Single-instance lock (held for entire process lifetime)
    _lock_fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(_lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        app = QApplication(sys.argv)
        QMessageBox.warning(None, "PeakCut", "PeakCut läuft bereits.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
