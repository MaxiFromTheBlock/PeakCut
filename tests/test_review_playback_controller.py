"""#76 Task 5 — Qt Playback Controller (Carl-Plan 2026-06-15).

Gemeinsame Uhr: Audio = Master, Video folgt und wird bei Drift korrigiert.
Mit Fake-Playern getestet (kein echtes Medium). Readiness-Gate vor dem
gemeinsamen Start (Audio UND Video, P1 Carl-Gate-E), harte stop()/cleanup().
drift_updated meldet den POST-Korrektur-Restdrift (P1 Carl-Gate-E),
corrected zählt Korrekturen separat.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_playback_controller import ReviewPlaybackController  # noqa: E402
from core.playback_windows import PlaybackWindow  # noqa: E402
from core.playback_audio_source import PlaybackAudioSource  # noqa: E402


class _Signal:
    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        self._cbs.append(cb)

    def emit(self, *a):
        for cb in list(self._cbs):
            cb(*a)


class FakeAudio:
    def __init__(self, status="loaded"):
        self.calls = []
        self._pos = 0
        self._status = status
        self.mediaStatusChanged = _Signal()

    def setSource(self, url):
        self.calls.append("setSource")

    def setPosition(self, p):
        self._pos = p
        self.calls.append(("setPos", p))

    def position(self):
        return self._pos

    def play(self):
        self.calls.append("play")

    def stop(self):
        self.calls.append("stop")

    def mediaStatus(self):
        return self._status

    def set_status(self, s):
        self._status = s
        self.mediaStatusChanged.emit(s)

    def deleteLater(self):
        self.calls.append("deleteLater")


class FakeVideo:
    def __init__(self, duration=100000):
        self.calls = []
        self._dur = duration
        self._mix = 0
        self.duration_changed = _Signal()

    def prepare_clip(self, a, b):
        self.calls.append(("prepare", a, b))

    def play_prepared(self):
        self.calls.append("play_prepared")

    def current_mix_position(self):
        return self._mix

    def set_position(self, p):
        self._mix = p
        self.calls.append(("setpos", p))

    def stop_clip_at(self, o=None):
        self.calls.append(("stop_clip_at", o))

    def get_duration(self):
        return self._dur

    def set_duration(self, d):
        self._dur = d
        self.duration_changed.emit(d)


def _ctrl(fa, fv, tol=40):
    return ReviewPlaybackController(
        fv, tolerance_ms=tol, audio_player_factory=lambda: fa,
        audio_ready_states={"loaded", "buffered"}, audio_end_states={"end"})


_WIN = PlaybackWindow("speak", 50000, 80000)
_SRC = PlaybackAudioSource(path="/a.wav", media_start_ms=50000, media_end_ms=80000,
                           timeline_start_ms=50000, timeline_end_ms=80000)


def _setpos_calls(fv):
    return [c for c in fv.calls if isinstance(c, tuple) and c[0] == "setpos"]


def test_play_starts_both_when_ready():
    fa, fv = FakeAudio(), FakeVideo()
    _ctrl(fa, fv).play(_WIN, _SRC)
    assert ("prepare", 50000, 80000) in fv.calls
    assert "play_prepared" in fv.calls
    assert "play" in fa.calls
    assert ("setPos", 50000) in fa.calls


def test_video_readiness_retriggers_begin():
    # P1.1: Audio ready, Video noch nicht -> kein Start; kommt die Video-
    # Duration nach, startet der Controller (kein Timeout).
    fa, fv = FakeAudio(status="loaded"), FakeVideo(duration=0)
    _ctrl(fa, fv).play(_WIN, _SRC)
    assert "play" not in fa.calls
    fv.set_duration(100000)
    assert "play" in fa.calls


def test_audio_readiness_retriggers_begin():
    # symmetrisch: Video ready, Audio kommt nach.
    fa, fv = FakeAudio(status="loading"), FakeVideo(duration=100000)
    _ctrl(fa, fv).play(_WIN, _SRC)
    assert "play" not in fa.calls
    fa.set_status("loaded")
    assert "play" in fa.calls


def test_audio_is_master_drift_corrects_video():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    fa._pos = 60000
    fv._mix = 60100          # Vor-Korrektur-Drift 100 > 40
    c._on_tick()
    assert ("setpos", 60000) in fv.calls


def test_small_drift_not_corrected():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    fa._pos = 60000
    fv._mix = 60030
    fv.calls.clear()
    c._on_tick()
    assert _setpos_calls(fv) == []


def test_drift_updated_is_post_correction_residual():
    # P1.2: bei Korrektur wird der RESTdrift (~0) gemeldet, nicht der
    # Vor-Korrektur-Wert; ohne Korrektur der echte (kleine) Drift.
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    seen = []
    c.drift_updated.connect(lambda d: seen.append(d))
    c.play(_WIN, _SRC)
    fa._pos = 60000
    fv._mix = 60100          # 100 > 40 -> korrigiert
    c._on_tick()
    assert seen[-1] == 0
    fa._pos = 61000
    fv._mix = 61020          # 20 <= 40 -> keine Korrektur
    c._on_tick()
    assert seen[-1] == 20


def test_corrected_signal_counts_corrections():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    n = {"c": 0}
    c.corrected.connect(lambda: n.__setitem__("c", n["c"] + 1))
    c.play(_WIN, _SRC)
    fa._pos = 60000
    fv._mix = 60100
    c._on_tick()             # korrigiert
    fa._pos = 61000
    fv._mix = 61010
    c._on_tick()             # drift 10, keine Korrektur
    assert n["c"] == 1


def test_out_point_stops_both_and_finishes():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    done = {"n": 0}
    c.finished.connect(lambda: done.__setitem__("n", done["n"] + 1))
    c.play(_WIN, _SRC)
    fa._pos = 80000
    c._on_tick()
    assert "stop" in fa.calls
    assert any(isinstance(x, tuple) and x[0] == "stop_clip_at" for x in fv.calls)
    assert done["n"] == 1
    assert c.is_playing() is False


def test_stop_is_idempotent():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    c.stop()
    c.stop()
    assert c.is_playing() is False


def test_disabled_source_does_not_play():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, PlaybackAudioSource(disabled_reason="Keine Audioquelle."))
    assert "play" not in fa.calls
    assert c.is_playing() is False


def test_ready_timeout_aborts_controlled():
    fa, fv = FakeAudio(status="loading"), FakeVideo()
    c = _ctrl(fa, fv)
    errs = []
    c.error.connect(lambda m: errs.append(m))
    c.play(_WIN, _SRC)
    c._on_ready_timeout()
    assert errs and not c.is_playing()
    assert "play" not in fa.calls


_OPEN_SRC = PlaybackAudioSource(path="/a.wav", media_start_ms=50000,
                                media_end_ms=0, timeline_start_ms=50000,
                                timeline_end_ms=0)
_OPEN_WIN = PlaybackWindow("speak", 50000, None)   # offenes Ende (Free-Play)


def test_open_end_does_not_autostop_on_tick():
    # #76 (A): end_ms None -> kein Auto-Stop per Tick, auch weit hinter Start.
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    done = {"n": 0}
    c.finished.connect(lambda: done.__setitem__("n", done["n"] + 1))
    c.play(_OPEN_WIN, _OPEN_SRC)
    fa._pos = 999999
    c._on_tick()
    assert done["n"] == 0
    assert c.is_playing() is True


def test_end_of_media_finishes_open_end():
    # #76 (A): Free-Play endet sauber am Medienende.
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    done = {"n": 0}
    c.finished.connect(lambda: done.__setitem__("n", done["n"] + 1))
    c.play(_OPEN_WIN, _OPEN_SRC)
    fa.set_status("end")
    assert done["n"] == 1
    assert c.is_playing() is False


def test_cleanup_deletes_audio():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    c.cleanup()
    assert "deleteLater" in fa.calls
    assert c.is_playing() is False
