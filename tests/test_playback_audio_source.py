"""#76 Task 3 — Audio Source Resolver (Carl-Plan 2026-06-15).

Liefert eine einheitliche, dateibasierte (QMediaPlayer-taugliche) Hörquelle
je Fenster: Key=Keyboard-Datei, Speak/Smart=Mix-Datei; ohne Mix Fallback
über get_speech_audio_segment als temporär gerenderte WAV. Keine neue
Mix-Heuristik (nur audio_routing).
"""

import os
import sys

import pytest
from pydub import AudioSegment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.playback_audio_source import (  # noqa: E402
    PlaybackAudioSource, resolve_playback_audio_source,
)
from core.playback_windows import PlaybackWindow  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core import audio_routing  # noqa: E402


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def _session(tmp, with_mix=True):
    proj = PeakCutProject()
    kb = _touch(tmp / "ep" / "keyboard.wav")
    mics = [_touch(tmp / "ep" / "MIC1.wav")]
    if with_mix:
        mics.append(_touch(tmp / "ep" / "Folge - Mix.wav"))
    proj.set_files(kb, mics, [_touch(tmp / "ep" / "cam.mp4")])
    s = PeakCutSession(proj, {"preview_duration_ms": 1000})
    s.keyboard_audio = AudioSegment.silent(1000)  # load_audio_lazy überspringen
    return s


def test_key_uses_keyboard_file_timeline_equals_media(tmp_path):
    s = _session(tmp_path)
    src = resolve_playback_audio_source(s, PlaybackWindow("key", 60000, 61000))
    assert src.path == s.project.keyboard_track
    assert src.media_start_ms == 60000 and src.media_end_ms == 61000
    assert src.timeline_start_ms == 60000 and src.timeline_end_ms == 61000
    assert not src.disabled


def test_speak_uses_mix_file(tmp_path):
    s = _session(tmp_path, with_mix=True)
    src = resolve_playback_audio_source(s, PlaybackWindow("speak", 50000, 80000))
    assert src.path == audio_routing.get_mix_track(s.project)
    assert src.media_start_ms == 50000 and src.timeline_start_ms == 50000


def test_smart_uses_mix_file(tmp_path):
    s = _session(tmp_path, with_mix=True)
    src = resolve_playback_audio_source(s, PlaybackWindow("smart", 40000, 90000))
    assert src.path == audio_routing.get_mix_track(s.project)


def test_no_mix_renders_temp_wav(tmp_path, monkeypatch):
    s = _session(tmp_path, with_mix=False)
    monkeypatch.setattr("core.audio_routing.get_speech_audio_segment",
                        lambda session, a, b: AudioSegment.silent(b - a))
    src = resolve_playback_audio_source(s, PlaybackWindow("speak", 50000, 51000))
    assert os.path.isfile(src.path) and src.path.endswith(".wav")
    assert src.media_start_ms == 0 and src.media_end_ms == 1000
    assert src.timeline_start_ms == 50000 and src.timeline_end_ms == 51000
    assert not src.disabled


def test_no_mix_and_no_segment_is_disabled(tmp_path, monkeypatch):
    s = _session(tmp_path, with_mix=False)
    monkeypatch.setattr("core.audio_routing.get_speech_audio_segment",
                        lambda session, a, b: None)
    src = resolve_playback_audio_source(s, PlaybackWindow("speak", 50000, 51000))
    assert src.disabled and src.disabled_reason


def test_key_without_keyboard_file_disabled(tmp_path):
    s = _session(tmp_path)
    s.project.keyboard_track = ""
    src = resolve_playback_audio_source(s, PlaybackWindow("key", 60000, 61000))
    assert src.disabled


def test_disabled_window_yields_disabled_source(tmp_path):
    s = _session(tmp_path)
    w = PlaybackWindow("smart", 0, 0, "Kein Sinnabschnitt für diesen Drücker.")
    src = resolve_playback_audio_source(s, w)
    assert src.disabled


def test_render_is_cached(tmp_path, monkeypatch):
    s = _session(tmp_path, with_mix=False)
    calls = {"n": 0}

    def fake(session, a, b):
        calls["n"] += 1
        return AudioSegment.silent(b - a)

    monkeypatch.setattr("core.audio_routing.get_speech_audio_segment", fake)
    w = PlaybackWindow("speak", 50000, 51000)
    src1 = resolve_playback_audio_source(s, w)
    src2 = resolve_playback_audio_source(s, w)
    assert src1.path == src2.path
    assert calls["n"] == 1  # zweiter Aufruf nutzt die gecachte WAV


def test_cache_key_changes_when_mic_set_changes(tmp_path, monkeypatch):
    # P2 (Carl 2026-06-15): andere Mic-Auswahl, gleiches Keyboard+Fenster
    # -> anderer Preview-Pfad (sonst stale Audio).
    s = _session(tmp_path, with_mix=False)
    monkeypatch.setattr("core.audio_routing.get_speech_audio_segment",
                        lambda session, a, b: AudioSegment.silent(b - a))
    w = PlaybackWindow("speak", 50000, 51000)
    p1 = resolve_playback_audio_source(s, w).path
    mic2 = _touch(tmp_path / "ep" / "MIC2.wav")
    s.project.set_files(s.project.keyboard_track, [mic2], list(s.project.videos))
    p2 = resolve_playback_audio_source(s, w).path
    assert p1 != p2


def test_cache_key_changes_when_mic_content_changes(tmp_path, monkeypatch):
    # Geänderter Mic-Inhalt (size/mtime) -> anderer Key -> Neu-Render.
    s = _session(tmp_path, with_mix=False)
    monkeypatch.setattr("core.audio_routing.get_speech_audio_segment",
                        lambda session, a, b: AudioSegment.silent(b - a))
    w = PlaybackWindow("speak", 50000, 51000)
    p1 = resolve_playback_audio_source(s, w).path
    with open(s.project.mic_tracks[0], "wb") as f:
        f.write(b"xxxxxxxxxxxxxxxx")  # Größe geändert
    p2 = resolve_playback_audio_source(s, w).path
    assert p1 != p2
