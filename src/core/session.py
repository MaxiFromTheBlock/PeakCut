import os
from concurrent.futures import ThreadPoolExecutor

from pydub import AudioSegment

from utils import parse_timecode_to_ms

from .project import PeakCutProject
from .peak import Peak
from .playback import play_audio


class StatusUpdate:
    """Simple callback-based status update mechanism (no Qt dependency)."""

    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        """Register a callback function."""
        self._callbacks.append(callback)

    def emit(self, message: str):
        """Notify all registered callbacks."""
        for cb in self._callbacks:
            cb(message)


class PeakCutSession:
    """Holds the complete state of an analysis session.

    Analysis runs in a separate subprocess (analysis_process.py).
    Results are loaded via load_analysis_results().
    Audio is loaded lazily on first playback/export via load_audio_lazy().
    """

    def __init__(self, project: PeakCutProject, config: dict):
        self.status_update = StatusUpdate()
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

        # Folgenschnitt data (Stage 1 auto camera cut)
        self.speaker_activity = []
        self.speaker_turns = []
        self.folgenschnitt_edit_decisions = []
        self.speaker_activity_csv: str | None = None

    def play_current(self, index=None):
        """Play the current peak (keyboard or mic mode)."""
        if not self.peaks:
            return

        if index is not None:
            self.current_peak = index

        if self.current_peak >= len(self.peaks):
            return

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
        self.play_current()

    def ignore_peak(self):
        """Mark current peak as ignored."""
        if 0 <= self.current_peak < len(self.peaks):
            self.peaks[self.current_peak].ignored = True

    def set_current_peak(self, index):
        """Set current peak index (bounds-checked)."""
        if 0 <= index < len(self.peaks):
            self.current_peak = index

    def get_active_peaks(self) -> list[tuple[int, 'Peak']]:
        """Return all non-ignored peaks as [(peak_number, Peak)]."""
        active = []
        num = 1
        for peak in self.peaks:
            if not peak.ignored:
                active.append((num, peak))
                num += 1
        return active

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
            self._offset_lookup_ms[video_filename] = parse_timecode_to_ms(offset_str, fps)

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

        from .folgenschnitt_models import ActivityFrame, EditDecision, SpeakerTurn

        self.speaker_activity = [
            ActivityFrame.from_dict(item)
            for item in results.get("speaker_activity", [])
        ]
        self.speaker_turns = [
            SpeakerTurn.from_dict(item)
            for item in results.get("speaker_turns", [])
        ]
        self.folgenschnitt_edit_decisions = [
            EditDecision.from_dict(item)
            for item in results.get("folgenschnitt_edit_decisions", [])
        ]
        self.speaker_activity_csv = results.get("speaker_activity_csv")

        self.current_peak = 0
        self.mode = "keyboard"

    def load_audio_lazy(self):
        """Load audio segments on demand (after analysis results are loaded).

        Loads keyboard + all mic tracks in parallel via ThreadPool.
        """
        if self.keyboard_audio is None and self.project.keyboard_track:
            self.status_update.emit("Lade Audio...")
            all_paths = [self.project.keyboard_track] + list(self.project.mic_tracks)
            with ThreadPoolExecutor(max_workers=len(all_paths)) as executor:
                results = list(executor.map(AudioSegment.from_file, all_paths))
            self.keyboard_audio = results[0]
            self.mic_audios = results[1:]
            # Set duration bounds on peaks so out_point_ms can't exceed audio length
            duration_ms = len(self.keyboard_audio)
            for peak in self.peaks:
                peak._duration_ms = duration_ms
            self.status_update.emit("Audio geladen")
