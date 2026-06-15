"""#76 Task 6 — ReviewPage-Dispatch über den Controller (Fake-Self).

on_play dispatcht den aktuellen Modus (key/speak/smart) an den Controller;
Smart ohne gültigen Kandidaten -> lauter Status, kein Start; Mode-Toggle
zyklt + stoppt + persistiert; Navigation stoppt + spielt nicht automatisch.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402
from core.peak import Peak  # noqa: E402
from core.clip_candidates import ClipCandidate, ClipBoundary  # noqa: E402


class FakeController:
    def __init__(self, playing=False):
        self.calls = []
        self._playing = playing

    def is_playing(self):
        return self._playing

    def play(self, window, source):
        self.calls.append(("play", window, source))
        self._playing = True

    def stop(self):
        self.calls.append("stop")
        self._playing = False


def _peak():
    p = Peak(index=0, position_ms=60000)
    p.set_in_point(50000)
    p.set_out_point(80000)
    return p


def _fs(mode="key", candidates=None, playing=False):
    ns = types.SimpleNamespace()
    ns.session = types.SimpleNamespace(
        mode=mode, peaks=[_peak()], current_peak=0,
        clip_candidates=candidates or [],
        config={"preview_duration_ms": 1000},
        project=types.SimpleNamespace(
            keyboard_track="/k.wav",
            mic_tracks=["/MIC1.wav", "/Folge - Mix.wav"], videos=[]))
    ns._controller = FakeController(playing)
    ns._events = []
    ns.status_message = types.SimpleNamespace(
        emit=lambda m: ns._events.append(m))
    ns.play_btn = types.SimpleNamespace(
        setText=lambda t: None, setEnabled=lambda b: None,
        setToolTip=lambda t: None)
    ns.mode_btn = types.SimpleNamespace(setText=lambda t: None)
    ns._is_playing = False
    ns._start_play_state = lambda: ReviewPage._start_play_state(ns)
    ns._stop_play_state = lambda: ReviewPage._stop_play_state(ns)
    ns._refresh_sinn_btn = lambda: None
    return ns


def _played(fs):
    return [c for c in fs._controller.calls if isinstance(c, tuple)]


def test_on_play_key_dispatches_to_controller():
    fs = _fs(mode="key")
    ReviewPage.on_play(fs)
    assert _played(fs) and _played(fs)[0][0] == "play"
    assert fs._is_playing is True


def test_on_play_stops_when_already_playing():
    fs = _fs(playing=True)
    ReviewPage.on_play(fs)
    assert "stop" in fs._controller.calls
    assert fs._is_playing is False


def test_on_play_smart_without_candidate_is_disabled_no_play():
    fs = _fs(mode="smart", candidates=[])
    ReviewPage.on_play(fs)
    assert not _played(fs)
    assert fs._events                      # lauter Status statt Start


def test_on_play_smart_with_candidate_plays():
    cand = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000),
                         score=0.8)
    fs = _fs(mode="smart", candidates=[cand])
    ReviewPage.on_play(fs)
    assert _played(fs) and _played(fs)[0][0] == "play"


def test_mode_toggle_cycles_stops_and_persists(monkeypatch):
    fs = _fs(mode="key", playing=True)
    saved = {}
    monkeypatch.setattr("gui.review_page.config.set_value",
                        lambda k, v: saved.__setitem__(k, v))
    fs.session.switch_mode = lambda: setattr(fs.session, "mode", "speak")
    ReviewPage._on_mode_toggle(fs)
    assert "stop" in fs._controller.calls
    assert fs.session.mode == "speak"
    assert saved.get("playback_mode") == "speak"


def test_navigate_stops_playback_no_autoplay():
    fs = _fs(playing=True)
    fs.session.set_current_peak = lambda i: setattr(
        fs.session, "current_peak", i)
    fs.peak_label = types.SimpleNamespace(setText=lambda t: None)
    fs._video_files = []
    ReviewPage.navigate_to_peak(fs, 0)
    assert "stop" in fs._controller.calls
    assert not _played(fs)                  # kein Auto-Play
