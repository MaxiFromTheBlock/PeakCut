import os
from PyQt6.QtCore import QObject, pyqtSignal
from pydub import AudioSegment

from .project import PeakCutProject
from .peak import Peak
from .audio import detect_peaks, play_audio, stop_playback
from .sync import sync_videos


class PeakCutSession(QObject):
    """Holds the complete state of an analysis session."""

    # Signals
    peaks_found = pyqtSignal(list)
    peak_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(str)
    peak_ignored = pyqtSignal(int)
    clip_adjusted = pyqtSignal(int)
    status_update = pyqtSignal(str)

    def __init__(self, project: PeakCutProject, config: dict):
        super().__init__()
        self.project = project
        self.config = config

        # Peak state
        self.peaks: list[Peak] = []
        self.current_peak: int = 0
        self.mode: str = "keyboard"

        # Audio data
        self.keyboard_audio: AudioSegment | None = None
        self.mic_audios: list[AudioSegment] = []

        # Sync data
        self.video_offsets: list[tuple[str, str]] = []
        self._offset_lookup_ms: dict[str, int] = {}  # video filename -> offset in ms

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
                # Build offset lookup for quick access
                fps = self.config.get("fps", 25)
                for video_filename, offset_str in self.video_offsets:
                    self._offset_lookup_ms[video_filename] = self._parse_timecode_to_ms(offset_str, fps)
                self.status_update.emit(
                    f"Sync complete. {len(self.video_offsets)} offset(s) ready.")

        # Step 2: Peak detection
        if not self.project.keyboard_track:
            self.status_update.emit("No keyboard file found.")
            return

        self.status_update.emit("Analysiere Peaks...")

        raw = detect_peaks(
            self.project.keyboard_track,
            self.config.get("threshold_factor", 0.4),
            self.config.get("min_gap_ms", 15000)
        )

        ctx = self.config.get("context_duration_ms", 15000)
        self.peaks = [Peak(i, t, ctx) for i, t in enumerate(raw)]

        # Load audio segments
        self.keyboard_audio = AudioSegment.from_file(self.project.keyboard_track)
        self.mic_audios = [AudioSegment.from_file(f) for f in self.project.mic_tracks]
        self.current_peak = 0
        self.mode = "keyboard"

        self.status_update.emit(f"{len(self.peaks)} peaks detected.")
        self.peaks_found.emit([p.position_ms for p in self.peaks])

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

        # Ensure audio is loaded (lazy loading after subprocess analysis)
        self.load_audio_lazy()

        if not self.keyboard_audio:
            return

        peak = self.peaks[self.current_peak]
        time_ms = peak.position_ms
        preview_duration = self.config.get("preview_duration_ms", 1000)

        if self.mode == "keyboard":
            segment = self.keyboard_audio[time_ms:time_ms + preview_duration]
        else:
            start = peak.in_point_ms
            end = peak.out_point_ms
            if not self.mic_audios:
                return
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
        self.peaks[self.current_peak].ignored = True
        self.peak_ignored.emit(self.current_peak)

    def set_current_peak(self, index):
        """Set current peak index (bounds-checked)."""
        if 0 <= index < len(self.peaks):
            self.current_peak = index
            self.peak_changed.emit(self.current_peak)

    def get_active_peaks(self) -> list[tuple[int, 'Peak']]:
        """Return all non-ignored peaks as [(peak_number, Peak)]."""
        active = []
        num = 1
        for peak in self.peaks:
            if not peak.ignored:
                active.append((num, peak))
                num += 1
        return active

    def adjust_clip(self, index, in_ms=None, out_ms=None):
        """Adjust In/Out points for a peak."""
        if 0 <= index < len(self.peaks):
            peak = self.peaks[index]
            if in_ms is not None:
                peak.set_in_point(in_ms)
            if out_ms is not None:
                peak.set_out_point(out_ms)
            self.clip_adjusted.emit(index)

    def reset_clip(self, index):
        """Reset In/Out points for a peak to default context."""
        if 0 <= index < len(self.peaks):
            ctx = self.config.get("context_duration_ms", 15000)
            self.peaks[index].reset_offsets(ctx)
            self.clip_adjusted.emit(index)

    def get_video_offset_ms(self, video_path: str) -> int:
        """Get offset in ms for a video file. Returns 0 if not found."""
        filename = os.path.basename(video_path)
        return self._offset_lookup_ms.get(filename, 0)

    def load_analysis_results(self, results: dict):
        """Load analysis results from subprocess.

        Args:
            results: Dict with 'peaks' (list of peak dicts) and 'video_offsets' (list of tuples)
        """
        # Load video offsets
        self.video_offsets = results.get("video_offsets", [])
        fps = self.config.get("fps", 25)
        for video_filename, offset_str in self.video_offsets:
            self._offset_lookup_ms[video_filename] = self._parse_timecode_to_ms(offset_str, fps)

        # Load peaks
        peak_data = results.get("peaks", [])
        self.peaks = []
        for p in peak_data:
            peak = Peak(
                index=p["index"],
                position_ms=p["position_ms"],
                context_ms=p.get("context_ms", self.config.get("context_duration_ms", 15000))
            )
            if p.get("in_point_ms") is not None:
                peak.set_in_point(p["in_point_ms"])
            if p.get("out_point_ms") is not None:
                peak.set_out_point(p["out_point_ms"])
            if p.get("ignored"):
                peak.ignored = True
            self.peaks.append(peak)

        self.current_peak = 0
        self.mode = "keyboard"

        # Emit signal
        self.peaks_found.emit([p.position_ms for p in self.peaks])

    def load_audio_lazy(self):
        """Load audio segments on demand (after analysis results are loaded)."""
        if self.keyboard_audio is None and self.project.keyboard_track:
            self.status_update.emit("Lade Audio...")
            self.keyboard_audio = AudioSegment.from_file(self.project.keyboard_track)
            self.mic_audios = [AudioSegment.from_file(f) for f in self.project.mic_tracks]
            self.status_update.emit("Audio geladen")

    def get_mix_audio(self) -> 'AudioSegment | None':
        """Get the mixed mic audio for playback."""
        # Ensure audio is loaded
        self.load_audio_lazy()

        if not self.mic_audios:
            return None
        if len(self.mic_audios) == 1:
            return self.mic_audios[0]
        # Mix all mic tracks
        mixed = self.mic_audios[0]
        for audio in self.mic_audios[1:]:
            mixed = mixed.overlay(audio)
        return mixed

    @staticmethod
    def _parse_timecode_to_ms(tc_str: str, fps: int) -> int:
        """Parse timecode string (HH:MM:SS:FF) to milliseconds."""
        negative = tc_str.startswith("-")
        tc_str = tc_str.lstrip("-")
        parts = tc_str.split(":")
        if len(parts) != 4:
            return 0
        hours, minutes, seconds, frames = map(int, parts)
        total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + int(frames * 1000 / fps)
        return -total_ms if negative else total_ms
