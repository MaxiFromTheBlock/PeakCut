# thumbnail_worker.py - async camera thumbnails for the assignment step

import hashlib
import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

from utils import FFMPEG_BIN, get_logger

_log = get_logger("peakcut.thumbnails")


def thumbnail_path_for_video(video_path: str, temp_dir: str) -> str:
    """Stable cache path keyed by absolute path + mtime.

    A changed file (new mtime) yields a new path so stale thumbnails are
    never reused.
    """
    abspath = os.path.abspath(video_path)
    try:
        mtime = os.path.getmtime(abspath)
    except OSError:
        mtime = 0
    digest = hashlib.sha1(f"{abspath}:{mtime}".encode()).hexdigest()[:16]
    return os.path.join(temp_dir, f"thumb_{digest}.jpg")


def build_thumbnail_command(video_path: str, output_path: str) -> list[str]:
    # Fast seek (-ss before -i), single frame, small scale.
    return [
        FFMPEG_BIN,
        "-y",
        "-ss", "2",
        "-i", video_path,
        "-frames:v", "1",
        "-vf", "scale=160:-1",
        "-q:v", "5",
        output_path,
    ]


class ThumbnailWorker(QThread):
    """Generates thumbnails sequentially off the main thread.

    One ffmpeg process at a time (not one per camera in parallel). The UI
    shows placeholders immediately and fills thumbnails as they arrive.
    """

    thumbnail_ready = pyqtSignal(str, str)   # video_path, thumbnail_path
    thumbnail_failed = pyqtSignal(str)       # video_path

    def __init__(self, video_paths: list[str], temp_dir: str, parent=None):
        super().__init__(parent)
        self._video_paths = list(video_paths)
        self._temp_dir = temp_dir

    def run(self):
        try:
            os.makedirs(self._temp_dir, exist_ok=True)
        except OSError:
            for video_path in self._video_paths:
                self.thumbnail_failed.emit(video_path)
            return

        for video_path in self._video_paths:
            out = thumbnail_path_for_video(video_path, self._temp_dir)
            if os.path.exists(out):
                self.thumbnail_ready.emit(video_path, out)
                continue
            try:
                result = subprocess.run(
                    build_thumbnail_command(video_path, out),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                if result.returncode == 0 and os.path.exists(out):
                    self.thumbnail_ready.emit(video_path, out)
                else:
                    self.thumbnail_failed.emit(video_path)
            except (subprocess.SubprocessError, OSError) as exc:
                _log.warning("Thumbnail failed for %s: %s", video_path, exc)
                self.thumbnail_failed.emit(video_path)
