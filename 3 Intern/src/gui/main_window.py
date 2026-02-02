# main_window.py - PeakCut Main Window (PyQt6)

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QTextEdit, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QSettings

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
        self._is_playing = False

        # File selection state
        self._selected_files = []
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        # Settings for remembering last folder
        self._settings = QSettings("PeakCut", "PeakCut")

        # Progress animation
        self._progress_timer = QTimer()
        self._progress_timer.timeout.connect(self._animate_progress)
        self._progress_dots = 0
        self._progress_text = ""

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

        # Load Files button
        self.load_btn = QPushButton("Dateien wählen")
        self.load_btn.setProperty("class", "primary")
        self.load_btn.setMinimumWidth(140)
        self.load_btn.clicked.connect(self._on_load_files)
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

        # Keyboard selection row (initially hidden)
        self.keyboard_row = QWidget()
        keyboard_layout = QHBoxLayout(self.keyboard_row)
        keyboard_layout.setContentsMargins(0, 0, 0, 0)
        keyboard_layout.setSpacing(8)

        self.keyboard_label = QLabel("Keyboard-Spur:")
        self.keyboard_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        keyboard_layout.addWidget(self.keyboard_label)

        self.keyboard_combo = QComboBox()
        self.keyboard_combo.setMinimumWidth(300)
        self.keyboard_combo.currentIndexChanged.connect(self._on_keyboard_selected)
        keyboard_layout.addWidget(self.keyboard_combo)

        keyboard_layout.addStretch()
        self.keyboard_row.hide()
        main_layout.addWidget(self.keyboard_row)

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

    def _on_load_files(self):
        """Open file dialog for multi-file selection."""
        # Get last used folder from settings
        last_folder = self._settings.value("last_folder", MATERIAL_DIR)
        if not os.path.exists(last_folder):
            last_folder = MATERIAL_DIR

        # Open file dialog
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Dateien auswählen",
            last_folder,
            "Media Files (*.wav *.mp3 *.mp4 *.mov);;Audio (*.wav *.mp3);;Video (*.mp4 *.mov);;All Files (*)"
        )

        if not files:
            return  # User cancelled

        # Save folder for next time
        if files:
            folder = os.path.dirname(files[0])
            self._settings.setValue("last_folder", folder)

        self._selected_files = files
        self._categorize_files()

    def _categorize_files(self):
        """Categorize selected files by type."""
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        audio_files = []

        for filepath in self._selected_files:
            filename = os.path.basename(filepath).lower()

            if filename.endswith(('.mp4', '.mov')):
                self._video_files.append(filepath)
            elif filename.endswith(('.wav', '.mp3')):
                audio_files.append(filepath)
                # Auto-detect keyboard track
                if any(kw in filename for kw in ["keyboard", "keys", "klavier"]):
                    self._keyboard_file = filepath

        # Separate mic files (all audio that's not keyboard)
        for f in audio_files:
            if f != self._keyboard_file:
                self._mic_files.append(f)

        self._update_file_display()

    def _update_file_display(self):
        """Update UI based on categorized files."""
        # Build status message
        status_parts = []

        if self._keyboard_file:
            status_parts.append(f"Keyboard: {os.path.basename(self._keyboard_file)}")
        if self._mic_files:
            status_parts.append(f"{len(self._mic_files)} Mic(s)")
        if self._video_files:
            status_parts.append(f"{len(self._video_files)} Video(s)")

        # Check if we need manual keyboard selection
        audio_files = [f for f in self._selected_files if f.lower().endswith(('.wav', '.mp3'))]

        if not self._keyboard_file and audio_files:
            # Show dropdown for manual selection
            self.keyboard_combo.clear()
            self.keyboard_combo.addItem("-- Bitte wählen --", None)
            for f in audio_files:
                self.keyboard_combo.addItem(os.path.basename(f), f)
            self.keyboard_row.show()
            self._log("Keyboard-Spur nicht erkannt\n\nBitte wähle die Keyboard-Spur\naus dem Dropdown-Menü")
            self.statusbar.showMessage("Keyboard-Spur auswählen")
            self.analyze_btn.setEnabled(False)
        else:
            self.keyboard_row.hide()

            if self._keyboard_file:
                self.statusbar.showMessage(" | ".join(status_parts))
                self._log("Dateien geladen\n\n" + "\n".join(status_parts) + "\n\nKlicke 'Analyze'")
                self.analyze_btn.setEnabled(True)
                self._copy_files_to_material()
            elif not audio_files:
                self.statusbar.showMessage("Keine Audio-Dateien ausgewählt")
                self._log("Keine Audio-Dateien gefunden\n\nBitte wähle mindestens\neine .wav oder .mp3 Datei")
                self.analyze_btn.setEnabled(False)

    def _on_keyboard_selected(self, index):
        """Handle manual keyboard track selection."""
        filepath = self.keyboard_combo.currentData()
        if filepath:
            self._keyboard_file = filepath
            # Update mic files (remove keyboard from list)
            self._mic_files = [f for f in self._selected_files
                             if f.lower().endswith(('.wav', '.mp3')) and f != filepath]
            self.keyboard_row.hide()
            self._update_file_display()

    def _copy_files_to_material(self):
        """Copy selected files to MATERIAL_DIR for processing (if not already there)."""
        import shutil

        # Ensure material dir exists
        if not os.path.exists(MATERIAL_DIR):
            os.makedirs(MATERIAL_DIR)

        # Check if ALL files are already in MATERIAL_DIR
        all_in_material = all(
            os.path.dirname(os.path.abspath(f)) == os.path.abspath(MATERIAL_DIR)
            for f in self._selected_files
        )

        if all_in_material:
            # Files already in Material folder, don't touch anything
            return

        # Files from outside - copy them (don't delete existing files)
        for filepath in self._selected_files:
            src_abs = os.path.abspath(filepath)
            dest = os.path.join(MATERIAL_DIR, os.path.basename(filepath))
            dest_abs = os.path.abspath(dest)

            # Only copy if source is different from destination
            if src_abs != dest_abs:
                shutil.copy2(filepath, dest)

    def _on_analyze(self):
        """Run sync and peak analysis."""
        self.analyze_btn.setEnabled(False)
        self._log("Synchronisiere...")
        QApplication.processEvents()

        try:
            # Run sync (for videos)
            run_sync()

            self._log("Analysiere Peaks...")
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
                self._log(f"{num_peaks} Peaks gefunden\n\nDrücke Play oder Leertaste")
            else:
                self._log("Keine Peaks gefunden")

        except Exception as e:
            self._log(f"Fehler: {str(e)}")

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

    def _start_progress(self, text):
        """Start animated progress indicator."""
        self._progress_text = text
        self._progress_dots = 0
        self._animate_progress()
        self._progress_timer.start(400)

    def _stop_progress(self):
        """Stop progress indicator."""
        self._progress_timer.stop()

    def _animate_progress(self):
        """Animate the progress dots."""
        dots = "." * (self._progress_dots % 4)
        self.status_label.setText(f"{self._progress_text}{dots}")
        self._progress_dots += 1

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()

        # Space → Play/Stop toggle
        if key == Qt.Key.Key_Space:
            if self._num_peaks > 0:
                if self._is_playing:
                    self._on_stop()
                    self._is_playing = False
                else:
                    self._on_play()
                    self._is_playing = True
            return

        # Right arrow → Next
        if key == Qt.Key.Key_Right:
            if self._num_peaks > 0:
                self._on_next()
            return

        # Left arrow → Back
        if key == Qt.Key.Key_Left:
            if self._num_peaks > 0:
                self._on_back()
            return

        # S → Switch mode
        if key == Qt.Key.Key_S:
            if self._num_peaks > 0:
                self._on_switch()
            return

        # I or Delete → Ignore
        if key in (Qt.Key.Key_I, Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._num_peaks > 0:
                self._on_ignore()
            return

        # E → Export
        if key == Qt.Key.Key_E:
            if self.export_btn.isEnabled():
                self._on_export()
            return

        super().keyPressEvent(event)
