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
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, ORIGIN_MARKER, marker_candidate_id)
from core.playback_windows import build_playback_window  # noqa: E402


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
            marker_track="/k.wav",
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
    ns._refresh_play_availability = lambda: None
    # Default: kein Scrub -> _resume_window aendert nichts (Clip-Preview).
    ns._scrubbed_pos = None
    ns.video_preview = types.SimpleNamespace(
        current_mix_position=lambda: None, set_position=lambda p: None)
    ns._resume_window = lambda w: ReviewPage._resume_window(ns, w)
    ns._has_file_source = lambda: ReviewPage._has_file_source(ns)
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
    cand = ClipCandidate(candidate_id=marker_candidate_id(0), origin=ORIGIN_MARKER,
                         anchor_ms=60000, peak_id=0,
                         boundary=ClipBoundary(40000, 90000), score=0.8)
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


def test_navigate_stops_controller_before_setting_frame():
    # P1 Carl-Gate-F: erst stoppen (sonst seekt stop_clip_at auf das alte
    # Clip-Out und überschreibt den neuen Frame), dann set_position.
    order = []
    fs = _fs(playing=True)
    fs.session.set_current_peak = lambda i: setattr(
        fs.session, "current_peak", i)
    fs.peak_label = types.SimpleNamespace(setText=lambda t: None)
    fs._video_files = ["/a.mp4"]
    fs.video_preview = types.SimpleNamespace(
        set_position=lambda p: order.append("set_position"))
    fs._controller.stop = lambda: order.append("stop")
    ReviewPage.navigate_to_peak(fs, 0)
    assert order.index("stop") < order.index("set_position")


def test_camera_change_stops_controller():
    # P2 Carl-Gate-F: Kamerawechsel während Playback stoppt den Controller.
    fs = _fs(playing=True)
    fs._video_files = ["/a.mp4"]
    fs.video_preview = types.SimpleNamespace(
        load_video_at_index=lambda i: None,
        get_current_brightness=lambda: 0,
        set_position=lambda p: None)
    fs.brightness_slider = types.SimpleNamespace(
        blockSignals=lambda b: None, setValue=lambda v: None)
    fs._update_brightness_label = lambda v: None
    ReviewPage._on_camera_changed(fs, 0)
    assert "stop" in fs._controller.calls


def test_slider_moved_stops_controller():
    fs = _fs(playing=True)
    fs.video_preview = types.SimpleNamespace(set_position=lambda p: None)
    ReviewPage._on_slider_moved(fs, 12345)
    assert "stop" in fs._controller.calls


def test_slider_pressed_stops_controller():
    fs = _fs(playing=True)
    fs.video_preview = types.SimpleNamespace(set_position=lambda p: None)
    fs.position_slider = types.SimpleNamespace(value=lambda: 5000)
    ReviewPage._on_slider_pressed(fs)
    assert "stop" in fs._controller.calls


def test_on_play_resumes_within_clip_from_scrub():
    # #76 (A): Scrub innerhalb des Clips -> Play ab Scrub-Stelle bis Clip-Ende.
    fs = _fs(mode="speak")     # speak-Fenster 50000-80000
    fs._scrubbed_pos = 65000
    ReviewPage.on_play(fs)
    w = _played(fs)[0][1]
    assert w.start_ms == 65000 and w.end_ms == 80000


def test_on_play_free_play_past_clip_open_end():
    # #76 (A): Scrub hinter das Clip-Ende -> frei ab Scrub-Stelle (offenes Ende).
    fs = _fs(mode="speak")     # Mix vorhanden im _fs-Projekt
    fs._scrubbed_pos = 200000
    ReviewPage.on_play(fs)
    w = _played(fs)[0][1]
    assert w.start_ms == 200000 and w.end_ms is None


def test_on_play_no_scrub_plays_clip_window():
    # Regression "nichts spielt beim ersten Play": ohne Scrub bleibt es beim
    # Clip-Fenster (kein async-Positions-Stale, kein Free-Play ab 0).
    fs = _fs(mode="speak")     # speak-Fenster 50000-80000, kein Scrub
    ReviewPage.on_play(fs)
    w = _played(fs)[0][1]
    assert w.start_ms == 50000 and w.end_ms == 80000


def test_on_play_key_ignores_scrub_stays_clip():
    # Regression "nichts spielt / Bild springt" im KEY-Modus: Scrub weit hinter
    # das Marker-Fenster darf KEIN Free-Play in die kurze Keyboard-Datei oeffnen.
    fs = _fs(mode="key")       # key-Fenster 60000-61000
    fs._scrubbed_pos = 600000  # weit hinter dem Fenster
    w = fs._resume_window(build_playback_window(fs.session, "key"))
    assert w.start_ms == 60000 and w.end_ms == 61000   # unveraendert, kein None


def test_slider_records_scrubbed_pos():
    fs = _fs(playing=True)
    fs.video_preview = types.SimpleNamespace(set_position=lambda p: None)
    ReviewPage._on_slider_moved(fs, 123456)
    assert fs._scrubbed_pos == 123456
