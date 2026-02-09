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
    QProgressBar
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer

from .apple_style import get_stylesheet, COLORS
from .video_preview_peak import PeakVideoPreview

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils import MATERIAL_DIR, EXPORT_DIR, LUTS_DIR
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.audio import stop_playback
from core.exporters import MP3Exporter, XMLExporter, TXTExporter


class AnalysisWorker(QThread):
    """Runs analysis in separate process."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self._process = None

    def run(self):
        project = self.session.project
        cfg = self.session.config

        config_data = {
            "keyboard_track": project.keyboard_track,
            "mic_tracks": project.mic_tracks,
            "videos": project.videos,
            "reference_track": project.get_reference_track(),
            "temp_dir": os.path.join(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))), "temp"),
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

            stdout_thread.join(timeout=10)
            try:
                stdout = stdout_queue.get(timeout=1)
            except queue.Empty:
                stdout = ""

            if self._process.returncode != 0:
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


class MainWindow(QMainWindow):
    """PeakCut Main Window — Simplified: Welcome → Analysis → Review"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        self.session = None
        self._worker = None

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
        self.camera_combo.setMinimumWidth(180)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
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

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Video preview
        self.video_preview = PeakVideoPreview()
        self.video_preview.setMinimumHeight(350)
        layout.addWidget(self.video_preview, stretch=1)

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

        controls.addStretch()

        # Peak counter
        self.peak_label = QLabel("Peak 1 / 10")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 16px;")
        controls.addWidget(self.peak_label)

        controls.addSpacing(20)

        # Mode toggle (KB/MIC)
        self.mode_btn = QPushButton("KB")
        self.mode_btn.setMaximumWidth(50)
        self.mode_btn.clicked.connect(self._on_mode_toggle)
        controls.addWidget(self.mode_btn)

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
        last_folder = self._settings.value("last_folder", MATERIAL_DIR)
        if not os.path.exists(last_folder):
            last_folder = MATERIAL_DIR

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

        project = PeakCutProject(MATERIAL_DIR, EXPORT_DIR)
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

    def _on_back(self):
        if self.session and self.session.current_peak > 0:
            self._navigate_to_peak(self.session.current_peak - 1)

    def _on_next(self):
        if self.session and self.session.current_peak < len(self.session.peaks) - 1:
            self._navigate_to_peak(self.session.current_peak + 1)

    def _on_play(self):
        if self.session:
            self.session.play_current()

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
            self.mode_btn.setText("KB" if self.session.mode == "keyboard" else "MIC")
            self.session.play_current()

    # ══════════════════════════════════════════════════════════════
    # Camera & LUT
    # ══════════════════════════════════════════════════════════════

    def _on_camera_changed(self, index):
        if 0 <= index < len(self._video_files):
            self.video_preview.load_video_at_index(index)
            # Re-show current peak position
            if self.session and self.session.peaks:
                peak = self.session.peaks[self.session.current_peak]
                self.video_preview.set_position(peak.position_ms)

    def _on_lut_changed(self, index):
        data = self.lut_combo.currentData()
        if data is not None:
            config.set("lut_path", data)
            self.video_preview.refresh_lut()

    # ══════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════

    def _on_export(self):
        if not self.session:
            return

        stop_playback()
        self.export_btn.setEnabled(False)
        self.statusbar.showMessage("Export läuft...")
        QApplication.processEvents()

        try:
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
            for exporter in exporters:
                result = exporter.export(self.session)
                if result:
                    self.statusbar.showMessage(f"Exportiert: {os.path.basename(result)}")
                    QApplication.processEvents()

            self.statusbar.showMessage(f"Export fertig! → {EXPORT_DIR}")
        except Exception as e:
            self.statusbar.showMessage(f"Export-Fehler: {e}")

        self.export_btn.setEnabled(True)

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
        else:
            super().keyPressEvent(event)

    # ══════════════════════════════════════════════════════════════
    # Cleanup
    # ══════════════════════════════════════════════════════════════

    def closeEvent(self, event):
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

        stop_playback()
        event.accept()
