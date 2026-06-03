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
