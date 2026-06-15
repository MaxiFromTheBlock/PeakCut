"""#76 Task 4 — PeakVideoPreview Clip-API (Carl-Plan 2026-06-15).

prepare_clip() setzt den Clip + springt auf den In-Punkt, startet aber NICHT;
play_prepared() startet. Das ist die Basis für den gemeinsamen Audio-Master-
Takt (Task 5). play_from bleibt abwärtskompatibel (= prepare + play).
Offset-Mapping bleibt unangetastet.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.video_preview_peak import PeakVideoPreview  # noqa: E402


def _spy(pv):
    calls = []
    pv.player.play = lambda: calls.append("play")
    pv.player.pause = lambda: calls.append("pause")
    pv.player.setPosition = lambda v: calls.append(("setPosition", v))
    return calls


def _seeked(calls):
    return any(isinstance(c, tuple) and c[0] == "setPosition" for c in calls)


def test_prepare_clip_seeks_but_does_not_play():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 100000
        calls = _spy(pv)
        pv.prepare_clip(50000, 80000)
        assert _seeked(calls)
        assert "play" not in calls
        assert pv._clip_out_ms == 80000
        assert pv._clip_playback_active is True
    finally:
        pv.cleanup()


def test_play_prepared_starts():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 100000
        pv.prepare_clip(50000, 80000)
        calls = _spy(pv)
        pv.play_prepared()
        assert "play" in calls
    finally:
        pv.cleanup()


def test_play_from_is_prepare_plus_play():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 100000
        calls = _spy(pv)
        pv.play_from(50000, 80000)
        assert _seeked(calls) and "play" in calls
        assert pv._clip_out_ms == 80000
    finally:
        pv.cleanup()


def test_stop_clip_at_pauses_deactivates_and_seeks_to_out():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 100000
        pv.play_from(50000, 80000)
        calls = _spy(pv)
        pv.stop_clip_at()
        assert "pause" in calls
        assert pv._clip_playback_active is False
        assert _seeked(calls)
    finally:
        pv.cleanup()


def test_pause_clip_pauses():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 100000
        pv.play_from(50000, 80000)
        calls = _spy(pv)
        pv.pause_clip()
        assert "pause" in calls
    finally:
        pv.cleanup()


def test_current_mix_position_is_get_position_alias():
    pv = PeakVideoPreview()
    try:
        assert pv.current_mix_position() == pv.get_position()
    finally:
        pv.cleanup()


def test_deferred_prepare_play_waits_for_duration():
    pv = PeakVideoPreview()
    try:
        pv._duration_ms = 0  # Video noch nicht geladen
        calls = _spy(pv)
        pv.prepare_clip(50000, 80000)
        assert "play" not in calls and not _seeked(calls)  # verschoben
        pv.play_prepared()
        assert "play" not in calls  # immer noch verschoben
        pv._on_duration_changed(100000)  # Duration kommt an
        assert _seeked(calls) and "play" in calls  # jetzt seek + start
    finally:
        pv.cleanup()
