# video_preview_peak.py - PeakCut Video Preview (video only, muted)

import os
import subprocess
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QSize, QThread, QMutex, QWaitCondition
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

_SCREENSHOT_TIMEOUT_S = 30
_WORKER_SHUTDOWN_WAIT_MS = 3000


class LUTWorker(QThread):
    """Worker thread for LUT frame processing off the main thread.

    Only processes the latest submitted frame — intermediate frames are dropped.
    Has its OWN LUTProcessor instance to avoid thread-safety issues.
    """
    frame_ready = pyqtSignal(QImage, float)  # processed image, device pixel ratio

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._pending = None  # (QImage, QSize, float, lut_path)
        self._abort = False
        # Worker owns its own LUTProcessor - thread safe
        self._lut_processor = None
        self._loaded_lut_path = None

    def submit(self, image, target_size, dpr, lut_path, brightness=0):
        """Submit frame for processing. Drops any pending unprocessed frame.

        Args:
            lut_path: Full path to .cube file (worker loads its own copy)
            brightness: Brightness offset (-100 to +100), 0 = neutral
        """
        self._mutex.lock()
        self._pending = (image.copy(), target_size, dpr, lut_path, brightness)  # Copy image for thread safety
        self._mutex.unlock()
        self._wait.wakeOne()

    def run(self):
        from lib.lut_processor import LUTProcessor

        while True:
            self._mutex.lock()
            while self._pending is None and not self._abort:
                self._wait.wait(self._mutex)
            if self._abort:
                self._mutex.unlock()
                return
            image, target_size, dpr, lut_path, brightness = self._pending
            self._pending = None
            self._mutex.unlock()

            try:
                # Load LUT if needed (worker's own instance)
                if lut_path != self._loaded_lut_path:
                    self._lut_processor = LUTProcessor()
                    if lut_path and os.path.exists(lut_path):
                        self._lut_processor.load_cube(lut_path)
                    self._loaded_lut_path = lut_path

                result = self._process(image, target_size, dpr, brightness)
                if result is not None:
                    self.frame_ready.emit(result, dpr)
            except Exception as e:
                print(f"LUT processing error: {e}", file=__import__('sys').stderr)

    def _process(self, image, target_size, dpr, brightness=0):
        """Scale, convert to numpy, apply LUT + brightness, return QImage."""
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

        # Brightness BEFORE LUT (like Premiere exposure → LUT pipeline)
        if brightness != 0:
            factor = 2 ** (brightness / 100.0)  # -100→0.5x, 0→1.0x, +100→2.0x
            arr = np.clip(arr.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        if self._lut_processor and self._lut_processor.is_loaded():
            arr = self._lut_processor.apply_fast(arr)

        return QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()

    def stop(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()
        self._wait.wakeOne()
        self.wait()


class ScreenshotWorker(QThread):
    """Async worker for screenshots - uses ffmpeg for everything (including LUT).

    This keeps all heavy processing in the ffmpeg subprocess,
    avoiding conflicts with the main thread's LUTWorker.
    """
    screenshot_done = pyqtSignal(str)  # filepath or "" on error

    def __init__(self, video_path, position_s, lut_filename, luts_dir,
                 camera_name, output_dir, counter, fps, brightness=0):
        super().__init__()
        self._video_path = video_path
        self._position_s = position_s
        self._lut_filename = lut_filename
        self._luts_dir = luts_dir
        self._camera_name = camera_name
        self._output_dir = output_dir
        self._counter = counter
        self._fps = fps
        self._brightness = brightness

    def run(self):
        os.makedirs(self._output_dir, exist_ok=True)

        # Build output filename
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

        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-y",  # Overwrite output
            "-ss", str(self._position_s),  # Seek before input (fast)
            "-i", self._video_path,
            "-frames:v", "1",
        ]

        # Build video filter chain (brightness BEFORE LUT, like Premiere)
        filters = []
        if self._brightness != 0:
            factor = 2 ** (self._brightness / 100.0)  # -100→0.5x, 0→1.0x, +100→2.0x
            # Linear RGB multiplication (matches live preview exactly)
            expr = f"clip(val*{factor:.4f},0,255)"
            filters.append(f"lutrgb=r='{expr}':g='{expr}':b='{expr}'")
        if self._lut_filename:
            lut_path = os.path.join(self._luts_dir, self._lut_filename)
            if os.path.exists(lut_path):
                filters.append(f"lut3d='{lut_path}'")
        if filters:
            cmd.extend(["-vf", ",".join(filters)])

        # Output as high-quality JPEG
        cmd.extend(["-q:v", "2", filepath])

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=_SCREENSHOT_TIMEOUT_S)
            if result.returncode == 0 and os.path.exists(filepath):
                self.screenshot_done.emit(filepath)
            else:
                self.screenshot_done.emit("")
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"Screenshot error: {e}", file=__import__('sys').stderr)
            self.screenshot_done.emit("")


