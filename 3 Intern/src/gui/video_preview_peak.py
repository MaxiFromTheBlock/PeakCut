# video_preview_peak.py - PeakCut Video Preview with Peak Timeline

import os
import subprocess
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSizePolicy, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QSize
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

from .apple_style import COLORS
from .peak_timeline import PeakTimeline


class PeakVideoPreview(QWidget):
    """Video preview widget with peak timeline for PeakCut."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms
    video_changed = pyqtSignal(str)  # video filepath
    peak_clicked = pyqtSignal(int)  # peak index

    def __init__(self, parent=None):
        super().__init__(parent)

        self._video_files = []
        self._current_video = None
        self._duration_ms = 0
        self._peaks = []  # List of peak positions in ms
        self._current_peak_index = -1
        self._is_seeking = False

        # LUT state
        self._lut_processor = None
        self._lut_loaded_filename = None  # Track which LUT file is loaded
        self._last_frame = None  # Store last frame for LUT refresh

        # Camera name state
        self._camera_names = {}  # video_path → name
        self._screenshot_counters = {}  # name → counter

        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video container card
        self.video_card = QFrame()
        self.video_card.setProperty("class", "card")
        self.video_card.setStyleSheet(f"""
            QFrame[class="card"] {{
                background-color: #1a1a1a;
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)

        card_layout = QVBoxLayout(self.video_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        # Video switcher row
        switcher_layout = QHBoxLayout()
        switcher_layout.setSpacing(8)

        switcher_label = QLabel("Kamera:")
        switcher_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        switcher_layout.addWidget(switcher_label)

        self.video_combo = QComboBox()
        self.video_combo.setMinimumWidth(200)
        self.video_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: #4a4a4a;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888888;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                selection-background-color: #007AFF;
            }}
        """)
        self.video_combo.currentIndexChanged.connect(self._on_video_selected)
        switcher_layout.addWidget(self.video_combo)

        self.camera_name_edit = QLineEdit()
        self.camera_name_edit.setPlaceholderText("Name...")
        self.camera_name_edit.setMaximumWidth(150)
        self.camera_name_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: #007AFF;
            }}
        """)
        self.camera_name_edit.textChanged.connect(self._on_camera_name_changed)
        self.camera_name_edit.returnPressed.connect(self.camera_name_edit.clearFocus)
        switcher_layout.addWidget(self.camera_name_edit)

        switcher_layout.addStretch()
        card_layout.addLayout(switcher_layout)

        # Video display (QLabel for LUT-graded frames via QVideoSink)
        self.video_label = QLabel()
        self.video_label.setMinimumHeight(300)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 6px;")
        card_layout.addWidget(self.video_label, stretch=1)

        # Timeline row
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(12)

        self.time_label = QLabel("00:00")
        self.time_label.setMinimumWidth(50)
        self.time_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.time_label)

        # Custom timeline with peak markers
        self.timeline = PeakTimeline()
        self.timeline.position_changed.connect(self._on_timeline_position_changed)
        self.timeline.peak_clicked.connect(self._on_timeline_peak_clicked)
        timeline_layout.addWidget(self.timeline, stretch=1)

        self.duration_label = QLabel("00:00")
        self.duration_label.setMinimumWidth(50)
        self.duration_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.duration_label)

        card_layout.addLayout(timeline_layout)

        layout.addWidget(self.video_card, stretch=1)

    def _setup_player(self):
        """Setup QMediaPlayer with QVideoSink for frame interception."""
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Use QVideoSink to intercept frames for LUT processing
        self.video_sink = QVideoSink()
        self.video_sink.videoFrameChanged.connect(self._on_video_frame)
        self.player.setVideoOutput(self.video_sink)

        # Connect signals
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.errorOccurred.connect(self._on_error)

    def _ensure_lut(self):
        """Lazy-load or reload LUT if config changed."""
        import config
        from utils import LUTS_DIR
        from lib.lut_processor import LUTProcessor

        lut_filename = config.get("lut_path") or ""

        if lut_filename == self._lut_loaded_filename:
            return  # Already up to date

        self._lut_loaded_filename = lut_filename

        if not lut_filename:
            self._lut_processor = None
            return

        lut_full_path = os.path.join(LUTS_DIR, lut_filename)
        if os.path.exists(lut_full_path):
            proc = LUTProcessor()
            if proc.load_cube(lut_full_path):
                self._lut_processor = proc
            else:
                self._lut_processor = None
        else:
            self._lut_processor = None

    def _on_video_frame(self, frame):
        """Receive frame from sink, store it, process it."""
        if not frame.isValid():
            return
        self._last_frame = frame
        self._process_frame(frame)

    def _process_frame(self, frame):
        """Apply LUT to frame and display in label."""
        image = frame.toImage()
        if image.isNull():
            return

        # Check LUT
        self._ensure_lut()

        if self._lut_processor and self._lut_processor.is_loaded():
            # Scale to physical (Retina) pixel size for sharp LUT rendering
            dpr = self.video_label.devicePixelRatioF()
            logical = self.video_label.size()
            target = QSize(int(logical.width() * dpr), int(logical.height() * dpr))
            image = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Convert QImage → numpy RGB (respecting bytesPerLine stride)
            image = image.convertToFormat(QImage.Format.Format_RGB888)
            w, h = image.width(), image.height()
            bpl = image.bytesPerLine()
            ptr = image.bits()
            ptr.setsize(h * bpl)
            raw = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)
            arr = raw[:, :w * 3].reshape(h, w, 3).copy()

            # Apply LUT
            graded = self._lut_processor.apply_to_image(arr)

            # numpy → QImage → QPixmap with Retina DPR
            qimg = QImage(graded.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimg)
            pixmap.setDevicePixelRatio(dpr)
            self.video_label.setPixmap(pixmap)
        else:
            # No LUT: display full-resolution frame, let Qt scale on GPU
            self.video_label.setPixmap(QPixmap.fromImage(image))

    def refresh_lut(self):
        """Re-apply LUT to current frame (call after LUT selection change)."""
        self._lut_loaded_filename = None  # Force reload
        if self._last_frame and self._last_frame.isValid():
            self._process_frame(self._last_frame)

    def set_videos(self, video_files: list):
        """Set the list of video files."""
        self._video_files = video_files
        self.video_combo.clear()

        for i, filepath in enumerate(video_files):
            filename = os.path.basename(filepath)
            self.video_combo.addItem(f"Kamera {i + 1}: {filename}", filepath)

        if video_files:
            self._load_video(video_files[0])

    def set_peaks(self, peaks_ms: list, current_index: int = 0):
        """Set peak positions in milliseconds."""
        self._peaks = peaks_ms
        self._current_peak_index = current_index
        self.timeline.set_peaks(peaks_ms)
        self.timeline.set_current_peak(current_index)

    def set_current_peak(self, index: int):
        """Highlight the current peak."""
        self._current_peak_index = index
        self.timeline.set_current_peak(index)

    def seek_to_peak(self, index: int):
        """Seek video to a specific peak."""
        if 0 <= index < len(self._peaks):
            self._current_peak_index = index
            position_ms = self._peaks[index]
            self.player.setPosition(position_ms)

    def _load_video(self, filepath: str):
        """Load a video file."""
        self._current_video = filepath
        self.player.setSource(QUrl.fromLocalFile(filepath))

        # Show first frame by briefly playing then pausing
        self.player.play()
        QTimer.singleShot(50, self._show_first_frame)

        self.video_changed.emit(filepath)

    def _show_first_frame(self):
        """Pause to show first frame after brief play."""
        self.player.pause()
        self.player.setPosition(0)

    def _on_camera_name_changed(self, text):
        """Store camera name for the current video."""
        if self._current_video:
            self._camera_names[self._current_video] = text.strip()

    def get_current_camera_name(self) -> str:
        """Get the camera name for the currently selected video."""
        if self._current_video:
            return self._camera_names.get(self._current_video, "")
        return ""

    def _on_video_selected(self, index: int):
        """Handle video selection from combo box."""
        if index >= 0 and index < len(self._video_files):
            # Restore camera name for this video
            path = self._video_files[index]
            name = self._camera_names.get(path, "")
            self.camera_name_edit.blockSignals(True)
            self.camera_name_edit.setText(name)
            self.camera_name_edit.blockSignals(False)
            self._load_video(path)

    def _on_duration_changed(self, duration: int):
        """Handle duration change."""
        self._duration_ms = duration
        self.timeline.set_duration(duration)
        self.duration_label.setText(self._format_time(duration))

    def _on_position_changed(self, position: int):
        """Handle position change during playback."""
        if not self._is_seeking:
            self.timeline.set_position(position)
            self.time_label.setText(self._format_time(position))
            self.position_changed.emit(position)

    def _on_timeline_position_changed(self, position: int):
        """Handle timeline seek from user interaction."""
        self._is_seeking = True
        self.player.setPosition(position)
        self.time_label.setText(self._format_time(position))
        self._is_seeking = False

    def _on_timeline_peak_clicked(self, peak_index: int):
        """Handle click on peak marker."""
        self._current_peak_index = peak_index
        self.timeline.set_current_peak(peak_index)
        if 0 <= peak_index < len(self._peaks):
            self.player.setPosition(self._peaks[peak_index])
        self.peak_clicked.emit(peak_index)

    def _on_error(self, error):
        """Handle player errors."""
        print(f"Video error: {error}, {self.player.errorString()}")

    def _format_time(self, ms: int) -> str:
        """Format milliseconds as MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def play(self):
        """Start playback."""
        self.player.play()

    def pause(self):
        """Pause playback."""
        self.player.pause()

    def stop(self):
        """Stop playback."""
        self.player.stop()

    def is_playing(self) -> bool:
        """Check if video is playing."""
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def get_position(self) -> int:
        """Get current position in ms."""
        return self.player.position()

    def set_position(self, position_ms: int):
        """Set position in ms."""
        self.player.setPosition(position_ms)

    def capture_screenshot(self, camera_name: str = "") -> str:
        """Capture current frame at full resolution, apply LUT, save as PNG.

        Args:
            camera_name: Optional name for counter-based naming (e.g. "Matze 1.png").

        Returns:
            Path to saved screenshot, or empty string on failure.
        """
        if not self._current_video:
            return ""

        import config
        from utils import EXPORT_DIR, LUTS_DIR
        from lib.lut_processor import LUTProcessor
        from PIL import Image
        import io

        # Get current position
        position_ms = self.player.position()
        position_s = position_ms / 1000.0

        # Extract frame via ffmpeg (full resolution)
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-ss", str(position_s),
                    "-i", self._current_video,
                    "-frames:v", "1",
                    "-f", "image2pipe", "-vcodec", "png", "pipe:1"
                ],
                capture_output=True, timeout=10
            )
            if result.returncode != 0:
                return ""
        except Exception:
            return ""

        # Load image from ffmpeg output
        image = Image.open(io.BytesIO(result.stdout)).convert("RGB")

        # Apply LUT if configured (filename resolved from luts/ library)
        lut_filename = config.get("lut_path")
        if lut_filename:
            lut_full_path = os.path.join(LUTS_DIR, lut_filename)
            if os.path.exists(lut_full_path):
                lut = LUTProcessor()
                if lut.load_cube(lut_full_path):
                    image = lut.apply_to_pil_image(image)

        # Save to Export/Gastname - Screenshots/
        from core.exporters import extract_guest_name
        gastname = extract_guest_name()
        screenshots_dir = os.path.join(EXPORT_DIR, f"{gastname} - Screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        # Build filename
        if camera_name:
            # Counter-based: "Name 1.png", "Name 2.png", ...
            counter = self._screenshot_counters.get(camera_name, 0) + 1
            self._screenshot_counters[camera_name] = counter
            filename = f"{camera_name} {counter}.jpg"
        else:
            # Fallback: VideoName_HH-MM-SS-FF.jpg
            video_name = os.path.splitext(os.path.basename(self._current_video))[0]
            fps = config.get("fps") or 25
            total_frames = int(position_s * fps)
            h = total_frames // (3600 * fps)
            m = (total_frames % (3600 * fps)) // (60 * fps)
            s = (total_frames % (60 * fps)) // fps
            f = total_frames % fps
            timecode = f"{h:02d}-{m:02d}-{s:02d}-{f:02d}"
            filename = f"{video_name}_{timecode}.jpg"

        filepath = os.path.join(screenshots_dir, filename)
        image.save(filepath, "JPEG", quality=95)

        return filepath

    def get_duration(self) -> int:
        """Get video duration in ms."""
        return self._duration_ms
