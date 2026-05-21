import os
from concurrent.futures import ThreadPoolExecutor

from pydub import AudioSegment

from utils import parse_timecode_to_ms

from .audio_routing import get_speech_audio_segment
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
        self.speaker_activity_mic_assignments = []
        self.folgenschnitt_mic_assignments = []
        self.folgenschnitt_camera_assignments = []
        self.clip_candidates = []   # Roadmap #2: ClipCandidate je Peak
        self.peak_decisions = []    # Roadmap #2: redaktioneller Rückkanal
        # Roadmap #3 Stufe A: Transkript-Zustand formalisiert (nicht
        # mehr ad-hoc). transcript bleibt None — Stufe B liest das
        # gespeicherte Sidecar; ref = Referenzblock; error = Hinweis
        # wenn Sidecar fehlt/kaputt (Smart dann nicht verfügbar).
        self.transcript = None
        self.transcript_ref = None
        self.transcript_error: str | None = None
        self.folgenschnitt_skip_reason: str | None = None
        # True once the user has gone through the assignment step. Then a
        # deliberately empty assignment must NOT silently fall back to
        # analysis/default mics.
        self.folgenschnitt_assignment_applied = False

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
            # #71a Task 4 (2026-05-21): Mic-/Speak-Mode delegiert die
            # Audio-Wahl an den zentralen audio_routing-Helper.
            # Phasing-Wurzel (Mix-mit-Mics-Overlay) ist damit auch
            # im Review-Pfad behoben, nicht nur im MP3-Export.
            start = peak.in_point_ms
            end = peak.out_point_ms
            segment = get_speech_audio_segment(self, start, end)
            if segment is None:
                return

        play_audio(segment)

    def switch_mode(self):
        """Toggle between keyboard and mic mode."""
        self.mode = "mic" if self.mode == "keyboard" else "keyboard"
        self.play_current()

    def _bootstrap_clip_candidates(self):
        """Roadmap #2: pro Peak ein ClipCandidate (nicht ignoriert ->
        proposed, ignoriert -> discarded). Kein Decision (kein echter
        redaktioneller Akt mit Timestamp). Boundary defensiv (>start)."""
        from .clip_candidates import ClipBoundary, ClipCandidate, \
            PROPOSED, DISCARDED
        cands = []
        for pk in self.peaks:
            lo, hi = pk.in_point_ms, pk.out_point_ms
            if hi <= lo:                       # defensiv (Clamp-Edge)
                hi = lo + 1
            cands.append(ClipCandidate(
                peak_id=pk.index,
                boundary=ClipBoundary(lo, hi),
                status=DISCARDED if pk.ignored else PROPOSED))
        self.clip_candidates = cands
        self.peak_decisions = []

    def ignore_peak(self):
        """Mark current peak as ignored."""
        if not (0 <= self.current_peak < len(self.peaks)):
            return
        peak = self.peaks[self.current_peak]
        peak.ignored = True
        # Roadmap #2: Rückkanal — Candidate (via peak_id == Peak.index,
        # NICHT Listenposition) auf discarded, Decision anhängen.
        # Idempotent (transition no-op bei gleichem Status). Defensiv:
        # ist der Candidate published (terminal), bleibt er historisch
        # published — der Peak wird trotzdem ignoriert (wie bisher).
        from datetime import datetime
        from .clip_candidates import transition, DISCARDED, \
            ClipCandidateError
        for i, c in enumerate(self.clip_candidates):
            if c.peak_id != peak.index:
                continue
            try:
                new, dec = transition(
                    c, DISCARDED, now=datetime.now().isoformat(),
                    source="ignore_peak")
            except ClipCandidateError:
                break  # z.B. published -> bewusst nichts ändern
            if dec is not None:
                self.clip_candidates[i] = new
                self.peak_decisions.append(dec)
            break

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

        # Roadmap #2: Candidates aus Peaks bootstrappen (kein Decision —
        # keine echte redaktionelle Aktion mit Timestamp). Ein späterer
        # Archiv-Load (Projektakte v2) überschreibt das ggf. wieder.
        self._bootstrap_clip_candidates()

        from .folgenschnitt_models import (
            ActivityFrame,
            EditDecision,
            MicAssignment,
            SpeakerTurn,
        )

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
        self.speaker_activity_mic_assignments = [
            MicAssignment.from_dict(item)
            for item in results.get("speaker_activity_mic_assignments", [])
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