class PeakVideoPreview(QWidget):
    """Video player widget with LUT support.

    Video plays MUTED - audio sync with mix is handled separately.
    No embedded timeline — that's handled externally by ClipTimeline/ScrubTimeline.
    """

    position_changed = pyqtSignal(int)  # position in ms
    video_changed = pyqtSignal(str)     # video filepath
    duration_changed = pyqtSignal(int)  # duration in ms
    screenshot_done = pyqtSignal(str)   # filepath or "" on error

    def __init__(self, parent=None):
        super().__init__(parent)

        self._video_files = []
        self._current_video = None
        self._current_video_index = 0
        self._duration_ms = 0
        self._is_seeking = False

        # Session reference (for video offsets)
        self._session = None
        self._video_offset_ms = 0

        # LUT state (main thread no longer needs LUTProcessor - worker has its own)
        self._last_frame_image = None  # Stored as QImage copy for refresh_lut()

        # Clip playback state
        self._clip_playback_active = False
        self._clip_out_ms = 0

        # Brightness state (per camera)
        self._brightness_values: dict[str, int] = {}

        # Camera name state
        self._camera_names = {}
        self._screenshot_counters = {}

        # Deferred play (when video not ready yet)
        self._deferred_play = None

        # Screenshot workers (parallel queue — each runs independently)
        self._screenshot_workers: list[ScreenshotWorker] = []

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
        self.audio_output.setMuted(True)  # MUTED - no camera audio
        self.player.setAudioOutput(self.audio_output)

        self.video_sink = QVideoSink()
        self.video_sink.videoFrameChanged.connect(self._on_video_frame)
        self.player.setVideoOutput(self.video_sink)

        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.errorOccurred.connect(self._on_error)

    def _get_lut_path(self):
        """Get the current LUT file path (or None if disabled)."""
        import config
        from utils import LUTS_DIR

        lut_filename = config.get("lut_path") or ""
        if not lut_filename:
            return None

        lut_full_path = os.path.join(LUTS_DIR, lut_filename)
        if os.path.exists(lut_full_path):
            return lut_full_path
        return None

    def _on_video_frame(self, frame):
        if not frame.isValid():
            return

        image = frame.toImage()
        if image.isNull():
            return

        # Store a COPY of the image, not the frame
        # QVideoFrame is only valid during this callback - storing it causes crashes
        self._last_frame_image = image.copy()

        lut_path = self._get_lut_path()
        brightness = self.get_current_brightness()

        if lut_path or brightness != 0:
            # Send to worker thread for LUT/brightness processing
            dpr = self.video_label.devicePixelRatioF()
            logical = self.video_label.size()
            target = QSize(int(logical.width() * dpr), int(logical.height() * dpr))
            self._lut_worker.submit(image, target, dpr, lut_path, brightness)
        else:
            # No processing needed - display directly
            self.video_label.setPixmap(QPixmap.fromImage(image))

    def _on_lut_frame_ready(self, image, dpr):
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        self.video_label.setPixmap(pixmap)

    def refresh_lut(self):
        """Re-apply LUT/brightness to current frame (call after LUT or brightness change)."""
        # Re-process the stored image copy with new LUT/brightness setting
        if hasattr(self, '_last_frame_image') and self._last_frame_image and not self._last_frame_image.isNull():
            lut_path = self._get_lut_path()
            brightness = self.get_current_brightness()
            if lut_path or brightness != 0:
                dpr = self.video_label.devicePixelRatioF()
                logical = self.video_label.size()
                target = QSize(int(logical.width() * dpr), int(logical.height() * dpr))
                self._lut_worker.submit(self._last_frame_image.copy(), target, dpr, lut_path, brightness)
            else:
                self.video_label.setPixmap(QPixmap.fromImage(self._last_frame_image))

    # --- Session & Offset ---

    def set_session(self, session):
        """Set session for video offset access."""
        self._session = session
        self._update_video_offset()

    def _update_video_offset(self):
        """Update offset for current video."""
        if self._session and self._current_video:
            self._video_offset_ms = self._session.get_video_offset_ms(self._current_video)
        else:
            self._video_offset_ms = 0

    def _mix_to_video_ms(self, mix_ms: int) -> int:
        """Convert mix audio position to video position (apply offset)."""
        return max(0, mix_ms + self._video_offset_ms)

    def _video_to_mix_ms(self, video_ms: int) -> int:
        """Convert video position to mix audio position (remove offset)."""
        return video_ms - self._video_offset_ms

    # --- Video loading ---

    def set_videos(self, video_files: list):
        self._video_files = video_files
        if video_files:
            self._current_video_index = 0
            self._load_video(video_files[0])

    def load_video_at_index(self, index: int):
        if 0 <= index < len(self._video_files):
            self._current_video_index = index
            path = self._video_files[index]
            name = self._camera_names.get(path, "")
            self._load_video(path)
            return name
        return ""

    def _load_video(self, filepath: str):
        self._current_video = filepath
        self._update_video_offset()
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.player.play()
        # Delay before pausing to allow first frame to render
        _FIRST_FRAME_DELAY_MS = 100
        QTimer.singleShot(_FIRST_FRAME_DELAY_MS, self._show_first_frame)
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

    # --- Brightness ---

    def set_brightness(self, value: int):
        """Set brightness offset for current camera (-100 to +100)."""
        if self._current_video:
            self._brightness_values[self._current_video] = value

    def get_current_brightness(self) -> int:
        """Get brightness offset for current camera."""
        if self._current_video:
            return self._brightness_values.get(self._current_video, 0)
        return 0

    # --- Playback ---

    def play_from(self, in_ms: int, out_ms: int):
        """Play video from in_ms, stop at out_ms. Positions are in MIX coordinates."""
        # Store out point in MIX coordinates for comparison
        self._clip_out_ms = out_ms
        self._clip_playback_active = True
        if self._duration_ms > 0:
            # Convert mix position to video position
            video_in = self._mix_to_video_ms(in_ms)
            self.player.setPosition(video_in)
            self.player.play()
        else:
            # Video not ready yet — defer until duration is known (store MIX coordinates)
            self._deferred_play = (in_ms, out_ms)

    def _try_deferred_play(self):
        """Execute deferred play_from after video loads."""
        if hasattr(self, '_deferred_play') and self._deferred_play:
            in_ms, out_ms = self._deferred_play  # MIX coordinates
            self._deferred_play = None
            self._clip_out_ms = out_ms  # Keep in MIX coordinates
            self._clip_playback_active = True
            # Convert mix position to video position
            video_in = self._mix_to_video_ms(in_ms)
            self.player.setPosition(video_in)
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
        """Get current position in MIX coordinates."""
        return self._video_to_mix_ms(self.player.position())

    def set_position(self, position_ms: int):
        """Set position using MIX coordinates."""
        video_pos = self._mix_to_video_ms(position_ms)
        self.player.setPosition(video_pos)

    def get_duration(self) -> int:
        return self._duration_ms

    # --- Player signals ---

    def _on_duration_changed(self, duration: int):
        self._duration_ms = duration
        self.duration_changed.emit(duration)
        self._try_deferred_play()

    def _on_position_changed(self, position: int):
        """Handle position change from player. position is in VIDEO coordinates."""
        if not self._is_seeking:
            # Convert video position to mix position for external consumers
            mix_position = self._video_to_mix_ms(position)
            self.position_changed.emit(mix_position)
            # Stop at out-point during clip playback (compare in MIX coordinates)
            if self._clip_playback_active and mix_position >= self._clip_out_ms:
                self._clip_playback_active = False
                self.player.pause()
                # Seek to exact out point in VIDEO coordinates
                video_out = self._mix_to_video_ms(self._clip_out_ms)
                self.player.setPosition(video_out)

    def _on_error(self, error):
        print(f"Video error: {error}, {self.player.errorString()}")

    # --- Screenshot ---

    def capture_screenshot_async(self, camera_name: str = ""):
        """Start async screenshot capture. Emits screenshot_done when finished.

        Multiple screenshots can run in parallel — each gets its own worker.
        """
        if not self._current_video:
            self.screenshot_done.emit("")
            return

        import config
        from utils import EXPORT_DIR, LUTS_DIR

        position_ms = self.player.position()
        position_s = position_ms / 1000.0
        lut_filename = config.get("lut_path") or ""
        fps = config.get("fps") or 25

        gastname = self._session.project.guest_name if self._session else "Unknown"
        screenshots_dir = os.path.join(EXPORT_DIR, f"{gastname} - Screenshots")

        # Counter
        if camera_name:
            counter = self._screenshot_counters.get(camera_name, 0) + 1
            self._screenshot_counters[camera_name] = counter
        else:
            counter = 0

        brightness = self.get_current_brightness()

        worker = ScreenshotWorker(
            self._current_video, position_s, lut_filename, LUTS_DIR,
            camera_name, screenshots_dir, counter, fps, brightness
        )
        worker.screenshot_done.connect(self._on_screenshot_done)
        worker.screenshot_done.connect(lambda _, w=worker: self._cleanup_screenshot_worker(w))
        self._screenshot_workers.append(worker)
        worker.start()

    def _on_screenshot_done(self, filepath):
        self.screenshot_done.emit(filepath)

    def _cleanup_screenshot_worker(self, worker):
        """Remove finished worker from list and schedule deletion."""
        if worker in self._screenshot_workers:
            self._screenshot_workers.remove(worker)
        worker.deleteLater()

    # --- Cleanup ---

    def cleanup(self):
        self._lut_worker.stop()
        for worker in self._screenshot_workers:
            if worker.isRunning():
                worker.wait(_WORKER_SHUTDOWN_WAIT_MS)
        self._screenshot_workers.clear()
