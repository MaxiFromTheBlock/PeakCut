"""HC-3 Task 0 — Fenster-Lesen in sync.py (Carl-Plan).

Roter Treiber: load_audio_as_array(max_seconds=) muss soundfile WIRKLICH
nur n Frames lesen lassen (frames=), statt voll zu lesen und danach zu
schneiden. Plus eine Invarianten-Sperre: das Fenster-Ergebnis muss
numerisch IDENTISCH zu "voll lesen, dann schneiden" sein.
"""

import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import core.sync as sync  # noqa: E402
from core.sync import load_audio_as_array  # noqa: E402


def _write_wav(path, seconds=3.0, sr=8000, stereo=True):
    n = int(sr * seconds)
    t = np.linspace(0, seconds, n, endpoint=False)
    left = np.sin(2 * np.pi * 220 * t)
    if stereo:
        right = np.sin(2 * np.pi * 330 * t) * 0.5
        data = np.stack([left, right], axis=1)
    else:
        data = left
    sf.write(str(path), data, sr, subtype="PCM_16")
    return sr, n


def test_load_audio_max_seconds_uses_soundfile_frames(tmp_path, monkeypatch):
    p = tmp_path / "a.wav"
    sr, _ = _write_wav(p, seconds=3.0, sr=8000)

    calls = []
    orig = sync.sf.read

    def spy(file, *a, **k):
        calls.append(k)
        return orig(file, *a, **k)

    monkeypatch.setattr(sync.sf, "read", spy)
    load_audio_as_array(str(p), max_seconds=1.25)

    assert calls, "sf.read wurde nicht aufgerufen"
    assert any(c.get("frames") == int(sr * 1.25) for c in calls), (
        f"sf.read muss mit frames={int(sr*1.25)} gelesen werden "
        f"(nicht voll lesen + schneiden); calls={calls}")


def test_windowed_read_matches_legacy_full_then_slice_exactly(tmp_path):
    p = tmp_path / "b.wav"
    sr, _ = _write_wav(p, seconds=3.0, sr=8000, stereo=True)

    full, sr_full = load_audio_as_array(str(p))
    n = int(sr_full * 1.5)
    legacy = full[:n]

    window, sr_win = load_audio_as_array(str(p), max_seconds=1.5)

    assert sr_win == sr_full
    assert np.array_equal(window, legacy), (
        "Fenster-Read muss numerisch identisch zu voll-lesen+schneiden sein")


import shutil
from core.sync import sync_videos, format_offset, calculate_offset


def _spy_loader(monkeypatch):
    """Zeichnet (basename, max_seconds) je load_audio_as_array-Call auf."""
    calls = []
    orig = sync.load_audio_as_array

    def spy(path, max_seconds=None):
        calls.append((os.path.basename(path), max_seconds))
        return orig(path, max_seconds=max_seconds)

    monkeypatch.setattr(sync, "load_audio_as_array", spy)
    return calls


def test_sync_fast_path_loads_windows_only(tmp_path, monkeypatch):
    ref = tmp_path / "ref.wav"
    _write_wav(ref, seconds=3.0, sr=8000, stereo=False)
    monkeypatch.setattr(sync, "_SYNC_WINDOW_S", 1.0)
    monkeypatch.setattr(sync, "extract_audio_from_video",
                        lambda v, out, target_sr=None: shutil.copy(str(ref), out))
    monkeypatch.setattr(sync, "calculate_offset", lambda a, b: (0, 0.9))
    calls = _spy_loader(monkeypatch)

    sync_videos(["/fake/cam.mp4"], str(ref), str(tmp_path / "t"), fps=25)

    assert calls, calls
    assert all(ms == 1.0 for _, ms in calls), f"nur Fenster erwartet: {calls}"
    assert not any(ms is None for _, ms in calls), f"kein Full-Read: {calls}"


def test_sync_fallback_full_only_after_weak_window(tmp_path, monkeypatch):
    ref = tmp_path / "ref.wav"
    _write_wav(ref, seconds=3.0, sr=8000, stereo=False)
    monkeypatch.setattr(sync, "_SYNC_WINDOW_S", 1.0)
    monkeypatch.setattr(sync, "extract_audio_from_video",
                        lambda v, out, target_sr=None: shutil.copy(str(ref), out))
    seq = iter([(0, 0.0), (0, 0.9)])  # erst schwach -> Fallback, dann stark
    monkeypatch.setattr(sync, "calculate_offset", lambda a, b: next(seq))
    calls = _spy_loader(monkeypatch)

    sync_videos(["/fake/cam.mp4"], str(ref), str(tmp_path / "t"), fps=25)

    window_calls = [c for c in calls if c[1] == 1.0]
    full_calls = [c for c in calls if c[1] is None]
    assert window_calls, f"Fenster-Reads fehlen: {calls}"
    assert full_calls, f"Fallback muss voll lesen: {calls}"
    # voll erst NACH den Fenster-Reads
    assert calls.index(full_calls[0]) > calls.index(window_calls[0])


def test_sync_fallback_offset_matches_legacy_full(tmp_path, monkeypatch):
    sr = 8000
    monkeypatch.setattr(sync, "_SYNC_WINDOW_S", 1.0)
    # Fenster (1s) = Stille -> schwach; Signal erst danach -> Fallback greift
    silence = np.zeros(sr)
    rng = np.random.default_rng(42)
    pulse = rng.standard_normal(sr * 3)
    ref_sig = np.concatenate([silence, pulse]).astype(np.float32)
    shift = 1234
    tgt_sig = np.concatenate([np.zeros(shift), ref_sig]).astype(np.float32)
    ref = tmp_path / "ref.wav"
    tgt = tmp_path / "tgt.wav"
    sf.write(str(ref), ref_sig, sr, subtype="PCM_16")
    sf.write(str(tgt), tgt_sig, sr, subtype="PCM_16")
    monkeypatch.setattr(sync, "extract_audio_from_video",
                        lambda v, out, target_sr=None: shutil.copy(str(tgt), out))

    res = sync_videos(["/fake/cam.mp4"], str(ref), str(tmp_path / "t"), fps=25)

    # Legacy-Weg: volle Referenz + volles Target direkt korrelieren
    rf, _ = sync.load_audio_as_array(str(ref))
    tf, _ = sync.load_audio_as_array(str(tgt))
    off, _ = calculate_offset(rf, tf)
    legacy_tc = format_offset(off / sr, 25)
    assert res == [("cam.mp4", legacy_tc)], (res, legacy_tc)


def test_reference_full_loaded_once_for_multiple_fallbacks(tmp_path, monkeypatch):
    ref = tmp_path / "ref.wav"
    _write_wav(ref, seconds=2.0, sr=8000, stereo=False)
    monkeypatch.setattr(sync, "_SYNC_WINDOW_S", 0.5)
    monkeypatch.setattr(sync, "extract_audio_from_video",
                        lambda v, out, target_sr=None: shutil.copy(str(ref), out))
    monkeypatch.setattr(sync, "calculate_offset", lambda a, b: (0, 0.0))  # immer Fallback
    calls = _spy_loader(monkeypatch)

    sync_videos(["/fake/c1.mp4", "/fake/c2.mp4"], str(ref),
                str(tmp_path / "t"), fps=25)

    ref_full = [c for c in calls if c[0] == "ref.wav" and c[1] is None]
    assert len(ref_full) == 1, f"volle Referenz nur EINMAL: {calls}"
