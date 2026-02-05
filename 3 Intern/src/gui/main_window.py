# main_window.py - PeakCut Main Window (2-Phase: Welcome → Workspace)

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog,
    QApplication, QComboBox, QStackedWidget, QInputDialog
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer, QElapsedTimer

from .apple_style import get_stylesheet, COLORS
from .video_preview_peak import PeakVideoPreview
from .peak_timeline import ClipTimeline, ScrubTimeline

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
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            self.session.analyze()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# Tab styling
_TAB_ACTIVE = """
    QPushButton {
        background-color: #007AFF;
        border: none;
        border-radius: 4px;
        color: white;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 14px;
    }
"""
_TAB_INACTIVE = """
    QPushButton {
        background-color: transparent;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        color: #888888;
        font-size: 12px;
        font-weight: 500;
        padding: 4px 14px;
    }
    QPushButton:hover { border-color: #555555; color: #bbbbbb; }
"""


class MainWindow(QMainWindow):
    """PeakCut Main Window — Welcome → Workspace."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 750)

        self.session = None
        self._worker = None
        self._view_mode = "screenshots"  # "peaks" or "screenshots"
        self._analysis_done = False

        # File state
        self._selected_files = []
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        # Camera state
        self._current_video_index = 0
        self._camera_names = {}  # video_path → name

        self._settings = QSettings("PeakCut", "PeakCut")

        self._setup_ui()
        self._setup_statusbar()

    # ── UI Setup ─────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self._setup_welcome_page()    # index 0
        self._setup_workspace_page()  # index 1

        self.stack.setCurrentIndex(0)

    def _setup_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("PeakCut")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 42px;
            font-weight: 700;
            font-family: 'SF Pro Display', -apple-system, sans-serif;
        """)
        layout.addWidget(title)

        layout.addSpacing(30)

        btn = QPushButton("Import Files")
        btn.setProperty("class", "primary")
        btn.setMinimumWidth(160)
        btn.setMinimumHeight(40)
        btn.clicked.connect(self._on_load_files)
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.stack.addWidget(page)

    def _setup_workspace_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(6)

        # ── Top bar: Mode tabs + Camera + LUT ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.tab_peaks = QPushButton("Peaks")
        self.tab_peaks.setStyleSheet(_TAB_INACTIVE)
        self.tab_peaks.clicked.connect(lambda: self._set_view_mode("peaks"))
        top_bar.addWidget(self.tab_peaks)

        self.tab_screenshots = QPushButton("Screenshots")
        self.tab_screenshots.setStyleSheet(_TAB_ACTIVE)
        self.tab_screenshots.clicked.connect(lambda: self._set_view_mode("screenshots"))
        top_bar.addWidget(self.tab_screenshots)

        self.screenshot_btn = QPushButton("\U0001F4F7")
        self.screenshot_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 20px;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #3a3a3a; border-radius: 6px; }
            QPushButton:pressed { background-color: #4a4a4a; border-radius: 6px; }
            QPushButton:disabled { opacity: 0.3; }
        """)
        self.screenshot_btn.clicked.connect(self._on_capture_screenshot)
        self.screenshot_btn.setEnabled(False)
        self.screenshot_btn.setVisible(False)
        top_bar.addWidget(self.screenshot_btn)

        top_bar.addSpacing(16)

        cam_label = QLabel("Kamera:")
        cam_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        top_bar.addWidget(cam_label)

        self.video_combo = QComboBox()
        self.video_combo.setEditable(True)
        self.video_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.video_combo.setCompleter(None)
        self.video_combo.setMinimumWidth(200)
        self.video_combo.setStyleSheet(self._dark_combo_style())
        self.video_combo.activated.connect(self._on_video_activated)
        self.video_combo.lineEdit().textEdited.connect(self._on_camera_name_typed)
        top_bar.addWidget(self.video_combo)

        top_bar.addStretch()

        lut_label = QLabel("LUT:")
        lut_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        top_bar.addWidget(lut_label)

        self.lut_combo = QComboBox()
        self.lut_combo.setMinimumWidth(160)
        self.lut_combo.setStyleSheet(self._dark_combo_style())
        self._populate_lut_combo()
        self.lut_combo.currentIndexChanged.connect(self._on_lut_selected)
        top_bar.addWidget(self.lut_combo)

        layout.addLayout(top_bar)

        # ── Video preview ──
        self.video_preview = PeakVideoPreview()
        self.video_preview.position_changed.connect(self._on_video_position_changed)
        self.video_preview.duration_changed.connect(self._on_video_duration_changed)
        self.video_preview.screenshot_done.connect(self._on_screenshot_done)
        layout.addWidget(self.video_preview, stretch=1)

        # ── Timeline stack (switches between modes) ──
        self.timeline_stack = QStackedWidget()

        # Page 0: Peak mode — ClipTimeline + In/Out controls
        peak_page = QWidget()
        clip_row = QHBoxLayout(peak_page)
        clip_row.setContentsMargins(0, 0, 0, 0)
        clip_row.setSpacing(8)

        self.in_label = QLabel("In: --:--:--")
        self.in_label.setMinimumWidth(90)
        self.in_label.setStyleSheet("color: #30D158; font-size: 12px; font-family: 'SF Mono', Menlo, monospace;")
        clip_row.addWidget(self.in_label)

        self.set_in_btn = QPushButton("Set In")
        self.set_in_btn.setProperty("class", "small")
        self.set_in_btn.setMaximumWidth(55)
        self.set_in_btn.clicked.connect(self._on_set_in)
        self.set_in_btn.setEnabled(False)
        clip_row.addWidget(self.set_in_btn)

        self.clip_timeline = ClipTimeline()
        self.clip_timeline.position_changed.connect(self._on_clip_seek)
        self.clip_timeline.clip_in_changed.connect(self._on_clip_in_dragged)
        self.clip_timeline.clip_out_changed.connect(self._on_clip_out_dragged)
        clip_row.addWidget(self.clip_timeline, stretch=1)

        self.set_out_btn = QPushButton("Set Out")
        self.set_out_btn.setProperty("class", "small")
        self.set_out_btn.setMaximumWidth(55)
        self.set_out_btn.clicked.connect(self._on_set_out)
        self.set_out_btn.setEnabled(False)
        clip_row.addWidget(self.set_out_btn)

        self.out_label = QLabel("Out: --:--:--")
        self.out_label.setMinimumWidth(90)
        self.out_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.out_label.setStyleSheet("color: #FF453A; font-size: 12px; font-family: 'SF Mono', Menlo, monospace;")
        clip_row.addWidget(self.out_label)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setProperty("class", "small")
        self.reset_btn.setMaximumWidth(50)
        self.reset_btn.clicked.connect(self._on_clip_reset)
        self.reset_btn.setEnabled(False)
        clip_row.addWidget(self.reset_btn)

        self.timeline_stack.addWidget(peak_page)

        # Page 1: Screenshot mode — ScrubTimeline (full duration)
        scrub_page = QWidget()
        scrub_row = QHBoxLayout(scrub_page)
        scrub_row.setContentsMargins(0, 0, 0, 0)
        scrub_row.setSpacing(0)

        self.scrub_timeline = ScrubTimeline()
        self.scrub_timeline.position_changed.connect(self._on_scrub_seek)
        scrub_row.addWidget(self.scrub_timeline, stretch=1)

        self.timeline_stack.addWidget(scrub_page)

        # Start in screenshots mode
        self.timeline_stack.setCurrentIndex(1)
        layout.addWidget(self.timeline_stack)

        # ── Bottom bar (stacked: analysis indicator / toolbar) ──
        self.bottom_stack = QStackedWidget()
        self.bottom_stack.setFixedHeight(36)

        # Page 0: Analysis indicator
        analysis_page = QWidget()
        analysis_layout = QHBoxLayout(analysis_page)
        analysis_layout.setContentsMargins(4, 0, 4, 0)
        analysis_layout.setSpacing(8)

        self.analysis_status_label = QLabel("Analyse läuft...")
        self.analysis_status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        analysis_layout.addWidget(self.analysis_status_label)

        analysis_layout.addStretch()

        self.analysis_time_label = QLabel("00:00")
        self.analysis_time_label.setStyleSheet("color: #888888; font-size: 13px; font-family: 'SF Mono', Menlo, monospace;")
        analysis_layout.addWidget(self.analysis_time_label)

        self.bottom_stack.addWidget(analysis_page)

        # Page 1: Toolbar
        toolbar_widget = QWidget()
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        self.back_btn = QPushButton("\u25C0")
        self.back_btn.setMaximumWidth(36)
        self.back_btn.clicked.connect(self._on_back)
        self.back_btn.setEnabled(False)
        toolbar.addWidget(self.back_btn)

        self.next_btn = QPushButton("\u25B6")
        self.next_btn.setMaximumWidth(36)
        self.next_btn.clicked.connect(self._on_next)
        self.next_btn.setEnabled(False)
        toolbar.addWidget(self.next_btn)

        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setProperty("class", "primary")
        self.play_pause_btn.setMinimumWidth(70)
        self.play_pause_btn.clicked.connect(self._on_play_pause)
        self.play_pause_btn.setEnabled(False)
        toolbar.addWidget(self.play_pause_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet(f"color: {COLORS['border_light']};")
        toolbar.addWidget(sep1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        self.time_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        toolbar.addWidget(self.time_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {COLORS['border_light']};")
        toolbar.addWidget(sep2)

        self.ignore_btn = QPushButton("Ignore")
        self.ignore_btn.clicked.connect(self._on_ignore)
        self.ignore_btn.setEnabled(False)
        toolbar.addWidget(self.ignore_btn)

        toolbar.addStretch()

        self.mode_btn = QPushButton("KB")
        self.mode_btn.setProperty("class", "small")
        self.mode_btn.setMaximumWidth(40)
        self.mode_btn.clicked.connect(self._on_switch_mode)
        self.mode_btn.setEnabled(False)
        toolbar.addWidget(self.mode_btn)

        self.peak_label = QLabel("- / -")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        toolbar.addWidget(self.peak_label)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setStyleSheet(f"color: {COLORS['border_light']};")
        toolbar.addWidget(sep3)

        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.export_btn)

        self.bottom_stack.addWidget(toolbar_widget)

        # Start on analysis indicator
        self.bottom_stack.setCurrentIndex(0)
        layout.addWidget(self.bottom_stack)

        # Elapsed time timer
        self._elapsed_timer = QElapsedTimer()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._update_remaining_time)

        self.stack.addWidget(page)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

    # ── View mode switching ──────────────────────────────────────

    def _set_view_mode(self, mode: str):
        self._view_mode = mode
        if mode == "peaks":
            self.tab_peaks.setStyleSheet(_TAB_ACTIVE)
            self.tab_screenshots.setStyleSheet(_TAB_INACTIVE)
            self.screenshot_btn.setVisible(False)
            if self._analysis_done:
                self.timeline_stack.setCurrentIndex(0)
                self.timeline_stack.setVisible(True)
                self.bottom_stack.setCurrentIndex(1)
            else:
                # Hide controls until analysis is done
                self.timeline_stack.setVisible(False)
                self.bottom_stack.setCurrentIndex(0)
        else:
            self.tab_peaks.setStyleSheet(_TAB_INACTIVE)
            self.tab_screenshots.setStyleSheet(_TAB_ACTIVE)
            self.screenshot_btn.setVisible(True)
            self.timeline_stack.setCurrentIndex(1)
            self.timeline_stack.setVisible(True)
            self.bottom_stack.setCurrentIndex(1)

    # ── Style helpers ────────────────────────────────────────────

    @staticmethod
    def _dark_combo_style():
        return """
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 5px 10px;
                font-size: 13px;
            }
            QComboBox:hover { border-color: #4a4a4a; }
            QComboBox::drop-down { border: none; padding-right: 8px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                selection-background-color: #007AFF;
            }
        """

    # ── File import ──────────────────────────────────────────────

    def _on_load_files(self):
        last_folder = self._settings.value("last_folder", MATERIAL_DIR)
        if not os.path.exists(last_folder):
            last_folder = MATERIAL_DIR

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Dateien auswählen",
            last_folder,
            "Media Files (*.wav *.mp3 *.mp4 *.mov);;All Files (*)"
        )
        if not files:
            return

        self._settings.setValue("last_folder", os.path.dirname(files[0]))
        self._selected_files = files
        self._categorize_files()

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

        self._copy_files_to_material()
        self._start_workspace()

    def _categorize_files(self):
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

    def _copy_files_to_material(self):
        import shutil
        os.makedirs(MATERIAL_DIR, exist_ok=True)

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

    def _default_camera_name(self, filepath: str) -> str:
        """Filename without extension as default camera name."""
        return os.path.splitext(os.path.basename(filepath))[0]

    # ── Start workspace + analysis ───────────────────────────────

    def _start_workspace(self):
        self.stack.setCurrentIndex(1)

        # Start in screenshots mode (full timeline for pre-analysis browsing)
        self._set_view_mode("screenshots")

        if self._video_files:
            self._populate_video_combo()
            self.video_preview.set_videos(self._video_files)
            self.screenshot_btn.setEnabled(True)
            self.play_pause_btn.setEnabled(True)

        self._analysis_done = False
        self.bottom_stack.setCurrentIndex(0)

        # Estimate analysis time from file sizes
        self._estimated_seconds = self._estimate_analysis_time()
        self._elapsed_timer.start()
        self._tick_timer.start()
        self._update_remaining_time()

        project = PeakCutProject(MATERIAL_DIR, EXPORT_DIR)
        project.set_files(self._keyboard_file, self._mic_files, self._video_files)

        self.session = PeakCutSession(project, config.load())
        self.session.status_update.connect(self._on_analysis_status)
        self.session.clip_adjusted.connect(self._on_clip_adjusted)

        self._worker = AnalysisWorker(self.session)
        self._worker.finished.connect(self._on_analysis_complete)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_status(self, message):
        self.statusbar.showMessage(message)
        self.analysis_status_label.setText(message)

    def _on_analysis_complete(self):
        self._tick_timer.stop()
        self._analysis_done = True

        try:
            peaks = self.session.peaks
            num_peaks = len(peaks)

            if num_peaks > 0:
                self._set_peak_controls_enabled(True)
                self.mode_btn.setText("KB" if self.session.mode == "keyboard" else "MIC")

                # Feed peaks to scrub timeline
                self.scrub_timeline.set_peaks([p.position_ms for p in peaks])

                # Switch to peaks mode and navigate to first peak
                self._set_view_mode("peaks")
                self.navigate_to_peak(0)
                self.statusbar.showMessage(f"{num_peaks} Peaks gefunden")
            else:
                self.bottom_stack.setCurrentIndex(1)
                self.statusbar.showMessage("Keine Peaks gefunden")
        except Exception as e:
            self.bottom_stack.setCurrentIndex(1)
            self.statusbar.showMessage(f"Fehler: {e}")

        self._worker = None

    def _on_analysis_error(self, error_msg):
        self._tick_timer.stop()
        self._analysis_done = True
        self.bottom_stack.setCurrentIndex(1)
        self.statusbar.showMessage(f"Fehler: {error_msg}")
        self._worker = None

    def _estimate_analysis_time(self) -> int:
        """Estimate analysis time in seconds based on file sizes."""
        total = 5  # base overhead
        if self._keyboard_file and os.path.exists(self._keyboard_file):
            size_mb = os.path.getsize(self._keyboard_file) / (1024 * 1024)
            total += int(size_mb * 0.15)
        for mic in self._mic_files:
            if os.path.exists(mic):
                size_mb = os.path.getsize(mic) / (1024 * 1024)
                total += int(size_mb * 0.05)
        total += len(self._video_files) * 12
        return max(5, total)

    def _update_remaining_time(self):
        elapsed_s = self._elapsed_timer.elapsed() // 1000
        remaining = max(0, self._estimated_seconds - elapsed_s)
        if remaining > 60:
            m = remaining // 60
            self.analysis_time_label.setText(f"~{m} Min.")
        else:
            self.analysis_time_label.setText(f"~{remaining} Sek.")

    # ── Peak Navigation ──────────────────────────────────────────

    def navigate_to_peak(self, index: int):
        if not self.session or not self.session.peaks:
            return
        if not (0 <= index < len(self.session.peaks)):
            return

        self.session.set_current_peak(index)
        peak = self.session.peaks[index]

        # Update clip timeline
        self.clip_timeline.set_peak(peak.position_ms, peak.in_point_ms, peak.out_point_ms)

        # Update scrub timeline
        self.scrub_timeline.set_current_peak(index)
        self.scrub_timeline.set_position(peak.position_ms)

        # Update labels
        self.in_label.setText(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")
        self.out_label.setText(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")
        self.peak_label.setText(f"{index + 1} / {len(self.session.peaks)}")

        # Video: play from In to Out
        if self._video_files:
            self.video_preview.play_from(peak.in_point_ms, peak.out_point_ms)
            self.play_pause_btn.setText("Pause")
        else:
            self.session.play_current()

    def _on_back(self):
        if self.session and self.session.current_peak > 0:
            self.navigate_to_peak(self.session.current_peak - 1)

    def _on_next(self):
        if self.session and self.session.current_peak < len(self.session.peaks) - 1:
            self.navigate_to_peak(self.session.current_peak + 1)

    def _on_play_pause(self):
        if not self.video_preview:
            return
        playing = self.video_preview.toggle_play_pause()
        self.play_pause_btn.setText("Pause" if playing else "Play")

    # ── Clip editing ─────────────────────────────────────────────

    def _on_set_in(self):
        if not self.session:
            return
        pos = self.video_preview.get_position()
        idx = self.session.current_peak
        self.session.adjust_clip(idx, in_ms=pos)
        peak = self.session.peaks[idx]
        self.clip_timeline.set_peak(peak.position_ms, peak.in_point_ms, peak.out_point_ms)
        self.in_label.setText(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")
        self.statusbar.showMessage(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")

    def _on_set_out(self):
        if not self.session:
            return
        pos = self.video_preview.get_position()
        idx = self.session.current_peak
        self.session.adjust_clip(idx, out_ms=pos)
        peak = self.session.peaks[idx]
        self.clip_timeline.set_peak(peak.position_ms, peak.in_point_ms, peak.out_point_ms)
        self.out_label.setText(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")
        self.statusbar.showMessage(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")

    def _on_clip_in_dragged(self, ms):
        if not self.session:
            return
        idx = self.session.current_peak
        self.session.adjust_clip(idx, in_ms=ms)
        self.video_preview.set_position(ms)
        peak = self.session.peaks[idx]
        self.in_label.setText(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")

    def _on_clip_out_dragged(self, ms):
        if not self.session:
            return
        idx = self.session.current_peak
        self.session.adjust_clip(idx, out_ms=ms)
        self.video_preview.set_position(ms)
        peak = self.session.peaks[idx]
        self.out_label.setText(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")

    def _on_clip_seek(self, ms):
        self.video_preview.set_position(ms)
        self.video_preview.stop_clip_playback()
        self.play_pause_btn.setText("Play")

    def _on_scrub_seek(self, ms):
        """Seek from ScrubTimeline (screenshot mode)."""
        self.video_preview.set_position(ms)
        self.video_preview.stop_clip_playback()
        self.play_pause_btn.setText("Play")

    def _on_clip_reset(self):
        if not self.session:
            return
        idx = self.session.current_peak
        self.session.reset_clip(idx)
        peak = self.session.peaks[idx]
        self.clip_timeline.set_peak(peak.position_ms, peak.in_point_ms, peak.out_point_ms)
        self.in_label.setText(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")
        self.out_label.setText(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")
        self.statusbar.showMessage("Clip reset")

    def _on_clip_adjusted(self, index):
        if self.session and index == self.session.current_peak:
            peak = self.session.peaks[index]
            self.clip_timeline.set_peak(peak.position_ms, peak.in_point_ms, peak.out_point_ms)
            self.in_label.setText(f"In: {self._ms_to_hhmmss(peak.in_point_ms)}")
            self.out_label.setText(f"Out: {self._ms_to_hhmmss(peak.out_point_ms)}")

    # ── Video position updates ───────────────────────────────────

    def _on_video_position_changed(self, ms):
        # Update whichever timeline is active
        self.clip_timeline.set_position(ms)
        self.scrub_timeline.set_position(ms)
        self.time_label.setText(
            f"{self._ms_to_mmss(ms)} / {self._ms_to_mmss(self.video_preview.get_duration())}")
        if not self.video_preview.is_playing():
            self.play_pause_btn.setText("Play")

    def _on_video_duration_changed(self, ms):
        self.clip_timeline.set_duration(ms)
        self.scrub_timeline.set_duration(ms)

    # ── Camera combo (editable = name field) ─────────────────────

    def _populate_video_combo(self):
        self.video_combo.blockSignals(True)
        self.video_combo.clear()
        for i, filepath in enumerate(self._video_files):
            filename = os.path.basename(filepath)
            self.video_combo.addItem(f"Kamera {i + 1}: {filename}", filepath)
        self._current_video_index = 0
        if self._video_files:
            path = self._video_files[0]
            name = self._camera_names.get(path, self._default_camera_name(path))
            self._camera_names[path] = name
            self.video_combo.setEditText(name)
            self.video_preview.set_camera_name(name)
        self.video_combo.blockSignals(False)

    def _on_video_activated(self, index):
        if not (0 <= index < len(self._video_files)):
            return

        # Store current name
        if 0 <= self._current_video_index < len(self._video_files):
            old_path = self._video_files[self._current_video_index]
            self._camera_names[old_path] = self.video_combo.currentText().strip()

        self._current_video_index = index
        self.video_preview.load_video_at_index(index)

        # Restore name (default to filename)
        path = self._video_files[index]
        name = self._camera_names.get(path, self._default_camera_name(path))
        self._camera_names[path] = name
        self.video_combo.setEditText(name)
        self.video_preview.set_camera_name(name)

    def _on_camera_name_typed(self, text):
        if 0 <= self._current_video_index < len(self._video_files):
            path = self._video_files[self._current_video_index]
            self._camera_names[path] = text.strip()
            self.video_preview.set_camera_name(text)

    # ── Screenshot (async) ───────────────────────────────────────

    def _on_capture_screenshot(self):
        self.screenshot_btn.setEnabled(False)
        self.statusbar.showMessage("Screenshot...")
        name = ""
        if 0 <= self._current_video_index < len(self._video_files):
            path = self._video_files[self._current_video_index]
            name = self._camera_names.get(path, "")
        self.video_preview.capture_screenshot_async(name)

    def _on_screenshot_done(self, filepath):
        self.screenshot_btn.setEnabled(True)
        if filepath:
            self.statusbar.showMessage(f"Screenshot: {os.path.basename(filepath)}")
        else:
            self.statusbar.showMessage("Screenshot fehlgeschlagen")

    # ── Mode switch ──────────────────────────────────────────────

    def _on_switch_mode(self):
        if self.session:
            self.session.switch_mode()
            self.mode_btn.setText("KB" if self.session.mode == "keyboard" else "MIC")
            self.statusbar.showMessage(f"Mode: {self.session.mode.upper()}")

    # ── Ignore ───────────────────────────────────────────────────

    def _on_ignore(self):
        if self.session:
            self.session.ignore_peak()
            self.statusbar.showMessage(f"Peak {self.session.current_peak + 1} ignoriert")

    # ── Export ───────────────────────────────────────────────────

    def _on_export(self):
        stop_playback()
        self.statusbar.showMessage("Export läuft...")
        self.export_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
            for exporter in exporters:
                exporter.export(self.session)
            self.statusbar.showMessage(f"Export fertig! → {EXPORT_DIR}")
        except Exception as e:
            self.statusbar.showMessage(f"Export-Fehler: {e}")

        self.export_btn.setEnabled(True)

    # ── LUT ──────────────────────────────────────────────────────

    def _populate_lut_combo(self):
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()

        current_lut = config.get("lut_path") or ""
        if current_lut and os.sep in current_lut:
            self._migrate_lut_path(current_lut)
            current_lut = config.get("lut_path") or ""

        self.lut_combo.addItem("Kein LUT", "")

        os.makedirs(LUTS_DIR, exist_ok=True)
        lut_files = sorted(
            f for f in os.listdir(LUTS_DIR) if f.lower().endswith('.cube'))

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
        import shutil
        data = self.lut_combo.currentData()
        if data is None:
            return

        if data == "__browse__":
            filepath, _ = QFileDialog.getOpenFileName(
                self, "LUT importieren",
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
                self.statusbar.showMessage(f"LUT importiert: {os.path.splitext(filename)[0]}")
            else:
                self._populate_lut_combo()
        else:
            config.set("lut_path", data)
            self.video_preview.refresh_lut()
            if data:
                self.statusbar.showMessage(f"LUT: {os.path.splitext(data)[0]}")
            else:
                self.statusbar.showMessage("LUT deaktiviert")

    # ── Controls enable/disable ──────────────────────────────────

    def _set_peak_controls_enabled(self, enabled):
        for btn in (self.back_btn, self.next_btn,
                    self.ignore_btn, self.export_btn, self.mode_btn,
                    self.set_in_btn, self.set_out_btn, self.reset_btn):
            btn.setEnabled(enabled)

    # ── Keyboard shortcuts ───────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text()

        if self.video_combo.lineEdit().hasFocus():
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Right:
            if self.session and self.session.peaks:
                self._on_next()
            return

        if key == Qt.Key.Key_Left:
            if self.session and self.session.peaks:
                self._on_back()
            return

        if key == Qt.Key.Key_Space:
            if self.stack.currentIndex() == 1:
                self._on_play_pause()
            return

        if self.session and self.session.peaks:
            if text == "[":
                self._on_set_in()
                return
            if text == "]":
                self._on_set_out()
                return
            if text == "r":
                self._on_clip_reset()
                return

        super().keyPressEvent(event)

    # ── Clean shutdown ───────────────────────────────────────────

    def closeEvent(self, event):
        self._tick_timer.stop()
        self.video_preview.cleanup()
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        stop_playback()
        event.accept()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _ms_to_hhmmss(ms):
        total_s = ms // 1000
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _ms_to_mmss(ms):
        seconds = ms // 1000
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"
