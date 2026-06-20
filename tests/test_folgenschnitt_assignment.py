"""Qt-freier Kern-Test der Zuordnungs-Datenschicht.

2026-06-20 aus gui/assignment_page.py in core/folgenschnitt_assignment.py
gehoben, damit PeakCut-web den Kern AUFRUFT statt ihn nachzubauen. Dieser Test
importiert DIREKT aus core (kein gui, kein PyQt) und friert das unveränderte
Verhalten ein (Charakterisierung der Extraktion).
"""
from types import SimpleNamespace

from core.folgenschnitt_models import SHOT_TOTAL, SHOT_WIDE, MicAssignment
from core.folgenschnitt_multitrack_layout import (
    UNUSED_CLIPS_DISABLE,
    UNUSED_CLIPS_REMOVE,
)
from core.folgenschnitt_assignment import (
    AssignmentState,
    CameraRow,
    NEUTRAL_SHOT_LABEL,
    SHOT_CHOICES,
    build_assignment_state,
    preview_start_s_for_mic,
)


def _session(mic_assignments=None, speaker_activity=None, unused_clips_mode=None):
    project = SimpleNamespace(
        guest_name="Tester", mic_tracks=["/m/MIC1.wav", "/m/MIC2.wav"]
    )
    s = SimpleNamespace(
        project=project,
        speaker_activity_mic_assignments=mic_assignments or [],
        speaker_activity=speaker_activity or [],
    )
    if unused_clips_mode is not None:
        s.folgenschnitt_unused_clips_mode = unused_clips_mode
    return s


def _frame(speaker, start_ms, end_ms, conf=1.0):
    return SimpleNamespace(
        smoothed_speaker=speaker, confidence=conf, start_ms=start_ms, end_ms=end_ms
    )


def test_shot_choices_shape_unchanged():
    assert SHOT_CHOICES[0] == (NEUTRAL_SHOT_LABEL, None)
    assert [c[0] for c in SHOT_CHOICES] == [
        NEUTRAL_SHOT_LABEL, "Weit", "Nah/Close", "Halbnah", "Totale", "— nicht nutzen",
    ]


def test_build_assignment_state_neutral_cameras_empty_mic_person():
    mics = [
        MicAssignment(0, "/m/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/m/MIC2.wav", "Gast", "mic_2"),
    ]
    state = build_assignment_state(
        _session(mic_assignments=mics), ["/m/CamA.mp4", "/m/CamB.mp4"]
    )
    assert [r.filename for r in state.camera_rows] == ["CamA.mp4", "CamB.mp4"]
    assert all(r.shot_type is None and r.person is None for r in state.camera_rows)
    assert [r.speaker_key for r in state.mic_rows] == ["mic_1", "mic_2"]
    assert [r.person for r in state.mic_rows] == ["", ""]
    assert state.people == []


def test_build_assignment_state_filters_mix_out_of_mics():
    mics = [
        MicAssignment(0, "/m/MIC1.wav", "A", "mic_1"),
        MicAssignment(1, "/m/Sheila Mix.mp3", "G", "mic_mix"),
        MicAssignment(2, "/m/MIC2.wav", "B", "mic_2"),
    ]
    state = build_assignment_state(_session(mic_assignments=mics), [])
    assert [r.path for r in state.mic_rows] == ["/m/MIC1.wav", "/m/MIC2.wav"]


def test_unused_clips_mode_default_and_normalize_unchanged():
    assert build_assignment_state(_session(), []).unused_clips_mode == UNUSED_CLIPS_DISABLE
    assert (
        build_assignment_state(
            _session(unused_clips_mode=UNUSED_CLIPS_REMOVE), []
        ).unused_clips_mode
        == UNUSED_CLIPS_REMOVE
    )
    assert (
        build_assignment_state(_session(unused_clips_mode="quatsch"), []).unused_clips_mode
        == UNUSED_CLIPS_DISABLE
    )


def test_preview_start_finds_longest_block():
    frames = [
        _frame("mic_1", 1000, 1200),     # kurzer Einzeltreffer
        _frame("mic_2", 1300, 5000),
        _frame("mic_1", 20000, 20200),   # Beginn des längsten Blocks
        _frame("mic_1", 20300, 20500),
        _frame("mic_1", 20600, 20800),
    ]
    start = preview_start_s_for_mic(_session(speaker_activity=frames), "mic_1")
    assert abs(start - 19.5) < 1e-6  # 20000ms - 0.5s


def test_preview_start_fallback_zero_without_activity():
    assert preview_start_s_for_mic(_session(), "mic_1") == 0.0


def test_to_camera_assignments_skips_person_shot_without_person():
    state = AssignmentState(
        camera_rows=[CameraRow("/m/A.mp4", "A.mp4", SHOT_WIDE, "")],
        mic_rows=[],
    )
    assert state.to_camera_assignments() == []  # Crash-Schutz statt ValueError


def test_to_camera_assignments_totale_forces_person_none():
    state = AssignmentState(
        camera_rows=[CameraRow("/m/A.mp4", "A.mp4", SHOT_TOTAL, "Matze")],
        mic_rows=[],
    )
    assert state.to_camera_assignments()[0].person is None
