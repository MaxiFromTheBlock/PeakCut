"""#76 Task 5 — Qt Playback Controller (Carl-Plan 2026-06-15).

Gemeinsame Uhr: Audio = Master, Video folgt und wird bei Drift korrigiert.
Mit Fake-Playern getestet (kein echtes Medium). Readiness-Gate vor dem
gemeinsamen Start, harte stop()/cleanup(). Drift-Schwelle config-gesteuert.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_playback_controller import ReviewPlaybackController  # noqa: E402
from core.playback_windows import PlaybackWindow  # noqa: E402
from core.playback_audio_source import PlaybackAudioSource  # noqa: E402


class _Sig:
    def connect(self, *a):
        pass


class FakeAudio:
    mediaStatusChanged = _Sig()

    def __init__(self, status="loaded"):
        self.calls = []
        self._pos = 0
        self._status = status

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

    def deleteLater(self):
        self.calls.append("deleteLater")


class FakeVideo:
    def __init__(self, duration=100000):
        self.calls = []
        self._dur = duration
        self._mix = 0

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


def _ctrl(fa, fv, tol=40):
    return ReviewPlaybackController(
        fv, tolerance_ms=tol, audio_player_factory=lambda: fa,
        audio_ready_states={"loaded", "buffered"})


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
    assert ("setPos", 50000) in fa.calls  # Audio auf media_start


def test_audio_is_master_drift_corrects_video():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    fa._pos = 60000          # timeline 60000
    fv._mix = 60100          # drift 100 > 40
    c._on_tick()
    assert ("setpos", 60000) in fv.calls  # Video auf Audio-Timeline korrigiert


def test_small_drift_not_corrected():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    fa._pos = 60000
    fv._mix = 60030          # drift 30 <= 40
    fv.calls.clear()
    c._on_tick()
    assert _setpos_calls(fv) == []


def test_out_point_stops_both_and_finishes():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    done = {"n": 0}
    c.finished.connect(lambda: done.__setitem__("n", done["n"] + 1))
    c.play(_WIN, _SRC)
    fa._pos = 80000          # timeline 80000 >= window.end 80000
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
    c.stop()  # darf nicht krachen
    assert c.is_playing() is False


def test_not_ready_defers_then_begins():
    fa, fv = FakeAudio(status="loading"), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    assert "play" not in fa.calls  # noch nicht ready -> verschoben
    fa._status = "loaded"
    c._try_begin()
    assert "play" in fa.calls


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


def test_cleanup_deletes_audio():
    fa, fv = FakeAudio(), FakeVideo()
    c = _ctrl(fa, fv)
    c.play(_WIN, _SRC)
    c.cleanup()
    assert "deleteLater" in fa.calls
    assert c.is_playing() is False
