# mic_preview_worker.py - short audio preview for the assignment step

import subprocess
from io import BytesIO

from PyQt6.QtCore import QThread, pyqtSignal

from utils import FFMPEG_BIN, get_logger

_log = get_logger("peakcut.micpreview")


def build_mic_preview_command(path: str, duration_s: float = 5.0, start_s: float = 0.0) -> list[str]:
    # Fast seek (-ss before -i), short duration, raw wav to stdout.
    return [
        FFMPEG_BIN,
        "-ss", str(start_s),
        "-t", str(duration_s),
        "-i", path,
        "-f", "wav",
        "-",
    ]


class MicPreviewWorker(QThread):
    """Plays a short snippet of a mic track off the main thread.

    Pure verification helper — never changes any data. Decodes only the
    short window (no full-track load). play_audio() already calls
    sa.stop_all(), so a new click interrupts a running preview.
    """

    failed = pyqtSignal()

    def __init__(self, path: str, start_s: float = 0.0, duration_s: float = 5.0, parent=None):
        super().__init__(parent)
        self._path = path
        self._start_s = start_s
        self._duration_s = duration_s

    def run(self):
        try:
            result = subprocess.run(
                build_mic_preview_command(self._path, self._duration_s, self._start_s),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if result.returncode != 0 or not result.stdout:
                self.failed.emit()
                return
            from pydub import AudioSegment
            from core.playback import play_audio

            segment = AudioSegment.from_file(BytesIO(result.stdout), format="wav")
            play_audio(segment)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            _log.warning("Mic preview failed for %s: %s", self._path, exc)
            self.failed.emit()
