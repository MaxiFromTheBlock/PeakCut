# video_preview_peak.py - PeakCut Video Preview (pure video player with LUT)

import os
import subprocess
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QSize, QThread, QMutex, QWaitCondition
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink


class LUTWorker(QThread):
    """Worker thread for LUT frame processing off the main thread.

    Only processes the latest submitted frame — intermediate frames are dropped.
    """
    frame_ready = pyqtSignal(QImage, float)  # processed image, device pixel ratio

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._pending = None  # (QImage, QSize, float, LUTProcessor)
        self._abort = False

    def submit(self, image, target_size, dpr, lut_processor):
        """Submit frame for processing. Drops any pending unprocessed frame."""
        self._mutex.lock()
        self._pending = (image, target_size, dpr, lut_processor)
        self._mutex.unlock()
        self._wait.wakeOne()

    def run(self):
        while True:
            self._mutex.lock()
            while self._pending is None and not self._abort:
                self._wait.wait(self._mutex)
            if self._abort:
                self._mutex.unlock()
                return
            image, target_size, dpr, lut = self._pending
            self._pending = None
            self._mutex.unlock()

            try:
                result = self._process(image, target_size, dpr, lut)
                if result is not None:
                    self.frame_ready.emit(result, dpr)
            except Exception:
                pass

    def _process(self, image, target_size, dpr, lut):
        """Scale, convert to numpy, apply LUT, return QImage."""
        image = image.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        image = image.convertToFormat(QImage.Format.Format_RGB888)
        w, h = image.width(), image.height()
        bpl = image.bytesPerLine()
        ptr = image.bits()
        ptr.setsize(h * bpl)
        raw = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)
        arr = raw[:, :w * 3].reshape(h, w, 3).copy()

        graded = lut.apply_fast(arr)
        return QImage(graded.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()

    def stop(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()
        self._wait.wakeOne()
        self.wait()


class ScreenshotWorker(QThread):
    """Async worker for capturing screenshots via ffmpeg + LUT."""
    screenshot_done = pyqtSignal(str)  # filepath or "" on error

    def __init__(self, video_path, position_s, lut_filename, luts_dir,
                 camera_name, output_dir, counter, fps):
        super().__init__()
        self._video_path = video_path
        self._position_s = position_s
        self._lut_filename = lut_filename
        self._luts_dir = luts_dir
        self._camera_name = camera_name
        self._output_dir = output_dir
        self._counter = counter
        self._fps = fps

    def run(self):
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-ss", str(self._position_s),
                    "-i", self._video_path,
                    "-frames:v", "1",
                    "-f", "image2pipe", "-vcodec", "png", "pipe:1"
                ],
                capture_output=True, timeout=10
            )
            if result.returncode != 0:
                self.screenshot_done.emit("")
                return
        except Exception:
            self.screenshot_done.emit("")
            return

        from PIL import Image
        import io
        image = Image.open(io.BytesIO(result.stdout)).convert("RGB")

        # Apply LUT
        if self._lut_filename:
            lut_path = os.path.join(self._luts_dir, self._lut_filename)
            if os.path.exists(lut_path):
                from lib.lut_processor import LUTProcessor
                lut = LUTProcessor()
                if lut.load_cube(lut_path):
                    image = lut.apply_to_pil_image(image)

        os.makedirs(self._output_dir, exist_ok=True)

        # Build filename
        if self._camera_name:
            filename = f"{self._camera_name} {self._counter}.jpg"
        else:
            video_name = os.path.splitext(os.path.basename(self._video_path))[0]
            total_frames = int(self._position_s * self._fps)
            h = total_frames // (3600 * self._fps)
            m = (total_frames % (3600 * self._fps)) // (60 * self._fps)
            s = (total_frames % (60 * self._fps)) // self._fps
            f = total_frames % self._fps
            timecode = f"{h:02d}-{m:02d}-{s:02d}-{f:02d}"
            filename = f"{video_name}_{timecode}.jpg"

        filepath = os.path.join(self._output_dir, filename)
        image.save(filepath, "JPEG", quality=95)
        self.screenshot_done.emit(filepath)


