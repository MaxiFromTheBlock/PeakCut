# main_window.py - PeakCut Main Window (PyQt6)

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QTextEdit, QComboBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QThread, pyqtSignal

from .apple_style import get_stylesheet, COLORS
from .video_preview_peak import PeakVideoPreview

# Import new core modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import MATERIAL_DIR, EXPORT_DIR, LUTS_DIR
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.audio import stop_playback
from core.exporters import MP3Exporter, XMLExporter, TXTExporter


class AnalysisWorker(QThread):
    """Background worker for sync + peak analysis."""
    finished = pyqtSignal()            # session has all data
    error = pyqtSignal(str)            # error message

    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            self.session.analyze()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """PeakCut Main Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)

        # Session (created on analyze)
        self.session = None

        # File selection state (before session exists)
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

        self._setup_ui()
        self._setup_statusbar()

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
        self.video_preview.clip_in_changed.connect(self._on_clip_in_changed)
        self.video_preview.clip_out_changed.connect(self._on_clip_out_changed)
        self.preview_stack.addWidget(self.video_preview)

        # Start with status page
        self.preview_stack.setCurrentIndex(0)

        main_layout.addWidget(self.preview_stack, stretch=1)

        # Peak controls (hidden until analysis complete)
        self.peak_controls = QWidget()
        peak_layout = QHBoxLayout(self.peak_controls)
        peak_layout.setContentsMargins(0, 0, 0, 0)
        peak_layout.setSpacing(8)

        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._on_back)
        peak_layout.addWidget(self.back_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setProperty("class", "primary")
        self.play_btn.clicked.connect(self._on_play)
        peak_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        peak_layout.addWidget(self.stop_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._on_next)
        peak_layout.addWidget(self.next_btn)

        peak_layout.addSpacing(20)

        self.switch_btn = QPushButton("Switch")
        self.switch_btn.clicked.connect(self._on_switch)
        peak_layout.addWidget(self.switch_btn)

        self.ignore_btn = QPushButton("Ignore")
        self.ignore_btn.clicked.connect(self._on_ignore)
        peak_layout.addWidget(self.ignore_btn)

        peak_layout.addSpacing(20)

        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._on_export)
        peak_layout.addWidget(self.export_btn)

        peak_layout.addStretch()

        self.mode_label = QLabel("Mode: -")
        self.mode_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        peak_layout.addWidget(self.mode_label)

        peak_layout.addSpacing(10)

        self.peak_label = QLabel("Peak: - / -")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        peak_layout.addWidget(self.peak_label)

        self.peak_controls.hide()
        main_layout.addWidget(self.peak_controls)

        # Tools row (Screenshot + LUT, visible when video loaded)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)

        self.screenshot_btn = QPushButton("Screenshot")
        self.screenshot_btn.setEnabled(False)
        self.screenshot_btn.clicked.connect(self._on_capture_screenshot)
        tools_layout.addWidget(self.screenshot_btn)

        tools_layout.addStretch()

        # LUT dropdown
        lut_label = QLabel("LUT:")
        lut_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        tools_layout.addWidget(lut_label)

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
        tools_layout.addWidget(self.lut_combo)

        main_layout.addLayout(tools_layout)

    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("")

    def _on_load_files(self):
        """Open file dialog for multi-file selection."""
        last_folder = self._settings.value("last_folder", MATERIAL_DIR)
        if not os.path.exists(last_folder):
            last_folder = MATERIAL_DIR

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Dateien auswählen",
            last_folder,
            "Media Files (*.wav *.mp3 *.mp4 *.mov);;Audio (*.wav *.mp3);;Video (*.mp4 *.mov);;All Files (*)"
        )

        if not files:
            return

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
                if any(kw in filename for kw in ["keyboard", "keys", "klavier"]):
                    self._keyboard_file = filepath

        for f in audio_files:
            if f != self._keyboard_file:
                self._mic_files.append(f)

        self._update_file_display()

    def _update_file_display(self):
        """Update UI based on categorized files."""
        status_parts = []

        if self._keyboard_file:
            status_parts.append(f"Keyboard: {os.path.basename(self._keyboard_file)}")
        if self._mic_files:
            status_parts.append(f"{len(self._mic_files)} Mic(s)")
        if self._video_files:
            status_parts.append(f"{len(self._video_files)} Video(s)")

        audio_files = [f for f in self._selected_files if f.lower().endswith(('.wav', '.mp3'))]

        if not self._keyboard_file and audio_files:
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

                if self._video_files:
                    self.video_preview.set_videos(self._video_files)
                    self.preview_stack.setCurrentIndex(1)
                    self.screenshot_btn.setEnabled(True)
            elif not audio_files:
                self.statusbar.showMessage("Keine Audio-Dateien ausgewählt")
                self._log("Keine Audio-Dateien gefunden\n\nBitte wähle mindestens\neine .wav oder .mp3 Datei")
                self.analyze_btn.setEnabled(False)

    def _on_keyboard_selected(self, index):
        """Handle manual keyboard track selection."""
        filepath = self.keyboard_combo.currentData()
        if filepath:
            self._keyboard_file = filepath
            self._mic_files = [f for f in self._selected_files
                             if f.lower().endswith(('.wav', '.mp3')) and f != filepath]
            self.keyboard_row.hide()
            self._update_file_display()

    def _copy_files_to_material(self):
        """Copy selected files to MATERIAL_DIR for processing (if not already there)."""
        import shutil

        if not os.path.exists(MATERIAL_DIR):
            os.makedirs(MATERIAL_DIR)

        all_in_material = all(
            os.path.dirname(os.path.abspath(f)) == os.path.abspath(MATERIAL_DIR)
            for f in self._selected_files
        )

        if all_in_material:
            return

        for filepath in self._selected_files:
            src_abs = os.path.abspath(filepath)
            dest = os.path.join(MATERIAL_DIR, os.path.basename(filepath))
            dest_abs = os.path.abspath(dest)

            if src_abs != dest_abs:
                shutil.copy2(filepath, dest)

    def _on_analyze(self):
        """Run sync and peak analysis in background thread."""
        self.analyze_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.statusbar.showMessage("Analyse läuft...")

        # Start button text animation
        self._progress_dots = 0
        self._progress_timer.start(400)

        # Create project and session
        project = PeakCutProject(MATERIAL_DIR, EXPORT_DIR)
        project.set_files(self._keyboard_file, self._mic_files, self._video_files)

        self.session = PeakCutSession(project, config.load())
        self.session.status_update.connect(self._on_analysis_status)

        # Start background worker
        self._worker = AnalysisWorker(self.session)
        self._worker.finished.connect(self._on_analysis_complete)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_status(self, message):
        """Handle status updates from session."""
        self.statusbar.showMessage(message)

    def _on_analysis_complete(self):
        """Handle completed analysis - set peaks and enable controls."""
        self._progress_timer.stop()
        self.analyze_btn.setText("Analyze")

        peaks = self.session.peaks
        num_peaks = len(peaks)

        if num_peaks > 0:
            self._enable_playback_controls(True)
            self._update_peak_label()
            self.mode_label.setText(f"Mode: {self.session.mode.upper()}")

            if self._video_files:
                self.video_preview.set_peaks(
                    [p.position_ms for p in peaks], self.session.current_peak)
                peak = peaks[self.session.current_peak]
                self.video_preview.set_clip_region(
                    peak.in_point_ms, peak.out_point_ms)
                self.preview_stack.setCurrentIndex(1)
                self.statusbar.showMessage(f"{num_peaks} Peaks gefunden")
            else:
                self._log(f"{num_peaks} Peaks gefunden\n\nDrücke Play oder Leertaste")
        else:
            self._log("Keine Peaks gefunden")
            self.statusbar.showMessage("Keine Peaks gefunden")

        self.analyze_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self._worker = None

    def _on_analysis_error(self, error_msg):
        """Handle analysis errors."""
        self._progress_timer.stop()
        self.analyze_btn.setText("Analyze")
        self._log(f"Fehler: {error_msg}")
        self.statusbar.showMessage(f"Fehler: {error_msg}")
        self.analyze_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self._worker = None

    def _on_peak_clicked(self, peak_index):
        """Handle click on peak marker in timeline."""
        if self.session and 0 <= peak_index < len(self.session.peaks):
            self.session.set_current_peak(peak_index)
            self._update_peak_label()
            self.session.play_current()
            peak = self.session.peaks[peak_index]
            self.video_preview.set_clip_region(
                peak.in_point_ms, peak.out_point_ms)
            self.statusbar.showMessage(f"Peak {peak_index + 1}")

    def _on_clip_in_changed(self, ms):
        """Handle clip In-point change from timeline drag."""
        if self.session:
            self.session.adjust_clip(self.session.current_peak, in_ms=ms)

    def _on_clip_out_changed(self, ms):
        """Handle clip Out-point change from timeline drag."""
        if self.session:
            self.session.adjust_clip(self.session.current_peak, out_ms=ms)

    def _on_export(self):
        """Run export via pluggable exporters."""
        stop_playback()
        self.statusbar.showMessage("Export läuft...")
        self.export_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
            for exporter in exporters:
                exporter.export(self.session)
            self.statusbar.showMessage(f"Export fertig! Dateien in: {EXPORT_DIR}")
        except Exception as e:
            self.statusbar.showMessage(f"Export-Fehler: {str(e)}")
            self._log(f"Export-Fehler: {str(e)}")

        self.export_btn.setEnabled(True)

    def _enable_playback_controls(self, enabled):
        """Show or hide peak playback controls."""
        self.peak_controls.setVisible(enabled)

    def _update_peak_label(self):
        """Update the peak counter label."""
        if self.session:
            self.peak_label.setText(
                f"Peak: {self.session.current_peak + 1} / {len(self.session.peaks)}")

    def _on_play(self):
        """Play current peak."""
        if self.session:
            self.session.play_current()
            self.statusbar.showMessage(f"Playing peak {self.session.current_peak + 1}")

    def _on_stop(self):
        """Stop playback."""
        stop_playback()
        self.statusbar.showMessage("Stopped")

    def _on_back(self):
        """Go to previous peak."""
        if self.session and self.session.current_peak > 0:
            self.session.prev_peak()
            self._update_peak_label()
            self._update_video_preview_peak()
            self.statusbar.showMessage(f"Peak {self.session.current_peak + 1}")

    def _on_next(self):
        """Go to next peak."""
        if self.session and self.session.current_peak < len(self.session.peaks) - 1:
            self.session.next_peak()
            self._update_peak_label()
            self._update_video_preview_peak()
            self.statusbar.showMessage(f"Peak {self.session.current_peak + 1}")

    def _update_video_preview_peak(self):
        """Update video preview to show current peak."""
        if self.session and self._video_files and self.preview_stack.currentIndex() == 1:
            self.video_preview.set_current_peak(self.session.current_peak)
            if self.session.peaks and self.session.current_peak < len(self.session.peaks):
                peak = self.session.peaks[self.session.current_peak]
                self.video_preview.set_position(peak.position_ms)
                self.video_preview.set_clip_region(
                    peak.in_point_ms, peak.out_point_ms)

    def _on_switch(self):
        """Switch between keyboard and mic mode."""
        if self.session:
            self.session.switch_mode()
            self.mode_label.setText(f"Mode: {self.session.mode.upper()}")
            self.statusbar.showMessage(f"Mode: {self.session.mode.upper()}")

    def _on_ignore(self):
        """Ignore current peak."""
        if self.session:
            self.session.ignore_peak()
            self.statusbar.showMessage(f"Peak {self.session.current_peak + 1} ignored")

    def _populate_lut_combo(self):
        """Fill LUT dropdown from luts/ library directory."""
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()

        current_lut = config.get("lut_path") or ""

        if current_lut and os.sep in current_lut:
            self._migrate_lut_path(current_lut)
            current_lut = config.get("lut_path") or ""

        self.lut_combo.addItem("Kein LUT", "")

        os.makedirs(LUTS_DIR, exist_ok=True)
        lut_files = sorted(
            f for f in os.listdir(LUTS_DIR)
            if f.lower().endswith('.cube')
        )

        selected_index = 0
        for i, filename in enumerate(lut_files):
            name = os.path.splitext(filename)[0]
            self.lut_combo.addItem(name, filename)
            if filename == current_lut:
                selected_index = i + 1

        self.lut_combo.addItem("LUT importieren...", "__browse__")

        self.lut_combo.setCurrentIndex(selected_index)
        self.lut_combo.blockSignals(False)

    def _migrate_lut_path(self, full_path):
        """Migrate old full-path lut_path to library filename."""
        import shutil
        if os.path.isfile(full_path):
            os.makedirs(LUTS_DIR, exist_ok=True)
            filename = os.path.basename(full_path)
            dest = os.path.join(LUTS_DIR, filename)
            if not os.path.exists(dest):
                shutil.copy2(full_path, dest)
            config.set("lut_path", filename)
        else:
            config.set("lut_path", "")

    def _on_lut_selected(self, index):
        """Handle LUT selection from dropdown."""
        import shutil
        data = self.lut_combo.currentData()
        if data is None:
            return

        if data == "__browse__":
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "LUT importieren",
                os.path.expanduser("~/Downloads"),
                "LUT Files (*.cube);;All Files (*)"
            )
            if filepath:
                os.makedirs(LUTS_DIR, exist_ok=True)
                filename = os.path.basename(filepath)
                dest = os.path.join(LUTS_DIR, filename)
                if not os.path.exists(dest):
                    shutil.copy2(filepath, dest)
                config.set("lut_path", filename)
                self._populate_lut_combo()
                self.video_preview.refresh_lut()
                name = os.path.splitext(filename)[0]
                self.statusbar.showMessage(f"LUT importiert: {name}")
            else:
                self._populate_lut_combo()
        else:
            config.set("lut_path", data)
            self.video_preview.refresh_lut()
            if data:
                name = os.path.splitext(data)[0]
                self.statusbar.showMessage(f"LUT: {name}")
            else:
                self.statusbar.showMessage("LUT deaktiviert")

    def _on_capture_screenshot(self):
        """Capture screenshot of current video frame with LUT."""
        self.statusbar.showMessage("Screenshot wird erstellt...")
        QApplication.processEvents()

        camera_name = self.video_preview.get_current_camera_name()
        filepath = self.video_preview.capture_screenshot(camera_name)
        if filepath:
            self.statusbar.showMessage(f"Screenshot gespeichert: {os.path.basename(filepath)}")
        else:
            self.statusbar.showMessage("Screenshot fehlgeschlagen")

    def _log(self, message):
        """Show message in status label (replaces previous)."""
        self.status_label.setText(message)
        QApplication.processEvents()

    def _animate_progress(self):
        """Animate the analyze button text with dots."""
        dots = "." * (self._progress_dots % 3 + 1)
        self.analyze_btn.setText(f"Analysiere{dots}")
        self._progress_dots += 1

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()

        if key == Qt.Key.Key_Right:
            if self.session and self.session.peaks:
                self._on_next()
            return

        if key == Qt.Key.Key_Left:
            if self.session and self.session.peaks:
                self._on_back()
            return

        super().keyPressEvent(event)
