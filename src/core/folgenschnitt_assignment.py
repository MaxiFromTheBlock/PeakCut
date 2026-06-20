# folgenschnitt_assignment.py — Qt-freie Datenschicht des Zuordnungs-Schritts.
#
# Aus gui/assignment_page.py herausgehoben (2026-06-20, Carl-Plan-Vorbedingung
# für den Web-Zuordnungs-Screen), damit PeakCut-web denselben Kern AUFRUFT statt
# ihn nachzubauen (kein Drift). Reine Logik — KEIN PyQt, keine Widgets/Signals/
# Worker. Verhalten unverändert; gui/assignment_page.py importiert diese Symbole
# zurück.
import os
from dataclasses import dataclass, field

from .folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_TOTAL,
    SHOT_UNUSED,
    SHOT_WIDE,
    PERSONLESS_SHOT_TYPES,
    CameraAssignment,
    MicAssignment,
)
from .folgenschnitt_pipeline import (
    build_default_folgenschnitt_mic_assignments,
    has_minimum_folgenschnitt_assignment,
)
from .audio_routing import is_mix_track
from .folgenschnitt_multitrack_layout import (
    DEFAULT_UNUSED_CLIPS_MODE,
    normalize_unused_clips_mode,
)


def _default_unused_clips_mode() -> str:
    return DEFAULT_UNUSED_CLIPS_MODE


NEUTRAL_SHOT_LABEL = "— bitte zuordnen —"

SHOT_CHOICES = [
    (NEUTRAL_SHOT_LABEL, None),
    ("Weit", SHOT_WIDE),
    ("Nah/Close", SHOT_CLOSE),
    ("Halbnah", SHOT_MEDIUM),
    ("Totale", SHOT_TOTAL),
    ("— nicht nutzen", SHOT_UNUSED),
]


def preview_start_s_for_mic(session, speaker_key: str) -> float:
    """Start of the *longest* sustained run where this mic is the active
    speaker (~0.5 s before its begin), so the person is actually talking
    through it — not just a one-sentence first hit. Fallback 0.0."""
    frames = [
        f
        for f in (getattr(session, "speaker_activity", []) or [])
        if f.smoothed_speaker == speaker_key and f.confidence > 0
    ]
    if not frames:
        return 0.0
    best_start = frames[0].start_ms
    best_len = 1
    run_start = frames[0].start_ms
    run_len = 1
    prev = frames[0]
    for frame in frames[1:]:
        if frame.start_ms <= prev.end_ms + 150:
            run_len += 1
        else:
            run_start = frame.start_ms
            run_len = 1
        if run_len > best_len:
            best_len = run_len
            best_start = run_start
        prev = frame
    return max(0.0, best_start / 1000 - 0.5)


# ══════════════════════════════════════════════════════════════
# Pure data layer (unit-tested without Qt)
# ══════════════════════════════════════════════════════════════

@dataclass
class CameraRow:
    path: str
    filename: str
    shot_type: str | None
    person: str | None


@dataclass
class MicRow:
    track_index: int
    path: str
    filename: str
    person: str
    speaker_key: str


@dataclass
class AssignmentState:
    camera_rows: list[CameraRow]
    mic_rows: list[MicRow]
    people: list[str] = field(default_factory=list)
    # Slice B Task 7 (Carl-Plan 2026-06-03): Multi-Track-Layout-Toggle
    # auf der Zuordnungs-Seite. Default = "disable" (Max 2026-06-03).
    unused_clips_mode: str = field(
        default_factory=lambda: _default_unused_clips_mode()
    )

    def to_mic_assignments(self) -> list[MicAssignment]:
        return [
            MicAssignment(
                track_index=r.track_index,
                path=r.path,
                person=r.person,
                speaker_key=r.speaker_key,
            )
            for r in self.mic_rows
            if (r.person or "").strip()
        ]

    def to_camera_assignments(self) -> list[CameraAssignment]:
        # Neutral (unassigned) rows have shot_type None and are skipped.
        # Crash-Schutz: ein Personen-Shot (Weit/Nah/Halbnah) OHNE Person ist
        # unvollständig -> ebenfalls überspringen. Sonst würde
        # CameraAssignment einen ValueError werfen ("person must not be empty")
        # und beim "Weiter" den Button-Slot hart crashen. Personenlose Shots
        # (Totale/unused) bleiben — die brauchen keine Person.
        result = []
        for r in self.camera_rows:
            if not r.shot_type:
                continue
            if (r.shot_type not in PERSONLESS_SHOT_TYPES
                    and not (r.person or "").strip()):
                continue
            result.append(
                CameraAssignment(path=r.path, shot_type=r.shot_type,
                                 person=r.person))
        return result

    def is_complete(self) -> bool:
        ok, _ = has_minimum_folgenschnitt_assignment(
            self.to_mic_assignments(), self.to_camera_assignments()
        )
        return ok


def build_assignment_state(session, video_files) -> AssignmentState:
    project = getattr(session, "project", None)
    analysis_mics = list(
        getattr(session, "speaker_activity_mic_assignments", []) or []
    )
    if not analysis_mics:
        analysis_mics = build_default_folgenschnitt_mic_assignments(project)
    analysis_mics = [m for m in analysis_mics if not is_mix_track(m.path)]

    # speaker_key + path are technical (needed for Folgenschnitt mapping and
    # the Hörprobe). The *person* is deliberately left empty — no analysis/
    # convention default may pre-fill it.
    mic_rows = [
        MicRow(m.track_index, m.path, os.path.basename(m.path), "", m.speaker_key)
        for m in analysis_mics
    ]

    # Cameras start neutral too: a guessed-but-wrong default that looks
    # filled-in is worse than an explicit "not yet assigned".
    camera_rows = [
        CameraRow(path, os.path.basename(path), None, None)
        for path in video_files
    ]

    # Shared person list starts empty; it grows from what the user types.
    # Slice B Task 7: Mode aus Session lesen (normalize_unused_clips_mode
    # filtert missing/invalid → Default, kein Crash).
    mode = normalize_unused_clips_mode(
        getattr(session, "folgenschnitt_unused_clips_mode", None)
    )
    return AssignmentState(camera_rows, mic_rows, [], unused_clips_mode=mode)
