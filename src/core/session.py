import os
from concurrent.futures import ThreadPoolExecutor

from pydub import AudioSegment

from utils import parse_timecode_to_ms

from .playback_modes import normalize_playback_mode, next_playback_mode
from .project import PeakCutProject
from .peak import Peak


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
        # #76: Wiedergabe-Modus key/speak/smart (aus Config, normalisiert).
        self.mode: str = normalize_playback_mode(config.get("playback_mode"))

        # Audio data
        self.keyboard_audio: AudioSegment | None = None
        self.mix_audio: AudioSegment | None = None
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
        # Slice B: Multi-Track-Folgenschnitt-XML — Toggle "Unused Clips".
        # Default kommt aus folgenschnitt_multitrack_layout (single source).
        from .folgenschnitt_multitrack_layout import DEFAULT_UNUSED_CLIPS_MODE
        self.folgenschnitt_unused_clips_mode = DEFAULT_UNUSED_CLIPS_MODE

    def switch_mode(self):
        """#76: zyklischer Modus-Wechsel key -> speak -> smart. KEIN Auto-Play
        mehr — die Wiedergabe steuert die ReviewPage über den Controller."""
        self.mode = next_playback_mode(self.mode)

    @staticmethod
    def _compute_reconciled_marker_candidates(existing_candidates, peaks):
        """Reine Berechnung (keine Seiteneffekte) fuer
        `_reconcile_marker_candidates`. Gleicht NUR die Partition
        origin == marker ab statt die gesamte Kandidatenliste zu ersetzen.

        Bestehende Marker-Kandidaten behalten ihren Bearbeitungszustand,
        fehlende werden ergaenzt, Nicht-Marker-Kandidaten (Fremdquellen wie
        auto/transcript/manual) bleiben unangetastet.

        GRENZE (Carl): gilt fuer einen UNVERAENDERTEN Marker-Satz.
        marker:<peak_id> ist ueber Analyselaeufe hinweg NICHT stabil, sobald
        Marker eingefuegt/entfernt werden — echte Reanalyse mit veraendertem
        Marker-Satz braucht ein zeitliches Event-Matching und ist ein
        eigener spaeterer Schritt.

        Fix-Runde 1 (Pruefer-Befund 1): die Eindeutigkeitspruefung laeuft
        (auch) gegen die FERTIGE Liste `keep`, nicht nur gegen
        `existing_candidates` — sonst entgehen ihr Dubletten, die erst
        WAEHREND dieser Methode entstehen (Fremdkandidat mit `marker:<n>`-ID
        fuer einen bisher fehlenden Marker-Kandidaten; zwei Peaks mit
        demselben `index`). Reine Funktion (statt Instanzmethode mit
        Seiteneffekt), damit `load_analysis_results` sie gegen lokale, noch
        nicht committete Peaks aufrufen kann (Fix-Runde 1, Befund 2 —
        Atomaritaet).

        Fix-Runde 2 (Pruefer-Befund): die Marker-Partition von
        `existing_candidates` wird VOR dem Aufbau von `by_id` auf
        Eindeutigkeit geprueft. Eine Dict-Comprehension
        (`{c.candidate_id: c for c in ... if origin==MARKER}`) wuerde zwei
        gleich benannte Marker-Kandidaten sonst still zusammenfallen lassen
        (der letzte gewinnt) — GENAU BEVOR die spaetere `seen`-Pruefung
        ueber `keep` ueberhaupt etwas sehen koennte, weil `keep` dann nur
        noch einen Eintrag mit dieser ID enthaelt. Bearbeitungszustand
        (Status, editierte Boundary) des verworfenen Kandidaten waere ohne
        Fehler verschwunden. Der Fehler muss fliegen, BEVOR irgendetwas
        verworfen wurde.
        """
        from .clip_candidates import (
            ClipBoundary, ClipCandidate, ClipCandidateError,
            ORIGIN_MARKER, PROPOSED, DISCARDED, marker_candidate_id)

        by_id = {}
        for c in existing_candidates:
            if c.origin != ORIGIN_MARKER:
                continue
            if c.candidate_id in by_id:
                raise ClipCandidateError(
                    f"Doppelte candidate_id in der Marker-Partition: "
                    f"{c.candidate_id!r}")
            by_id[c.candidate_id] = c

        keep = [c for c in existing_candidates if c.origin != ORIGIN_MARKER]

        for pk in peaks:
            cid = marker_candidate_id(pk.index)
            existing = by_id.get(cid)
            if existing is not None:
                keep.append(existing)       # Bearbeitungszustand bleibt
                continue
            lo, hi = pk.in_point_ms, pk.out_point_ms
            if hi <= lo:                    # defensiv (Clamp-Edge)
                hi = lo + 1
            keep.append(ClipCandidate(
                candidate_id=cid, origin=ORIGIN_MARKER,
                anchor_ms=pk.position_ms, peak_id=pk.index,
                boundary=ClipBoundary(lo, hi),
                status=DISCARDED if pk.ignored else PROPOSED))

        seen = set()
        for c in keep:
            if c.candidate_id in seen:
                raise ClipCandidateError(
                    f"Doppelte candidate_id: {c.candidate_id!r}")
            seen.add(c.candidate_id)

        keep.sort(key=lambda c: (c.anchor_ms, c.candidate_id))
        # peak_decisions bewusst NICHT angefasst (kein Zugriff hier drin).
        return keep

    def _reconcile_marker_candidates(self):
        """Instanzmethode: gleicht `self.clip_candidates` gegen
        `self.peaks` ab (Delegation an die reine Berechnung oben).
        Fuer den atomaren Pfad in `load_analysis_results` siehe dort —
        die ruft die reine Berechnung direkt mit lokalen Peaks auf,
        BEVOR `self.peaks` ueberschrieben wird."""
        self.clip_candidates = self._compute_reconciled_marker_candidates(
            self.clip_candidates, self.peaks)

    # Rueckwaertskompatibler Name: project_archive.py:319-320 ruft ihn per
    # hasattr(session, "_bootstrap_clip_candidates") auf (Save-Pfad, falls
    # eine Akte ohne Candidates gespeichert wird). Alias statt Umbenennung
    # der Aufrufstelle, damit dieser Pfad nicht still ausfaellt.
    _bootstrap_clip_candidates = _reconcile_marker_candidates

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
        from .candidate_view import marker_candidate_for_peak
        target = marker_candidate_for_peak(self, peak.index)
        if target is not None:
            i = self.clip_candidates.index(target)
            try:
                new, dec = transition(
                    target, DISCARDED, now=datetime.now().isoformat(),
                    source="ignore_peak")
            except ClipCandidateError:
                new, dec = None, None   # z.B. published (terminal) -> nichts aendern
            if dec is not None:
                self.clip_candidates[i] = new
                self.peak_decisions.append(dec)

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
        # Fix-Runde 1 (Befund 2): Peaks/Offsets/Kandidaten erst LOKAL
        # aufbauen und die Reconciliation GEGEN DIESE lokalen Peaks laufen
        # lassen — self.peaks bleibt bis zum Erfolg unangetastet. Fliegt
        # dabei ein ClipCandidateError, bleibt die Session unveraendert
        # (alte Peaks + alte Kandidaten passen weiter zueinander), statt
        # mit neuen Peaks und alten, dazu nicht mehr passenden Kandidaten
        # stehen zu bleiben.
        video_offsets = results.get("video_offsets", [])
        fps = self.config.get("fps", 25)
        offset_lookup_updates = {}
        for video_filename, offset_str in video_offsets:
            offset_lookup_updates[video_filename] = parse_timecode_to_ms(offset_str, fps)

        peak_data = results.get("peaks", [])
        peaks = []
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
            peaks.append(peak)

        # Task 2: NUR die Marker-Partition abgleichen, nicht ersetzen.
        # Fremdquellen, Bearbeitungszustand und peak_decisions bleiben.
        # Ein späterer Archiv-Load (Projektakte v2) überschreibt das ggf.
        # wieder (lädt die gespeicherte Wahrheit). Laeuft gegen die
        # LOKALEN `peaks` (noch nicht self.peaks) — kann also raisen,
        # ohne dass vorher schon etwas an der Session veraendert wurde.
        new_candidates = self._compute_reconciled_marker_candidates(
            self.clip_candidates, peaks)

        # Alles durch -> jetzt erst gemeinsam auf self uebernehmen.
        self.video_offsets = video_offsets
        self._offset_lookup_ms.update(offset_lookup_updates)
        self.peaks = peaks
        self.clip_candidates = new_candidates

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
        self.mode = normalize_playback_mode(self.mode)

    def load_audio_lazy(self):
        """Load audio segments on demand (after analysis results are loaded).

        Loads marker/keyboard + structural mix + legacy mic tracks in
        parallel via ThreadPool. During #77 Gate B, mic_tracks still may
        contain the Mix; mic_audios therefore intentionally stays 1:1
        aligned to project.mic_tracks while mix_audio is exposed
        separately.
        """
        if self.keyboard_audio is None and self.project.keyboard_track:
            self.status_update.emit("Lade Audio...")
            all_paths = []

            def add_path(path):
                if path and path not in all_paths:
                    all_paths.append(path)

            add_path(self.project.keyboard_track)
            add_path(getattr(self.project, "mix_track", None))
            for path in self.project.mic_tracks:
                add_path(path)

            with ThreadPoolExecutor(max_workers=len(all_paths)) as executor:
                results = list(executor.map(AudioSegment.from_file, all_paths))
            loaded = dict(zip(all_paths, results))

            self.keyboard_audio = loaded[self.project.keyboard_track]
            mix_track = getattr(self.project, "mix_track", None)
            self.mix_audio = loaded.get(mix_track) if mix_track else None
            self.mic_audios = [
                loaded[path] for path in self.project.mic_tracks
            ]
            # Set duration bounds on peaks so out_point_ms can't exceed audio length
            duration_ms = len(self.keyboard_audio)
            for peak in self.peaks:
                peak._duration_ms = duration_ms
            self.status_update.emit("Audio geladen")
