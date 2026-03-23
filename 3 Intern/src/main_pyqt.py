# main_pyqt.py - PeakCut Entry Point (PyQt6 Version)

import sys
import os
import fcntl
import multiprocessing

from PyQt6.QtWidgets import QApplication, QMessageBox

from gui.main_window import MainWindow
from gui.apple_style import get_stylesheet
from utils import TEMP_DIR

LOCK_FILE = os.path.join(TEMP_DIR, "peakcut.lock")

# Module-level reference prevents GC from closing the file and releasing the lock
_lock_fp = None


def _setup_environment():
    """Set up environment for macOS .app bundles."""
    # Homebrew paths (macOS .app bundles don't inherit shell PATH)
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
    current = os.environ.get("PATH", "")
    missing = [p for p in extra_paths if p not in current]
    if missing:
        os.environ["PATH"] = current + ":" + ":".join(missing)

    # Force ffmpeg multimedia backend — AVFoundation creates native video
    # rendering layers that show through even when using QVideoSink
    os.environ["QT_MULTIMEDIA_BACKEND"] = "ffmpeg"


def main():
    global _lock_fp

    _setup_environment()

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
    multiprocessing.freeze_support()
    main()
