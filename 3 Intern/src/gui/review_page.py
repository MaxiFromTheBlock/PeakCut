# review_page.py - Peak Review Page (Video + Controls + Navigation)

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QComboBox, QSlider,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from .apple_style import COLORS
from .video_preview_peak import PeakVideoPreview
from .workers import ExportWorker

import config
from utils import EXPORT_DIR, LUTS_DIR, ms_to_mmss, get_logger
from core.playback import stop_playback, is_playing

_log = get_logger("peakcut.review")
_PLAYBACK_POLL_MS = 200


class ReviewPage(QWidget):
    """Peak Review Page — Video player, navigation, export."""

    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.session = None
        self._video_files = []
        self._is_playing = False
        self._export_worker = None

        # Playback poll timer
        self._play_timer = QTimer()
        self._play_timer.setInterval(_PLAYBACK_POLL_MS)
        self._play_timer.timeout.connect(self._poll_playback)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # Top bar: Camera + LUT + Brightness
        top_bar = QHBoxLayout()

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

        lut_label = QLabel("LUT:")
        lut_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        top_bar.addWidget(lut_label)

        self.lut_combo = QComboBox()
        self.lut_combo.setMinimumWidth(150)
        self.lut_combo.currentIndexChanged.connect(self._on_lut_changed)
        top_bar.addWidget(self.lut_combo)

        top_bar.addSpacing(20)

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
        self.back_btn.clicked.connect(self.on_back)
        controls.addWidget(self.back_btn)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setProperty("class", "primary")
        self.play_btn.setMinimumWidth(100)
        self.play_btn.clicked.connect(self.on_play)
        controls.addWidget(self.play_btn)

        self.next_btn = QPushButton("Weiter ▶")
        self.next_btn.setMinimumWidth(90)
        self.next_btn.clicked.connect(self.on_next)
        controls.addWidget(self.next_btn)

        controls.addSpacing(20)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #3a3a3a;")
        controls.addWidget(sep)

        controls.addSpacing(20)

        self.ignore_btn = QPushButton("Ignorieren")
        self.ignore_btn.clicked.connect(self.on_ignore)
        controls.addWidget(self.ignore_btn)

        controls.addSpacing(20)

        self.mode_btn = QPushButton("Mode")
        self.mode_btn.clicked.connect(self._on_mode_toggle)
        controls.addWidget(self.mode_btn)

        controls.addStretch()

        self.peak_label = QLabel("Peak 1 / 10")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 16px;")
        controls.addWidget(self.peak_label)

        controls.addStretch()

        self.screenshot_btn = QPushButton("Screenshot")
        self.screenshot_btn.clicked.connect(self.on_screenshot)
        controls.addWidget(self.screenshot_btn)

        controls.addSpacing(20)

        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("class", "primary")
        self.export_btn.setMinimumWidth(100)
        self.export_btn.clicked.connect(self._on_export)
        controls.addWidget(self.export_btn)

        layout.addLayout(controls)

    # ══════════════════════════════════════════════════════════════
    # Setup (called after analysis completes)
    # ══════════════════════════════════════════════════════════════

    def set_session(self, session, video_files):
        """Initialize the review page with analysis results."""
        self.session = session
        self._video_files = video_files

        # Populate camera combo
        self.camera_combo.clear()
        for path in video_files:
            name = os.path.splitext(os.path.basename(path))[0]
            self.camera_combo.addItem(f"{name}", path)

        if video_files:
            self.video_preview.set_videos(video_files)
            self.video_preview.set_session(session)
            self.video_preview.screenshot_done.connect(self._on_screenshot_done)

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

    def navigate_to_peak(self, index):
        if not self.session or not self.session.peaks:
            return
        if not (0 <= index < len(self.session.peaks)):
            return

        self.session.set_current_peak(index)
        peak = self.session.peaks[index]

        total = len(self.session.peaks)
        self.peak_label.setText(f"Peak {index + 1} / {total}")

        if self._video_files:
            self.video_preview.set_position(peak.position_ms)

        self.session.play_current()
        self._start_play_state()

    def on_back(self):
        if self.session and self.session.current_peak > 0:
            self.navigate_to_peak(self.session.current_peak - 1)

    def on_next(self):
        if self.session and self.session.current_peak < len(self.session.peaks) - 1:
            self.navigate_to_peak(self.session.current_peak + 1)

    def on_play(self):
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

    def on_ignore(self):
        if not self.session:
            return
        self.session.ignore_peak()
        idx = self.session.current_peak
        self.status_message.emit(f"Peak {idx + 1} ignoriert")
        if idx < len(self.session.peaks) - 1:
            self.navigate_to_peak(idx + 1)

    def _on_mode_toggle(self):
        if self.session:
            self.session.switch_mode()
            mode_name = "Keyboard" if self.session.mode == "keyboard" else "Mikrofon"
            self.status_message.emit(f"Mode: {mode_name}")
            self.session.play_current()
            self._start_play_state()

    # ══════════════════════════════════════════════════════════════
    # Screenshot
    # ══════════════════════════════════════════════════════════════

    def on_screenshot(self):
        if not self._video_files:
            self.status_message.emit("Keine Videos geladen")
            return
        camera_name = self.camera_combo.currentText()
        self.status_message.emit("Screenshot wird erstellt...")
        self.video_preview.capture_screenshot_async(camera_name)

    def _on_screenshot_done(self, filepath):
        if filepath:
            self.status_message.emit(f"Screenshot: {os.path.basename(filepath)}")
        else:
            self.status_message.emit("Screenshot fehlgeschlagen")

    # ══════════════════════════════════════════════════════════════
    # Camera & LUT
    # ══════════════════════════════════════════════════════════════

    def _on_camera_changed(self, index):
        if 0 <= index < len(self._video_files):
            self.video_preview.load_video_at_index(index)
            brightness = self.video_preview.get_current_brightness()
            self.brightness_slider.blockSignals(True)
            self.brightness_slider.setValue(brightness)
            self.brightness_slider.blockSignals(False)
            self._update_brightness_label(brightness)
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
        self.status_message.emit("Export läuft...")

        self._export_worker = ExportWorker(self.session)
        self._export_worker.progress.connect(self.status_message.emit)
        self._export_worker.finished.connect(self._on_export_done)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_done(self, exported):
        _log.info("Export done: %d files -> %s", len(exported), EXPORT_DIR)
        self.export_btn.setEnabled(True)
        self.status_message.emit(f"Export fertig! {len(exported)} Dateien → {EXPORT_DIR}")
        self._export_worker.deleteLater()
        self._export_worker = None

    def _on_export_error(self, msg):
        _log.error("Export error: %s", msg)
        self.export_btn.setEnabled(True)
        self.status_message.emit(f"Export-Fehler: {msg}")
        self._export_worker.deleteLater()
        self._export_worker = None

    # ══════════════════════════════════════════════════════════════
    # Cleanup
    # ══════════════════════════════════════════════════════════════

    def cleanup(self):
        """Stop timers and workers. Called from MainWindow.closeEvent."""
        self._play_timer.stop()
        self.video_preview.cleanup()
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.wait(3000)
