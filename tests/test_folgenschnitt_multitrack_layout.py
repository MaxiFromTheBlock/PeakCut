"""Slice B Task 1 — Contracts + Defaults.

Verriegelt die Plan-Datenform (Konstanten, normalize, Dataclasses,
Session-Default), bevor Task 2/3 die Layout-Logik draufsetzen und
Task 4 den XML-Writer dranbaut. Gate A: Carl-Bless dieser Datei vor
Layout-Build.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------
# 1. Konstanten + normalize_unused_clips_mode
# ---------------------------------------------------------------------


def test_module_constants_exist():
    """Drei Konstanten als single source of truth."""
    from core import folgenschnitt_multitrack_layout as m

    assert m.UNUSED_CLIPS_REMOVE == "remove"
    assert m.UNUSED_CLIPS_DISABLE == "disable"
    assert m.DEFAULT_UNUSED_CLIPS_MODE == "disable"


def test_normalize_returns_valid_modes_unchanged():
    from core.folgenschnitt_multitrack_layout import (
        normalize_unused_clips_mode,
        UNUSED_CLIPS_DISABLE,
        UNUSED_CLIPS_REMOVE,
    )

    assert normalize_unused_clips_mode("disable") == UNUSED_CLIPS_DISABLE
    assert normalize_unused_clips_mode("remove") == UNUSED_CLIPS_REMOVE


@pytest.mark.parametrize("value", [None, "", "garbage", "DISABLE", "Remove", 0, 123, [], {}])
def test_normalize_returns_default_for_invalid(value):
    """Ungueltige Werte (None, leer, Tippfehler, falsche Typen,
    Groesszeichen) → Default, kein Crash."""
    from core.folgenschnitt_multitrack_layout import (
        DEFAULT_UNUSED_CLIPS_MODE,
        normalize_unused_clips_mode,
    )

    assert normalize_unused_clips_mode(value) == DEFAULT_UNUSED_CLIPS_MODE


def test_normalize_default_is_disable():
    """Schutz gegen versehentliche Drift des Defaults im Bau."""
    from core.folgenschnitt_multitrack_layout import (
        DEFAULT_UNUSED_CLIPS_MODE,
        UNUSED_CLIPS_DISABLE,
    )

    assert DEFAULT_UNUSED_CLIPS_MODE == UNUSED_CLIPS_DISABLE


# ---------------------------------------------------------------------
# 2. Pure Dataclasses (Plan-Datenform)
# ---------------------------------------------------------------------


def test_video_clip_plan_fields_and_frozen():
    """VideoClipPlan haelt Timeline + Source-Range + enabled.
    Frozen, damit Plan-Daten zwischen Layout-Bau und XML-Writer
    nicht stillschweigend mutieren."""
    from core.folgenschnitt_multitrack_layout import VideoClipPlan

    clip = VideoClipPlan(
        start_ms=0,
        end_ms=4200,
        in_ms=0,
        out_ms=4200,
        enabled=True,
    )
    assert clip.start_ms == 0
    assert clip.end_ms == 4200
    assert clip.in_ms == 0
    assert clip.out_ms == 4200
    assert clip.enabled is True

    # Frozen-Garantie
    with pytest.raises(Exception):
        clip.start_ms = 999  # type: ignore[misc]


def test_video_track_plan_fields_and_frozen():
    """VideoTrackPlan haelt file_path + name + Liste von Clips.
    name ist fuer XML-<name>-Tag (z.B. 'Jan', 'Totale')."""
    from core.folgenschnitt_multitrack_layout import (
        VideoClipPlan,
        VideoTrackPlan,
    )

    clip = VideoClipPlan(start_ms=0, end_ms=100, in_ms=0, out_ms=100, enabled=True)
    track = VideoTrackPlan(
        file_path="/path/to/Jan.mp4",
        name="Jan",
        clips=(clip,),
    )
    assert track.file_path == "/path/to/Jan.mp4"
    assert track.name == "Jan"
    assert track.clips == (clip,)

    with pytest.raises(Exception):
        track.file_path = "/other"  # type: ignore[misc]


def test_audio_clip_plan_fields_and_frozen():
    from core.folgenschnitt_multitrack_layout import AudioClipPlan

    clip = AudioClipPlan(start_ms=0, end_ms=85365 * 40, in_ms=0, out_ms=85365 * 40)
    assert clip.start_ms == 0
    assert clip.end_ms == 85365 * 40

    with pytest.raises(Exception):
        clip.start_ms = 999  # type: ignore[misc]


def test_audio_track_plan_fields_and_frozen():
    from core.folgenschnitt_multitrack_layout import (
        AudioClipPlan,
        AudioTrackPlan,
    )

    clip = AudioClipPlan(start_ms=0, end_ms=100, in_ms=0, out_ms=100)
    track = AudioTrackPlan(
        file_path="/path/to/Mix.wav",
        name="Mix",
        clips=(clip,),
    )
    assert track.file_path == "/path/to/Mix.wav"
    assert track.name == "Mix"
    assert track.clips == (clip,)

    with pytest.raises(Exception):
        track.file_path = "/other"  # type: ignore[misc]


def test_multitrack_layout_plan_fields_and_frozen():
    """MultitrackLayoutPlan = Gesamtergebnis. uses_mix-Flag fuer
    Status-Hinweis bei Fallback auf echte Mics."""
    from core.folgenschnitt_multitrack_layout import (
        AudioClipPlan,
        AudioTrackPlan,
        MultitrackLayoutPlan,
        UNUSED_CLIPS_DISABLE,
        VideoClipPlan,
        VideoTrackPlan,
    )

    v_clip = VideoClipPlan(start_ms=0, end_ms=100, in_ms=0, out_ms=100, enabled=True)
    v_track = VideoTrackPlan(file_path="/jan.mp4", name="Jan", clips=(v_clip,))
    a_clip = AudioClipPlan(start_ms=0, end_ms=100, in_ms=0, out_ms=100)
    a_track = AudioTrackPlan(file_path="/mix.wav", name="Mix", clips=(a_clip,))

    plan = MultitrackLayoutPlan(
        video_tracks=(v_track,),
        audio_tracks=(a_track,),
        uses_mix=True,
        mode=UNUSED_CLIPS_DISABLE,
    )
    assert plan.video_tracks == (v_track,)
    assert plan.audio_tracks == (a_track,)
    assert plan.uses_mix is True
    assert plan.mode == UNUSED_CLIPS_DISABLE

    with pytest.raises(Exception):
        plan.uses_mix = False  # type: ignore[misc]


# ---------------------------------------------------------------------
# 3. PeakCutSession-Default
# ---------------------------------------------------------------------


def test_session_default_unused_clips_mode_is_disable():
    """Frische Session traegt DEFAULT_UNUSED_CLIPS_MODE als Initial-
    Wert auf session.folgenschnitt_unused_clips_mode."""
    from core.folgenschnitt_multitrack_layout import DEFAULT_UNUSED_CLIPS_MODE
    from core.project import PeakCutProject
    from core.session import PeakCutSession

    project = PeakCutProject()
    session = PeakCutSession(project, {"fps": 25})

    assert hasattr(session, "folgenschnitt_unused_clips_mode")
    assert session.folgenschnitt_unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


# ---------------------------------------------------------------------
# 4. build_video_track_order (Task 2)
# ---------------------------------------------------------------------


def _ca(path, shot_type, person=None):
    """Test-Helper: CameraAssignment."""
    from core.folgenschnitt_models import CameraAssignment
    return CameraAssignment(path=path, shot_type=shot_type, person=person)


def _ed(start_ms, end_ms, camera_path, speaker="X"):
    """Test-Helper: EditDecision."""
    from core.folgenschnitt_models import EditDecision
    return EditDecision(
        start_ms=start_ms, end_ms=end_ms,
        camera_path=camera_path, speaker=speaker, reason="test",
    )


def test_track_order_1plus1_totale_first_then_persons():
    """1plus1-Setup: V1=Totale, V2=Jan, V3=Tim."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [
        _ca("/Jan.mp4", "weit", "Jan"),
        _ca("/Tim.mp4", "weit", "Tim"),
        _ca("/Totale.mp4", "totale"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Tim.mp4", "Tim"),
    ]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/Totale.mp4", "/Jan.mp4", "/Tim.mp4"]


