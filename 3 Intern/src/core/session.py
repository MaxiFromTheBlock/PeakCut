import os
from PyQt6.QtCore import QObject, pyqtSignal
from pydub import AudioSegment

from .project import PeakCutProject
from .audio import detect_peaks, play_audio, stop_playback
from .sync import sync_videos


class PeakCutSession(QObject):
    """Holds the complete state of an analysis session."""

    # Signals
    peaks_found = pyqtSignal(list)
    peak_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(str)
    peak_ignored = pyqtSignal(int)
    status_update = pyqtSignal(str)

    def __init__(self, project: PeakCutProject, config: dict):
        super().__init__()
        self.project = project
        self.config = config

        # Peak state
        self.peaks: list[int] = []
        self.current_peak: int = 0
        self.ignored_peaks: set[int] = set()
        self.mode: str = "keyboard"

        # Audio data
        self.keyboard_audio: AudioSegment | None = None
        self.mic_audios: list[AudioSegment] = []

        # Sync data
        self.video_offsets: list[tuple[str, str]] = []

    def analyze(self):
        """Run sync + peak detection. Populates peaks, audio, and offsets."""
        os.makedirs(self.project.export_dir, exist_ok=True)

        # Step 1: Sync videos (if any)
        if self.project.videos:
            reference = self.project.get_reference_track()
            if reference:
                self.status_update.emit("Synchronisiere...")

                # Get temp_dir from utils path convention
                intern_dir = os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))))
                temp_dir = os.path.join(intern_dir, "temp")

                self.video_offsets = sync_videos(
                    video_files=self.project.videos,
                    reference_path=reference,
                    temp_dir=temp_dir,
                    fps=self.config.get("fps", 25),
                    status_fn=self.status_update.emit
                )
                self.status_update.emit(
                    f"Sync complete. {len(self.video_offsets)} offset(s) ready.")

        # Step 2: Peak detection
        if not self.project.keyboard_track:
            self.status_update.emit("No keyboard file found.")
            return

        self.status_update.emit("Analysiere Peaks...")

        self.peaks = detect_peaks(
            self.project.keyboard_track,
            self.config.get("threshold_factor", 0.4),
            self.config.get("min_gap_ms", 15000)
        )

        # Load audio segments
        self.keyboard_audio = AudioSegment.from_wav(self.project.keyboard_track)
        self.mic_audios = [AudioSegment.from_wav(f) for f in self.project.mic_tracks]
        self.current_peak = 0
        self.mode = "keyboard"

        self.status_update.emit(f"{len(self.peaks)} peaks detected.")
        self.peaks_found.emit(self.peaks)

    def next_peak(self) -> int:
        """Advance to next peak and play it."""
        if self.current_peak < len(self.peaks) - 1:
            self.current_peak += 1
            self.peak_changed.emit(self.current_peak)
            self.play_current()
        return self.current_peak

    def prev_peak(self) -> int:
        """Go back to previous peak and play it."""
        if self.current_peak > 0:
            self.current_peak -= 1
            self.peak_changed.emit(self.current_peak)
            self.play_current()
        return self.current_peak

    def play_current(self, index=None):
        """Play the current peak (keyboard or mic mode)."""
        if not self.peaks:
            return

        if index is not None:
            self.current_peak = index

        if self.current_peak >= len(self.peaks):
            return

        time_ms = self.peaks[self.current_peak]
        preview_duration = self.config.get("preview_duration_ms", 1000)
        context_duration = self.config.get("context_duration_ms", 15000)

        if self.mode == "keyboard":
            segment = self.keyboard_audio[time_ms:time_ms + preview_duration]
        else:
            start = max(0, time_ms - context_duration)
            end = time_ms + context_duration
            segment = self.mic_audios[0][start:end]
            for audio in self.mic_audios[1:]:
                segment = segment.overlay(audio[start:end])

        play_audio(segment)

    def switch_mode(self):
        """Toggle between keyboard and mic mode."""
        self.mode = "mic" if self.mode == "keyboard" else "keyboard"
        self.mode_changed.emit(self.mode)
        self.play_current()

    def ignore_peak(self):
        """Mark current peak as ignored."""
        self.ignored_peaks.add(self.current_peak)
        self.peak_ignored.emit(self.current_peak)

    def set_current_peak(self, index):
        """Set current peak index (bounds-checked)."""
        if 0 <= index < len(self.peaks):
            self.current_peak = index
            self.peak_changed.emit(self.current_peak)

    def get_active_peaks(self) -> list[tuple[int, int]]:
        """Return all non-ignored peaks as [(peak_number, time_ms)]."""
        active = []
        num = 1
        for i, t in enumerate(self.peaks):
            if i not in self.ignored_peaks:
                active.append((num, t))
                num += 1
        return active
