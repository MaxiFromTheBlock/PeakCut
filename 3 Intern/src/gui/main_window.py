# main_window.py - PeakCut Main Window (Simplified: Welcome → Analysis → Review)

import os
import sys
import json
import subprocess
import queue
import threading

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QComboBox, QStackedWidget, QInputDialog,
    QSlider,
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer

from .apple_style import COLORS, get_stylesheet
from .video_preview_peak import PeakVideoPreview

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import APP_DIR, EXPORT_DIR, LUTS_DIR, TEMP_DIR, ms_to_mmss
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.audio import stop_playback, is_playing
from core.exporters import MP3Exporter, XMLExporter, TXTExporter


_ANALYSIS_TIMEOUT_S = 600  # 10 minutes max


class AnalysisWorker(QThread):
    """Runs analysis in separate process with timeout protection."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self._process = None

    def run(self):
        project = self.session.project

        # Pre-flight: verify all files exist
        all_files = project.get_all_file_paths()
        for f in all_files:
            if not os.path.exists(f):
                self.error.emit(f"Datei nicht gefunden: {os.path.basename(f)}")
                return

        cfg = self.session.config

        config_data = {
            "keyboard_track": project.keyboard_track,
            "mic_tracks": project.mic_tracks,
            "videos": project.videos,
            "reference_track": project.get_reference_track(),
            "temp_dir": TEMP_DIR,
            "export_dir": project.export_dir,
            "config": cfg
        }

        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(script_dir, "core", "analysis_process.py")
        python_exe = sys.executable

        try:
            self._process = subprocess.Popen(
                [python_exe, script_path, json.dumps(config_data)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=script_dir
            )

            # Watchdog: kill process if analysis takes too long
            watchdog = threading.Timer(
                _ANALYSIS_TIMEOUT_S,
                lambda: self._process.kill() if self._process and self._process.poll() is None else None
            )
            watchdog.daemon = True
            watchdog.start()

            stdout_queue = queue.Queue()

            def read_stdout():
                stdout_data = self._process.stdout.read()
                stdout_queue.put(stdout_data)

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()

            while True:
                line = self._process.stderr.readline()
                if not line and self._process.poll() is not None:
                    break
                line = line.strip()
                if line.startswith("PROGRESS: "):
                    self.progress.emit(line[10:])
                elif line.startswith("ERROR: "):
                    self.progress.emit(f"Fehler: {line[7:]}")

            watchdog.cancel()
            stdout_thread.join(timeout=10)
            try:
                stdout = stdout_queue.get(timeout=1)
            except queue.Empty:
                stdout = ""

            if self._process.returncode != 0:
                if self._process.returncode == -9:
                    self.error.emit("Analyse abgebrochen: Timeout (>10 Min)")
                else:
                    self.error.emit(f"Analyse-Prozess beendet mit Code {self._process.returncode}")
                return

            try:
                results = json.loads(stdout)
                if results.get("error"):
                    self.error.emit(results["error"])
                else:
                    self.finished.emit(results)
            except json.JSONDecodeError as e:
                self.error.emit(f"Ungültige Analyse-Ergebnisse: {e}")

        except Exception as e:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    self._process.kill()
            self.error.emit(f"Analyse fehlgeschlagen: {e}")


class ExportWorker(QThread):
    """Runs export in background thread to keep UI responsive."""
    finished = pyqtSignal(list)   # list of exported file paths
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            exported = []
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
            for exporter in exporters:
                result = exporter.export(self.session)
                if result:
                    self.progress.emit(f"Exportiert: {os.path.basename(result)}")
                    exported.append(result)
            self.finished.emit(exported)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """PeakCut Main Window — Simplified: Welcome → Analysis → Review"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        self.session = None
        self._worker = None
        self._export_worker = None
        self._is_playing = False

        # Playback poll timer
        self._play_timer = QTimer()
        self._play_timer.setInterval(200)
        self._play_timer.timeout.connect(self._poll_playback)

        # File state
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        self._settings = QSettings("PeakCut", "PeakCut")

        self._setup_ui()
        self.setStyleSheet(get_stylesheet())

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self._setup_welcome_page()    # 0
        self._setup_analysis_page()   # 1
        self._setup_review_page()     # 2

        self.stack.setCurrentIndex(0)

        # Status bar
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

    # ══════════════════════════════════════════════════════════════
    # PAGE 0: Welcome
    # ══════════════════════════════════════════════════════════════

    def _setup_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("PeakCut")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 48px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(40)

        btn = QPushButton("Import Files")
        btn.setProperty("class", "primary")
        btn.setMinimumWidth(180)
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._on_import)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════
    # PAGE 1: Analysis (wait screen)
    # ══════════════════════════════════════════════════════════════

    def _setup_analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.analysis_label = QLabel("Analyse läuft...")
        self.analysis_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px;")
        self.analysis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.analysis_label)

        layout.addSpacing(20)

        self.analysis_status = QLabel("Starte...")
        self.analysis_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        self.analysis_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.analysis_status)

        self.stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════
    # PAGE 2: Peak Review
    # ══════════════════════════════════════════════════════════════

    def _setup_review_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # Top bar: LUT + Camera selection
        top_bar = QHBoxLayout()

        # Camera selector (if videos)
        cam_label = QLabel("Kamera:")
        cam_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        top_bar.addWidget(cam_label)

        self.camera_combo = QComboBox()
        self.camera_combo.setEditable(True)
        self.camera_combo.setMinimumWidth(180)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self.camera_combo.lineEdit().editingFinished.connect(self._on_camera_name_edited)
        top_bar.addWidget(self.camera_combo)

        top_bar.addSpacing(20)

        # LUT selector
        lut_label = QLabel("LUT:")
        lut_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        top_bar.addWidget(lut_label)

        self.lut_combo = QComboBox()
        self.lut_combo.setMinimumWidth(150)
        self.lut_combo.currentIndexChanged.connect(self._on_lut_changed)
        top_bar.addWidget(self.lut_combo)

        top_bar.addSpacing(20)

        # Brightness slider (per camera)
        brightness_label = QLabel("Helligkeit:")
        brightness_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        top_bar.addWidget(brightness_label)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setFixedWidth(120)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        top_bar.addWidget(self.brightness_slider)

        self.brightness_value_label = QLabel("0")
        self.brightness_value_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.brightness_value_label.setMinimumWidth(30)
        top_bar.addWidget(self.brightness_value_label)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Video preview
        self.video_preview = PeakVideoPreview()
        self.video_preview.setMinimumHeight(350)
        layout.addWidget(self.video_preview, stretch=1)

        # Timeline slider
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(8)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        timeline_row.addWidget(self.position_slider)

        self.timecode_label = QLabel("0:00 / 0:00")
        self.timecode_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.timecode_label.setMinimumWidth(90)
        timeline_row.addWidget(self.timecode_label)

        layout.addLayout(timeline_row)

        self.video_preview.position_changed.connect(self._on_position_update)
        self.video_preview.duration_changed.connect(self._on_duration_update)

        # Peak controls
        controls = QHBoxLayout()
        controls.setSpacing(12)

        self.back_btn = QPushButton("◀ Zurück")
        self.back_btn.setMinimumWidth(90)
        self.back_btn.clicked.connect(self._on_back)
        controls.addWidget(self.back_btn)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setProperty("class", "primary")
        self.play_btn.setMinimumWidth(100)
        self.play_btn.clicked.connect(self._on_play)
        controls.addWidget(self.play_btn)

        self.next_btn = QPushButton("Weiter ▶")
        self.next_btn.setMinimumWidth(90)
        self.next_btn.clicked.connect(self._on_next)
        controls.addWidget(self.next_btn)

        controls.addSpacing(20)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #3a3a3a;")
        controls.addWidget(sep)

        controls.addSpacing(20)

        self.ignore_btn = QPushButton("Ignorieren")
        self.ignore_btn.clicked.connect(self._on_ignore)
        controls.addWidget(self.ignore_btn)

        controls.addSpacing(20)

        # Mode toggle
        self.mode_btn = QPushButton("Mode")
        self.mode_btn.clicked.connect(self._on_mode_toggle)
        controls.addWidget(self.mode_btn)

        controls.addStretch()

        # Peak counter
        self.peak_label = QLabel("Peak 1 / 10")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 16px;")
        controls.addWidget(self.peak_label)

        controls.addStretch()

        self.screenshot_btn = QPushButton("Screenshot")
        self.screenshot_btn.clicked.connect(self._on_screenshot)
        controls.addWidget(self.screenshot_btn)

        controls.addSpacing(20)

        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.setMinimumWidth(100)
        self.export_btn.clicked.connect(self._on_export)
        controls.addWidget(self.export_btn)

        layout.addLayout(controls)

        self.stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════
    # Import & Analysis
    # ══════════════════════════════════════════════════════════════

    def _on_import(self):
        last_folder = self._settings.value("last_folder", os.path.expanduser("~/Desktop"))
        if not os.path.exists(last_folder):
            last_folder = os.path.expanduser("~/Desktop")

        files, _ = QFileDialog.getOpenFileNames(
            self, "Dateien auswählen", last_folder,
            "Media Files (*.wav *.mp3 *.mp4 *.mov);;All Files (*)"
        )
        if not files:
            return

        self._settings.setValue("last_folder", os.path.dirname(files[0]))
        self._categorize_files(files)

        if not self._keyboard_file:
            audio_files = [f for f in files if f.lower().endswith(('.wav', '.mp3'))]
            if not audio_files:
                self.statusbar.showMessage("Keine Audio-Dateien gefunden")
                return
            items = [os.path.basename(f) for f in audio_files]
            item, ok = QInputDialog.getItem(
                self, "Keyboard-Spur wählen",
                "Welche Datei ist die Keyboard-Spur?",
                items, 0, False
            )
            if not ok:
                return
            idx = items.index(item)
            self._keyboard_file = audio_files[idx]
            self._mic_files = [f for f in audio_files if f != self._keyboard_file]

        self._start_analysis()

    def _categorize_files(self, files):
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        audio_files = []
        for filepath in files:
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

    def _start_analysis(self):
        self.stack.setCurrentIndex(1)  # Show analysis page
        self.analysis_status.setText("Starte Analyse...")

        project = PeakCutProject(EXPORT_DIR)
        project.set_files(self._keyboard_file, self._mic_files, self._video_files)

        self.session = PeakCutSession(project, config.load())

        self._worker = AnalysisWorker(self.session)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.start()

    def _on_analysis_progress(self, msg):
        self.analysis_status.setText(msg)

    def _on_analysis_done(self, results):
        self.session.load_analysis_results(results)

        num_peaks = len(self.session.peaks)
        if num_peaks == 0:
            self.analysis_label.setText("Keine Peaks gefunden")
            self.analysis_status.setText("Bitte andere Dateien importieren")
            return

        # Setup review page
        self._setup_review_data()
        self.stack.setCurrentIndex(2)  # Show review page
        self._navigate_to_peak(0)
        self.statusbar.showMessage(f"{num_peaks} Peaks gefunden")

    def _on_analysis_error(self, msg):
        self.analysis_label.setText("Fehler")
        self.analysis_status.setText(msg)

    # ══════════════════════════════════════════════════════════════
    # Review Page Setup
    # ══════════════════════════════════════════════════════════════

    def _setup_review_data(self):
        # Populate camera combo
        self.camera_combo.clear()
        for i, path in enumerate(self._video_files):
            name = os.path.splitext(os.path.basename(path))[0]
            self.camera_combo.addItem(f"{name}", path)

        if self._video_files:
            self.video_preview.set_videos(self._video_files)
            self.video_preview.set_session(self.session)
            self.video_preview.screenshot_done.connect(self._on_screenshot_done)

        # Populate LUT combo
        self._populate_lut_combo()

    def _populate_lut_combo(self):
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()
        self.lut_combo.addItem("Kein LUT", "")

        os.makedirs(LUTS_DIR, exist_ok=True)
        current_lut = config.get("lut_path") or ""

        lut_files = sorted(f for f in os.listdir(LUTS_DIR) if f.lower().endswith('.cube'))
        selected = 0
        for i, filename in enumerate(lut_files):
            name = os.path.splitext(filename)[0]
            self.lut_combo.addItem(name, filename)
            if filename == current_lut:
                selected = i + 1

        self.lut_combo.setCurrentIndex(selected)
        self.lut_combo.blockSignals(False)

    # ══════════════════════════════════════════════════════════════
    # Peak Navigation
    # ══════════════════════════════════════════════════════════════

    def _navigate_to_peak(self, index):
        if not self.session or not self.session.peaks:
            return
        if not (0 <= index < len(self.session.peaks)):
            return

        self.session.set_current_peak(index)
        peak = self.session.peaks[index]

        # Update label
        total = len(self.session.peaks)
        self.peak_label.setText(f"Peak {index + 1} / {total}")

        # Show video frame at peak position
        if self._video_files:
            self.video_preview.set_position(peak.position_ms)

        # Play audio
        self.session.play_current()
        self._start_play_state()

    def _on_back(self):
        if self.session and self.session.current_peak > 0:
            self._navigate_to_peak(self.session.current_peak - 1)

    def _on_next(self):
        if self.session and self.session.current_peak < len(self.session.peaks) - 1:
            self._navigate_to_peak(self.session.current_peak + 1)

    def _on_play(self):
        if not self.session:
            return
        if self._is_playing:
            stop_playback()
            self._stop_play_state()
        else:
            self.session.play_current()
            self._start_play_state()

    def _start_play_state(self):
        self._is_playing = True
        self.play_btn.setText("■ Stop")
        self._play_timer.start()

    def _stop_play_state(self):
        self._is_playing = False
        self.play_btn.setText("▶ Play")
        self._play_timer.stop()

    def _poll_playback(self):
        if not is_playing():
            self._stop_play_state()

    def _on_ignore(self):
        if not self.session:
            return
        self.session.ignore_peak()
        idx = self.session.current_peak
        self.statusbar.showMessage(f"Peak {idx + 1} ignoriert")
        # Auto-advance to next
        if idx < len(self.session.peaks) - 1:
            self._navigate_to_peak(idx + 1)

    def _on_mode_toggle(self):
        if self.session:
            self.session.switch_mode()
            mode_name = "Keyboard" if self.session.mode == "keyboard" else "Mikrofon"
            self.statusbar.showMessage(f"Mode: {mode_name}")
            self.session.play_current()
            self._start_play_state()

    # ══════════════════════════════════════════════════════════════
    # Screenshot
    # ══════════════════════════════════════════════════════════════

    def _on_screenshot(self):
        if not self._video_files:
            self.statusbar.showMessage("Keine Videos geladen")
            return
        camera_name = self.camera_combo.currentText()
        self.statusbar.showMessage("Screenshot wird erstellt...")
        self.video_preview.capture_screenshot_async(camera_name)

    def _on_screenshot_done(self, filepath):
        if filepath:
            self.statusbar.showMessage(f"Screenshot: {os.path.basename(filepath)}")
        else:
            self.statusbar.showMessage("Screenshot fehlgeschlagen")

    # ══════════════════════════════════════════════════════════════
    # Camera & LUT
    # ══════════════════════════════════════════════════════════════

    def _on_camera_changed(self, index):
        if 0 <= index < len(self._video_files):
            self.video_preview.load_video_at_index(index)
            # Load brightness for this camera
            brightness = self.video_preview.get_current_brightness()
            self.brightness_slider.blockSignals(True)
            self.brightness_slider.setValue(brightness)
            self.brightness_slider.blockSignals(False)
            self._update_brightness_label(brightness)
            # Re-show current peak position
            if self.session and self.session.peaks:
                peak = self.session.peaks[self.session.current_peak]
                self.video_preview.set_position(peak.position_ms)

    def _on_camera_name_edited(self):
        name = self.camera_combo.currentText().strip()
        if name:
            idx = self.camera_combo.currentIndex()
            self.camera_combo.setItemText(idx, name)
            self.video_preview.set_camera_name(name)

    def _on_lut_changed(self, index):
        data = self.lut_combo.currentData()
        if data is not None:
            config.set_value("lut_path", data)
            self.video_preview.refresh_lut()

    def _on_brightness_changed(self, value):
        self._update_brightness_label(value)
        self.video_preview.set_brightness(value)
        self.video_preview.refresh_lut()

    def _update_brightness_label(self, value):
        if value > 0:
            self.brightness_value_label.setText(f"+{value}")
        else:
            self.brightness_value_label.setText(str(value))

    # ══════════════════════════════════════════════════════════════
    # Timeline Slider
    # ══════════════════════════════════════════════════════════════

    def _on_slider_moved(self, value):
        self.video_preview.set_position(value)

    def _on_slider_pressed(self):
        self.video_preview.set_position(self.position_slider.value())

    def _on_position_update(self, position_ms):
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)
        duration_ms = self.position_slider.maximum()
        self.timecode_label.setText(
            f"{ms_to_mmss(position_ms)} / {ms_to_mmss(duration_ms)}"
        )

    def _on_duration_update(self, duration_ms):
        self.position_slider.setMaximum(duration_ms)
        self.timecode_label.setText(
            f"{ms_to_mmss(0)} / {ms_to_mmss(duration_ms)}"
        )

    # ══════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════

    def _on_export(self):
        if not self.session:
            return

        stop_playback()
        self.export_btn.setEnabled(False)
        self.statusbar.showMessage("Export läuft...")

        self._export_worker = ExportWorker(self.session)
        self._export_worker.progress.connect(lambda msg: self.statusbar.showMessage(msg))
        self._export_worker.finished.connect(self._on_export_done)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_done(self, exported):
        self.export_btn.setEnabled(True)
        self.statusbar.showMessage(f"Export fertig! {len(exported)} Dateien → {EXPORT_DIR}")
        self._export_worker.deleteLater()
        self._export_worker = None

    def _on_export_error(self, msg):
        self.export_btn.setEnabled(True)
        self.statusbar.showMessage(f"Export-Fehler: {msg}")
        self._export_worker.deleteLater()
        self._export_worker = None

    # ══════════════════════════════════════════════════════════════
    # Keyboard Shortcuts
    # ══════════════════════════════════════════════════════════════

    def keyPressEvent(self, event):
        key = event.key()

        if self.stack.currentIndex() != 2:  # Only in review mode
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Right:
            self._on_next()
        elif key == Qt.Key.Key_Left:
            self._on_back()
        elif key == Qt.Key.Key_Space:
            self._on_play()
        elif key == Qt.Key.Key_I or event.text() == 'i':
            self._on_ignore()
        elif key == Qt.Key.Key_S or event.text() == 's':
            self._on_screenshot()
        else:
            super().keyPressEvent(event)

    # ══════════════════════════════════════════════════════════════
    # Cleanup
    # ══════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        self._play_timer.stop()
        if hasattr(self, 'video_preview'):
            self.video_preview.cleanup()

        if self._worker:
            if hasattr(self._worker, '_process') and self._worker._process:
                if self._worker._process.poll() is None:
                    self._worker._process.terminate()
                    try:
                        self._worker._process.wait(timeout=2)
                    except Exception:
                        self._worker._process.kill()
            if self._worker.isRunning():
                self._worker.wait(3000)

        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.wait(3000)

        stop_playback()
        event.accept()