def test_track_order_hm_without_totale_in_assignment_order():
    """HM-Setup: 3 Kameras (Matze weit, Gast weit, Gast close), keine Totale.
    Reihenfolge V1=Matze, V2=Gast weit, V3=Gast close."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [
        _ca("/MatzeW.mp4", "weit", "Matze"),
        _ca("/GastW.mp4", "weit", "Gast"),
        _ca("/GastC.mp4", "nah_close", "Gast"),
    ]
    decisions = [_ed(0, 1000, "/MatzeW.mp4", "Matze")]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/MatzeW.mp4", "/GastW.mp4", "/GastC.mp4"]


def test_track_order_hm_with_totale_totale_first():
    """HM mit hypothetischer Totale: V1=Totale, dann Assignments."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [
        _ca("/MatzeW.mp4", "weit", "Matze"),
        _ca("/GastW.mp4", "weit", "Gast"),
        _ca("/Totale.mp4", "totale"),
        _ca("/GastC.mp4", "nah_close", "Gast"),
    ]
    decisions = [_ed(0, 1000, "/MatzeW.mp4", "Matze")]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/Totale.mp4", "/MatzeW.mp4", "/GastW.mp4", "/GastC.mp4"]


def test_track_order_unused_filtered_out():
    """shot_type='unused' wird gefiltert."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [
        _ca("/A.mp4", "weit", "A"),
        _ca("/B.mp4", "unused"),
        _ca("/C.mp4", "weit", "C"),
    ]
    decisions = [_ed(0, 1000, "/A.mp4", "A")]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/A.mp4", "/C.mp4"]


def test_track_order_dedup_by_path():
    """Duplicate-Path-Assignments: nur einmal."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [
        _ca("/A.mp4", "weit", "A"),
        _ca("/A.mp4", "weit", "B"),  # versehentliche Doppelzuweisung
    ]
    decisions = [_ed(0, 1000, "/A.mp4", "A")]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/A.mp4"]