class PeakVideoPreview(QWidget):
    """Pure video player widget with LUT support.

    No embedded timeline — that's handled externally by PeakStrip/ClipTimeline.
    """

    position_changed = pyqtSignal(int)  # position in ms
    video_changed = pyqtSignal(str)     # video filepath
    duration_changed = pyqtSignal(int)  # duration in ms
    screenshot_done = pyqtSignal(str)   # filepath or "" on error

    def __init__(self, parent=None):
        super().__init__(parent)

        self._video_files = []
        self._current_video = None
        self._duration_ms = 0
        self._is_seeking = False

        # LUT state
        self._lut_processor = None
        self._lut_loaded_filename = None
        self._last_frame = None

        # Clip playback state
        self._clip_playback_active = False
        self._clip_out_ms = 0

        # Camera name state
        self._camera_names = {}
        self._screenshot_counters = {}

        # Deferred play (when video not ready yet)
        self._deferred_play = None

        # Screenshot worker ref (prevent GC)
        self._screenshot_worker = None

        # LUT worker thread
        self._lut_worker = LUTWorker(self)
        self._lut_worker.frame_ready.connect(self._on_lut_frame_ready)
        self._lut_worker.start()

        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video display label
        self.video_label = QLabel()
        self.video_label.setMinimumHeight(300)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.video_label.setStyleSheet("background-color: #000000;")
        layout.addWidget(self.video_label, stretch=1)

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.video_sink = QVideoSink()
        self.video_sink.videoFrameChanged.connect(self._on_video_frame)
        self.player.setVideoOutput(self.video_sink)

        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.errorOccurred.connect(self._on_error)

    def _ensure_lut(self):
        import config
        from utils import LUTS_DIR
        from lib.lut_processor import LUTProcessor

        lut_filename = config.get("lut_path") or ""
        if lut_filename == self._lut_loaded_filename:
            return
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
        if not frame.isValid():
            return
        self._last_frame = frame

        image = frame.toImage()
        if image.isNull():
            return

        self._ensure_lut()

        if self._lut_processor and self._lut_processor.is_loaded():
            dpr = self.video_label.devicePixelRatioF()
            logical = self.video_label.size()
            target = QSize(int(logical.width() * dpr), int(logical.height() * dpr))
            self._lut_worker.submit(image, target, dpr, self._lut_processor)
        else:
            self.video_label.setPixmap(QPixmap.fromImage(image))

    def _on_lut_frame_ready(self, image, dpr):
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        self.video_label.setPixmap(pixmap)

    def refresh_lut(self):
        """Re-apply LUT to current frame (call after LUT selection change)."""
        self._lut_loaded_filename = None
        if self._last_frame and self._last_frame.isValid():
            self._on_video_frame(self._last_frame)

    # --- Video loading ---

    def set_videos(self, video_files: list):
        self._video_files = video_files
        if video_files:
            self._load_video(video_files[0])

    def load_video_at_index(self, index: int):
        if 0 <= index < len(self._video_files):
            path = self._video_files[index]
            name = self._camera_names.get(path, "")
            self._load_video(path)
            return name
        return ""

    def _load_video(self, filepath: str):
        self._current_video = filepath
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.player.play()
        QTimer.singleShot(50, self._show_first_frame)
        self.video_changed.emit(filepath)

    def _show_first_frame(self):
        self.player.pause()
        self.player.setPosition(0)

    # --- Camera names ---

    def set_camera_name(self, name: str):
        if self._current_video:
            self._camera_names[self._current_video] = name.strip()

    def get_current_camera_name(self) -> str:
        if self._current_video:
            return self._camera_names.get(self._current_video, "")
        return ""

    # --- Playback ---

    def play_from(self, in_ms: int, out_ms: int):
        """Play video from in_ms, stop at out_ms."""
        self._clip_out_ms = out_ms
        self._clip_playback_active = True
        if self._duration_ms > 0:
            self.player.setPosition(in_ms)
            self.player.play()
        else:
            # Video not ready yet — defer until duration is known
            self._deferred_play = (in_ms, out_ms)

    def _try_deferred_play(self):
        """Execute deferred play_from after video loads."""
        if hasattr(self, '_deferred_play') and self._deferred_play:
            in_ms, out_ms = self._deferred_play
            self._deferred_play = None
            self._clip_out_ms = out_ms
            self._clip_playback_active = True
            self.player.setPosition(in_ms)
            self.player.play()

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle_play_pause(self):
        """Toggle between play and pause. Returns True if now playing."""
        if self.is_playing():
            self.player.pause()
            return False
        else:
            self.player.play()
            return True

    def stop(self):
        self.player.stop()

    def stop_clip_playback(self):
        self._clip_playback_active = False

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def get_position(self) -> int:
        return self.player.position()

    def set_position(self, position_ms: int):
        self.player.setPosition(position_ms)

    def get_duration(self) -> int:
        return self._duration_ms

    # --- Player signals ---

    def _on_duration_changed(self, duration: int):
        self._duration_ms = duration
        self.duration_changed.emit(duration)
        self._try_deferred_play()

    def _on_position_changed(self, position: int):
        if not self._is_seeking:
            self.position_changed.emit(position)
            # Stop at out-point during clip playback
            if self._clip_playback_active and position >= self._clip_out_ms:
                self._clip_playback_active = False
                self.player.pause()
                self.player.setPosition(self._clip_out_ms)

    def _on_error(self, error):
        print(f"Video error: {error}, {self.player.errorString()}")

    # --- Async Screenshot ---

    def capture_screenshot_async(self, camera_name: str = ""):
        """Start async screenshot capture. Emits screenshot_done when finished."""
        if not self._current_video:
            self.screenshot_done.emit("")
            return

        import config
        from utils import EXPORT_DIR, LUTS_DIR
        from core.exporters import extract_guest_name
        from utils import MATERIAL_DIR

        position_ms = self.player.position()
        position_s = position_ms / 1000.0
        lut_filename = config.get("lut_path") or ""
        fps = config.get("fps") or 25

        gastname = extract_guest_name(MATERIAL_DIR)
        screenshots_dir = os.path.join(EXPORT_DIR, f"{gastname} - Screenshots")

        # Counter
        if camera_name:
            counter = self._screenshot_counters.get(camera_name, 0) + 1
            self._screenshot_counters[camera_name] = counter
        else:
            counter = 0

        self._screenshot_worker = ScreenshotWorker(
            self._current_video, position_s, lut_filename, LUTS_DIR,
            camera_name, screenshots_dir, counter, fps
        )
        self._screenshot_worker.screenshot_done.connect(self._on_screenshot_done)
        self._screenshot_worker.start()

    def _on_screenshot_done(self, filepath):
        self.screenshot_done.emit(filepath)
        self._screenshot_worker = None

    # --- Cleanup ---

    def cleanup(self):
        self._lut_worker.stop()
        if self._screenshot_worker and self._screenshot_worker.isRunning():
            self._screenshot_worker.wait(3000)
