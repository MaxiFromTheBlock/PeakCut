# main_window.py - PeakCut Main Window (PyQt6)

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QTextEdit, QComboBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QSettings

from .apple_style import get_stylesheet, COLORS
from .video_preview_peak import PeakVideoPreview

# Import PeakCut core modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import MATERIAL_DIR, EXPORT_DIR
from sync import run_sync
from peaks import (
    run_peak_analysis, get_peaks, get_mode,
    play_current_peak, go_back, go_forward,
    stop_playback, switch_mode, ignore_current_peak,
    get_current_peak_index, set_current_peak
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

        # Stacked widget for status/video preview
        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumHeight(400)

        # Page 0: Status display (welcome/progress messages)
        self.status_frame = QFrame()
        self.status_frame.setProperty("class", "card")
        self.status_frame.setStyleSheet(f"""
            QFrame[class="card"] {{
                background-color: #1a1a1a;
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Willkommen bei PeakCut\n\nKlicke 'Dateien wählen' um zu starten")
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
        status_layout.addWidget(self.status_label)
        self.preview_stack.addWidget(self.status_frame)

        # Page 1: Video preview with peak timeline
        self.video_preview = PeakVideoPreview()
        self.video_preview.peak_clicked.connect(self._on_peak_clicked)
        self.preview_stack.addWidget(self.video_preview)

        # Start with status page
        self.preview_stack.setCurrentIndex(0)

        main_layout.addWidget(self.preview_stack, stretch=1)

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

        controls_layout.addSpacing(20)

        self.screenshot_btn = QPushButton("Screenshot")
        self.screenshot_btn.setEnabled(False)
        self.screenshot_btn.clicked.connect(self._on_capture_screenshot)
        controls_layout.addWidget(self.screenshot_btn)

        controls_layout.addStretch()

        # LUT dropdown
        lut_label = QLabel("LUT:")
        lut_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        controls_layout.addWidget(lut_label)

        self.lut_combo = QComboBox()
        self.lut_combo.setMinimumWidth(160)
        self.lut_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; padding-right: 6px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                selection-background-color: #007AFF;
            }}
        """)
        self._populate_lut_combo()
        self.lut_combo.currentIndexChanged.connect(self._on_lut_selected)
        controls_layout.addWidget(self.lut_combo)

        controls_layout.addSpacing(20)

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

                # Show video preview if videos available
                if self._video_files:
                    self._setup_video_preview(peaks)
                    self.preview_stack.setCurrentIndex(1)
                else:
                    self._log(f"{num_peaks} Peaks gefunden\n\nDrücke Play oder Leertaste")
            else:
                self._log("Keine Peaks gefunden")

        except Exception as e:
            self._log(f"Fehler: {str(e)}")

        self.analyze_btn.setEnabled(True)

    def _setup_video_preview(self, peaks):
        """Setup video preview with peaks."""
        # Load videos into preview
        self.video_preview.set_videos(self._video_files)

        # peaks from peaks.py are already in milliseconds
        self.video_preview.set_peaks(peaks, self._current_peak)

    def _on_peak_clicked(self, peak_index):
        """Handle click on peak marker in timeline."""
        if 0 <= peak_index < self._num_peaks:
            self._current_peak = peak_index
            set_current_peak(peak_index)  # Sync with peaks.py
            self._update_peak_label()
            play_current_peak()
            self.statusbar.showMessage(f"Peak {peak_index + 1}")

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
        self.screenshot_btn.setEnabled(enabled and bool(self._video_files))

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
            self._update_video_preview_peak()
            self.statusbar.showMessage(f"Peak {self._current_peak + 1}")

    def _on_next(self):
        """Go to next peak."""
        if self._current_peak < self._num_peaks - 1:
            self._current_peak += 1
            go_forward()
            self._update_peak_label()
            self._update_video_preview_peak()
            self.statusbar.showMessage(f"Peak {self._current_peak + 1}")

    def _update_video_preview_peak(self):
        """Update video preview to show current peak."""
        if self._video_files and self.preview_stack.currentIndex() == 1:
            self.video_preview.set_current_peak(self._current_peak)
            # Also seek video to peak position
            peaks = get_peaks()
            if peaks and self._current_peak < len(peaks):
                self.video_preview.set_position(peaks[self._current_peak])

    def _on_switch(self):
        """Switch between keyboard and mic mode."""
        switch_mode()
        self.mode_label.setText(f"Mode: {get_mode().upper()}")
        self.statusbar.showMessage(f"Mode: {get_mode().upper()}")

    def _on_ignore(self):
        """Ignore current peak."""
        ignore_current_peak()
        self.statusbar.showMessage(f"Peak {self._current_peak + 1} ignored")

    def _populate_lut_combo(self):
        """Fill LUT dropdown with recent LUTs + browse option."""
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()

        current_lut = config.get("lut_path") or ""
        recent_luts = config.get("lut_recent") or []

        self.lut_combo.addItem("Kein LUT", "")

        selected_index = 0
        for i, path in enumerate(recent_luts):
            name = os.path.splitext(os.path.basename(path))[0]
            self.lut_combo.addItem(name, path)
            if path == current_lut:
                selected_index = i + 1  # +1 for "Kein LUT"

        self.lut_combo.addItem("LUT wählen...", "__browse__")

        self.lut_combo.setCurrentIndex(selected_index)
        self.lut_combo.blockSignals(False)

    def _on_lut_selected(self, index):
        """Handle LUT selection from dropdown."""
        data = self.lut_combo.currentData()
        if data is None:
            return

        if data == "__browse__":
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "LUT wählen",
                os.path.expanduser("~/Downloads"),
                "LUT Files (*.cube);;All Files (*)"
            )
            if filepath:
                # Add to recent list
                recent = config.get("lut_recent") or []
                if filepath in recent:
                    recent.remove(filepath)
                recent.insert(0, filepath)
                recent = recent[:10]  # Keep max 10
                config.set("lut_recent", recent)
                config.set("lut_path", filepath)
                self._populate_lut_combo()
                name = os.path.splitext(os.path.basename(filepath))[0]
                self.statusbar.showMessage(f"LUT: {name}")
            else:
                # User cancelled - revert to previous selection
                self._populate_lut_combo()
        else:
            config.set("lut_path", data)
            if data:
                name = os.path.splitext(os.path.basename(data))[0]
                self.statusbar.showMessage(f"LUT: {name}")
            else:
                self.statusbar.showMessage("LUT deaktiviert")

    def _on_capture_screenshot(self):
        """Capture screenshot of current video frame with LUT."""
        self.statusbar.showMessage("Screenshot wird erstellt...")
        QApplication.processEvents()

        filepath = self.video_preview.capture_screenshot()
        if filepath:
            self.statusbar.showMessage(f"Screenshot gespeichert: {os.path.basename(filepath)}")
        else:
            self.statusbar.showMessage("Screenshot fehlgeschlagen")

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

        super().keyPressEvent(event)