def test_track_order_missing_decision_camera_appended():
    """Decision referenziert eine Kamera, die nicht in den Assignments
    steht (sollte nicht passieren, aber defensiv): wird hinten
    angehaengt damit kein aktiver Schnitt verloren geht."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [_ca("/A.mp4", "weit", "A")]
    decisions = [
        _ed(0, 1000, "/A.mp4", "A"),
        _ed(1000, 2000, "/Stufe2.mp4", "A"),  # nicht in Assignments
    ]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/A.mp4", "/Stufe2.mp4"]


def test_track_order_solo_one_track():
    """Solo: 1 Kamera → 1 Track."""
    from core.folgenschnitt_multitrack_layout import build_video_track_order

    assignments = [_ca("/Solo.mp4", "weit", "Solo")]
    decisions = [_ed(0, 1000, "/Solo.mp4", "Solo")]
    order = build_video_track_order(assignments, decisions)
    paths = [c.path for c in order]
    assert paths == ["/Solo.mp4"]


# ---------------------------------------------------------------------
# 5. build_multitrack_layout (Task 2)
# ---------------------------------------------------------------------


def test_layout_remove_mode_persons_only_active():
    """Remove-Modus: Person-Tracks haben nur aktive Clips."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Jan.mp4", "weit", "Jan"),
        _ca("/Tim.mp4", "weit", "Tim"),
        _ca("/Totale.mp4", "totale"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Tim.mp4", "Tim"),
        _ed(2000, 3000, "/Jan.mp4", "Jan"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    # 3 Tracks: V1=Totale, V2=Jan, V3=Tim
    assert len(tracks) == 3
    # V1 Totale: jede Decision
    assert len(tracks[0].clips) == 3
    # V2 Jan: 2 Decisions (Jan)
    assert len(tracks[1].clips) == 2
    # V3 Tim: 1 Decision
    assert len(tracks[2].clips) == 1
    # Im Remove-Modus alle clips enabled
    for t in tracks:
        for c in t.clips:
            assert c.enabled is True


def test_layout_disable_mode_all_tracks_all_decisions():
    """Disable-Modus: jeder Track hat jeden Decision-Clip, nur die
    aktive ist enabled."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Jan.mp4", "weit", "Jan"),
        _ca("/Tim.mp4", "weit", "Tim"),
        _ca("/Totale.mp4", "totale"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Tim.mp4", "Tim"),
        _ed(2000, 3000, "/Jan.mp4", "Jan"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_DISABLE,
    )
    assert len(tracks) == 3
    # Jeder Track hat alle 3 Decisions
    for t in tracks:
        assert len(t.clips) == 3
    # V1 Totale: alle enabled (Fallback-Schicht)
    assert all(c.enabled for c in tracks[0].clips)
    # V2 Jan: aktiv bei Decision 0 + 2 (enabled), 1 disabled
    assert tracks[1].clips[0].enabled is True
    assert tracks[1].clips[1].enabled is False
    assert tracks[1].clips[2].enabled is True
    # V3 Tim: nur Decision 1 enabled
    assert tracks[2].clips[0].enabled is False
    assert tracks[2].clips[1].enabled is True
    assert tracks[2].clips[2].enabled is False


def test_layout_remove_mode_has_no_disabled_clips():
    """Sanity: Remove-Modus hat keine enabled=False-Clips."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/A.mp4", "weit", "A"),
        _ca("/B.mp4", "weit", "B"),
    ]
    decisions = [
        _ed(0, 1000, "/A.mp4", "A"),
        _ed(1000, 2000, "/B.mp4", "B"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    for t in tracks:
        for c in t.clips:
            assert c.enabled is True


def test_layout_clip_source_range_equals_timeline_position():
    """Plan-Vertrag: in_ms/out_ms = start_ms/end_ms (Offset-Logik
    bleibt im Exporter)."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        build_video_track_layout,
    )

    assignments = [_ca("/A.mp4", "weit", "A")]
    decisions = [_ed(5000, 7500, "/A.mp4", "A")]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_DISABLE,
    )
    clip = tracks[0].clips[0]
    assert clip.start_ms == 5000
    assert clip.end_ms == 7500
    assert clip.in_ms == clip.start_ms
    assert clip.out_ms == clip.end_ms


def test_layout_totale_name_is_totale():
    """Name-Konvention: Totale-Track heisst 'Totale'."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Totale.mp4", "totale"),
        _ca("/A.mp4", "weit", "Jan"),
    ]
    decisions = [_ed(0, 1000, "/A.mp4", "Jan")]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    assert tracks[0].name == "Totale"


