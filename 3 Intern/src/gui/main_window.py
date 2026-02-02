# main_window.py - PeakCut Main Window (PyQt6)

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QTextEdit
)
from PyQt6.QtCore import Qt

from .apple_style import get_stylesheet, COLORS

# Import PeakCut core modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import MATERIAL_DIR, EXPORT_DIR
from sync import run_sync
from peaks import (
    run_peak_analysis, get_peaks, get_mode,
    play_current_peak, go_back, go_forward,
    stop_playback, switch_mode, ignore_current_peak
)
from export import run_export
from status import set_callback


class MainWindow(QMainWindow):
    """PeakCut Main Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)

        # Track current peak locally
        self._current_peak = 0
        self._num_peaks = 0

        self._setup_ui()
        self._setup_statusbar()

        # Connect status updates to GUI
        set_callback(self._on_status_update)

    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header with title
        header = QLabel("PeakCut")
        header.setProperty("class", "title")
        header.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-family: 'SF Pro Display', sans-serif;
            font-size: 28px;
            font-weight: 700;
        """)
        main_layout.addWidget(header)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # Load Video button
        self.load_btn = QPushButton("Video laden")
        self.load_btn.setProperty("class", "primary")
        self.load_btn.setMinimumWidth(120)
        self.load_btn.clicked.connect(self._on_load_video)
        button_layout.addWidget(self.load_btn)

        # Analyze button
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setMinimumWidth(100)
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.analyze_btn.setEnabled(False)
        button_layout.addWidget(self.analyze_btn)

        # Export button
        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumWidth(100)
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Video preview area (placeholder)
        self.preview_frame = QFrame()
        self.preview_frame.setProperty("class", "card")
        self.preview_frame.setMinimumHeight(400)
        self.preview_frame.setStyleSheet(f"""
            QFrame[class="card"] {{
                background-color: #1a1a1a;
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)

        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Willkommen bei PeakCut\n\nKlicke 'Video laden' um zu starten")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-family: 'SF Pro Display', 'SF Pro Text', -apple-system, sans-serif;
                font-size: 18px;
                font-weight: 500;
                padding: 20px;
            }
        """)
        preview_layout.addWidget(self.status_label)

        main_layout.addWidget(self.preview_frame, stretch=1)

        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.back_btn = QPushButton("Back")
        self.back_btn.setEnabled(False)
        self.back_btn.clicked.connect(self._on_back)
        controls_layout.addWidget(self.back_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.play_btn.setProperty("class", "primary")
        self.play_btn.clicked.connect(self._on_play)
        controls_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        controls_layout.addWidget(self.stop_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next)
        controls_layout.addWidget(self.next_btn)

        controls_layout.addSpacing(20)

        self.switch_btn = QPushButton("Switch")
        self.switch_btn.setEnabled(False)
        self.switch_btn.clicked.connect(self._on_switch)
        controls_layout.addWidget(self.switch_btn)

        self.ignore_btn = QPushButton("Ignore")
        self.ignore_btn.setEnabled(False)
        self.ignore_btn.clicked.connect(self._on_ignore)
        controls_layout.addWidget(self.ignore_btn)

        controls_layout.addStretch()

        self.mode_label = QLabel("Mode: -")
        self.mode_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        controls_layout.addWidget(self.mode_label)

        controls_layout.addSpacing(10)

        self.peak_label = QLabel("Peak: - / -")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        controls_layout.addWidget(self.peak_label)

        main_layout.addLayout(controls_layout)

    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        # Keep status bar empty/minimal
        self.statusbar.showMessage("")

    def _on_load_video(self):
        """Check MATERIAL_DIR for files and show status."""
        if not os.path.exists(MATERIAL_DIR):
            self.statusbar.showMessage(f"Fehler: {MATERIAL_DIR} nicht gefunden")
            return

        files = os.listdir(MATERIAL_DIR)
        if not files:
            self.statusbar.showMessage("Material-Ordner ist leer")
            self._log("Keine Dateien in 1 Material/")
            return

        # Categorize files
        keyboard_files = [f for f in files if any(kw in f.lower() for kw in ["keyboard", "keys", "klavier"])]
        video_files = [f for f in files if f.lower().endswith(('.mp4', '.mov'))]
        audio_files = [f for f in files if f.lower().endswith(('.wav', '.mp3'))]

        # Build status message
        status_parts = []
        if keyboard_files:
            status_parts.append(f"Keyboard: {keyboard_files[0]}")
        if video_files:
            status_parts.append(f"{len(video_files)} Video(s)")
        if audio_files:
            status_parts.append(f"{len(audio_files)} Audio(s)")

        if keyboard_files:
            self.statusbar.showMessage(" | ".join(status_parts))
            self._log("Dateien gefunden\n\n" + "\n".join(status_parts) + "\n\nKlicke 'Analyze'")
            self.analyze_btn.setEnabled(True)
        else:
            self.statusbar.showMessage("Keine Keyboard-Datei gefunden")
            self._log("Keine Keyboard-Datei gefunden\n\n(Name muss 'keyboard', 'keys'\noder 'klavier' enthalten)")

    def _on_analyze(self):
        """Run sync and peak analysis."""
        self.statusbar.showMessage("Sync läuft...")
        self.analyze_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            # Run sync (for videos)
            run_sync()

            self.statusbar.showMessage("Peak-Analyse läuft...")
            QApplication.processEvents()

            # Run peak analysis
            run_peak_analysis()

            # Get results
            peaks = get_peaks()
            num_peaks = len(peaks)

            if num_peaks > 0:
                self._num_peaks = num_peaks
                self._current_peak = 0
                self._enable_playback_controls(True)
                self._update_peak_label()
                self.mode_label.setText(f"Mode: {get_mode().upper()}")
                self.statusbar.showMessage(f"Analyse fertig: {num_peaks} Peaks gefunden")
            else:
                self.statusbar.showMessage("Keine Peaks gefunden")
                self._log("Keine Peaks gefunden")

        except Exception as e:
            self.statusbar.showMessage(f"Fehler: {str(e)}")
            self._log(f"Fehler bei Analyse: {str(e)}")

        self.analyze_btn.setEnabled(True)

    def _on_export(self):
        """Run export."""
        stop_playback()
        self.statusbar.showMessage("Export läuft...")
        self.export_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            run_export()
            self.statusbar.showMessage(f"Export fertig! Dateien in: {EXPORT_DIR}")
        except Exception as e:
            self.statusbar.showMessage(f"Export-Fehler: {str(e)}")
            self._log(f"Export-Fehler: {str(e)}")

        self.export_btn.setEnabled(True)

    def _enable_playback_controls(self, enabled):
        """Enable or disable playback controls."""
        self.export_btn.setEnabled(enabled)
        self.back_btn.setEnabled(enabled)
        self.play_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(enabled)
        self.next_btn.setEnabled(enabled)
        self.switch_btn.setEnabled(enabled)
        self.ignore_btn.setEnabled(enabled)

    def _update_peak_label(self):
        """Update the peak counter label."""
        self.peak_label.setText(f"Peak: {self._current_peak + 1} / {self._num_peaks}")

    def _on_play(self):
        """Play current peak."""
        play_current_peak()
        self.statusbar.showMessage(f"Playing peak {self._current_peak + 1}")

    def _on_stop(self):
        """Stop playback."""
        stop_playback()
        self.statusbar.showMessage("Stopped")

    def _on_back(self):
        """Go to previous peak."""
        if self._current_peak > 0:
            self._current_peak -= 1
            go_back()
            self._update_peak_label()
            self.statusbar.showMessage(f"Peak {self._current_peak + 1}")

    def _on_next(self):
        """Go to next peak."""
        if self._current_peak < self._num_peaks - 1:
            self._current_peak += 1
            go_forward()
            self._update_peak_label()
            self.statusbar.showMessage(f"Peak {self._current_peak + 1}")

    def _on_switch(self):
        """Switch between keyboard and mic mode."""
        switch_mode()
        self.mode_label.setText(f"Mode: {get_mode().upper()}")
        self.statusbar.showMessage(f"Mode: {get_mode().upper()}")

    def _on_ignore(self):
        """Ignore current peak."""
        ignore_current_peak()
        self.statusbar.showMessage(f"Peak {self._current_peak + 1} ignored")

    def _log(self, message):
        """Show message in status label (replaces previous)."""
        self.status_label.setText(message)
        QApplication.processEvents()

    def _on_status_update(self, message):
        """Callback for status.py updates."""
        self._log(message)