def test_layout_person_name_is_person_plus_shot():
    """Name-Konvention: Person-Track heisst '{person} {shot_type}'."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Jan.mp4", "weit", "Jan"),
        _ca("/Gast.mp4", "nah_close", "Gast"),
    ]
    decisions = [_ed(0, 1000, "/Jan.mp4", "Jan")]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    names = [t.name for t in tracks]
    assert "Jan weit" in names
    assert "Gast nah_close" in names


def test_layout_missing_decision_camera_name_basename_fallback():
    """Name-Fallback fuer Decision-Kamera ohne Assignment: Basename."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [_ca("/A.mp4", "weit", "A")]
    decisions = [
        _ed(0, 1000, "/A.mp4", "A"),
        _ed(1000, 2000, "/Mystery.mp4", "A"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    names = [t.name for t in tracks]
    assert "Mystery.mp4" in names


# ---------------------------------------------------------------------
# 6. build_audio_track_plan (Task 3)
# ---------------------------------------------------------------------


class _StubProject:
    """Minimaler Project-Stub fuer Audio-Tests (umgeht PyQt-Abhaengigkeiten)."""

    def __init__(self, mic_tracks):
        self.mic_tracks = list(mic_tracks)


def test_audio_plan_mix_only_when_mix_present():
    """Mix-Datei in mic_tracks → genau eine Audio-Spur mit Mix,
    uses_mix=True."""
    from core.folgenschnitt_multitrack_layout import build_audio_track_plan

    project = _StubProject([
        "/MIC1.wav",
        "/MIC2.wav",
        "/Hotel Matze - Test mix.wav",
    ])
    tracks, uses_mix = build_audio_track_plan(project, sequence_duration_ms=120000)

    assert uses_mix is True
    assert len(tracks) == 1
    assert "mix" in tracks[0].file_path.lower()
    assert len(tracks[0].clips) == 1
    assert tracks[0].clips[0].start_ms == 0
    assert tracks[0].clips[0].end_ms == 120000


def test_audio_plan_fallback_to_mics_when_no_mix():
    """Kein Mix → echte Mics als Fallback, uses_mix=False."""
    from core.folgenschnitt_multitrack_layout import build_audio_track_plan

    project = _StubProject(["/MIC1.wav", "/MIC2.wav"])
    tracks, uses_mix = build_audio_track_plan(project, sequence_duration_ms=60000)

    assert uses_mix is False
    assert len(tracks) == 2
    paths = sorted(t.file_path for t in tracks)
    assert paths == ["/MIC1.wav", "/MIC2.wav"]
    for t in tracks:
        assert len(t.clips) == 1
        assert t.clips[0].start_ms == 0
        assert t.clips[0].end_ms == 60000


def test_audio_plan_empty_when_no_tracks():
    """Keine Audio-Files → leere Plan-Liste, uses_mix=False."""
    from core.folgenschnitt_multitrack_layout import build_audio_track_plan

    project = _StubProject([])
    tracks, uses_mix = build_audio_track_plan(project, sequence_duration_ms=60000)

    assert tracks == ()
    assert uses_mix is False


# ---------------------------------------------------------------------
# 7. build_multitrack_layout (Integration aller drei Tasks)
# ---------------------------------------------------------------------


def test_full_layout_1plus1_disable_mode():
    """End-to-end: 1plus1 Disable-Modus produziert vollstaendigen
    MultitrackLayoutPlan."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        build_multitrack_layout,
    )

    assignments = [
        _ca("/Jan.mp4", "weit", "Jan"),
        _ca("/Tim.mp4", "weit", "Tim"),
        _ca("/Totale.mp4", "totale"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Tim.mp4", "Tim"),
    ]
    project = _StubProject(["/MIC1.wav", "/Mix.wav"])
    plan = build_multitrack_layout(
        decisions=decisions,
        camera_assignments=assignments,
        project=project,
        mode=UNUSED_CLIPS_DISABLE,
    )
    # 3 Video-Tracks
    assert len(plan.video_tracks) == 3
    # 1 Audio-Track (Mix-only)
    assert len(plan.audio_tracks) == 1
    assert plan.uses_mix is True
    assert plan.mode == UNUSED_CLIPS_DISABLE
    # Sequence-Dauer aus Decisions abgeleitet (max end_ms)
    assert plan.audio_tracks[0].clips[0].end_ms == 2000


# ---------------------------------------------------------------------
# 7b. Carl-P2-Fix (2026-06-03): Mehrfach-Totale-Edge-Case
# ---------------------------------------------------------------------


def test_layout_multiple_totale_only_first_is_fallback_remove():
    """Carl-P2: Wenn zwei Totale-Kameras zugewiesen sind, ist nur die
    ERSTE Fallback. Die zweite verhaelt sich wie eine normale Person-
    Kamera (Remove-Modus: nur Clips an aktiven Decisions)."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Totale1.mp4", "totale"),
        _ca("/Totale2.mp4", "totale"),
        _ca("/Jan.mp4", "weit", "Jan"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Jan.mp4", "Jan"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    by_path = {t.file_path: t for t in tracks}
    # Erste Totale (in track-order V1): Fallback-Schicht, alle Decisions
    assert len(by_path["/Totale1.mp4"].clips) == 2
    # Zweite Totale: NICHT-Fallback, keine aktiven Decisions → 0 Clips
    assert len(by_path["/Totale2.mp4"].clips) == 0


def test_layout_multiple_totale_only_first_is_fallback_disable():
    """Carl-P2 im Disable-Modus: erste Totale alle enabled, zweite
    Totale hat alle Decisions aber alle disabled (kein aktiver
    Decision)."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Totale1.mp4", "totale"),
        _ca("/Totale2.mp4", "totale"),
        _ca("/Jan.mp4", "weit", "Jan"),
    ]
    decisions = [
        _ed(0, 1000, "/Jan.mp4", "Jan"),
        _ed(1000, 2000, "/Jan.mp4", "Jan"),
    ]
    tracks = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_DISABLE,
    )
    by_path = {t.file_path: t for t in tracks}
    # Erste Totale: 2 Decisions, ALLE enabled (Fallback)
    t1 = by_path["/Totale1.mp4"]
    assert len(t1.clips) == 2
    assert all(c.enabled for c in t1.clips)
    # Zweite Totale: 2 Decisions, ALLE disabled (nie aktiv, keine
    # Fallback-Rolle)
    t2 = by_path["/Totale2.mp4"]
    assert len(t2.clips) == 2
    assert not any(c.enabled for c in t2.clips)


def test_layout_multiple_totale_with_decision_for_second_totale():
    """Edge-Case: zweite Totale ist aktiv in einer Decision → ihr
    Clip ist enabled (im Disable-Modus); im Remove-Modus hat sie
    diesen einen Clip."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        UNUSED_CLIPS_REMOVE,
        build_video_track_layout,
    )

    assignments = [
        _ca("/Totale1.mp4", "totale"),
        _ca("/Totale2.mp4", "totale"),
    ]
    decisions = [
        _ed(0, 1000, "/Totale2.mp4", "X"),
    ]
    # Remove: Totale1 hat alle (Fallback), Totale2 nur die aktive
    rt = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_REMOVE,
    )
    by_path_r = {t.file_path: t for t in rt}
    assert len(by_path_r["/Totale1.mp4"].clips) == 1
    assert len(by_path_r["/Totale2.mp4"].clips) == 1
    # Disable: beide haben den Clip; Totale1 als Fallback enabled,
    # Totale2 enabled weil aktiv
    dt = build_video_track_layout(
        assignments, decisions, UNUSED_CLIPS_DISABLE,
    )
    by_path_d = {t.file_path: t for t in dt}
    assert by_path_d["/Totale1.mp4"].clips[0].enabled is True
    assert by_path_d["/Totale2.mp4"].clips[0].enabled is True


def test_full_layout_hm_remove_mode_no_totale():
    """HM-Setup ohne Totale, Remove-Modus."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_REMOVE,
        build_multitrack_layout,
    )

    assignments = [
        _ca("/MatzeW.mp4", "weit", "Matze"),
        _ca("/GastW.mp4", "weit", "Gast"),
        _ca("/GastC.mp4", "nah_close", "Gast"),
    ]
    decisions = [
        _ed(0, 5000, "/MatzeW.mp4", "Matze"),
        _ed(5000, 10000, "/GastW.mp4", "Gast"),
    ]
    project = _StubProject(["/MIC1.wav", "/MIC2.wav"])  # kein Mix
    plan = build_multitrack_layout(
        decisions=decisions,
        camera_assignments=assignments,
        project=project,
        mode=UNUSED_CLIPS_REMOVE,
    )
    assert len(plan.video_tracks) == 3
    # Remove: jeder Track hat nur seine aktiven Decisions
    matze_track = next(t for t in plan.video_tracks if t.file_path == "/MatzeW.mp4")
    assert len(matze_track.clips) == 1
    gastw_track = next(t for t in plan.video_tracks if t.file_path == "/GastW.mp4")
    assert len(gastw_track.clips) == 1
    gastc_track = next(t for t in plan.video_tracks if t.file_path == "/GastC.mp4")
    assert len(gastc_track.clips) == 0  # Gast-Close nie aktiv
    # Audio: 2 Mic-Tracks (kein Mix)
    assert plan.uses_mix is False
    assert len(plan.audio_tracks) == 2
