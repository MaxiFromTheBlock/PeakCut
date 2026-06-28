"""Marker-Auto-Erkennung Hybrid (Spec 2026-06-28, Carl-Gate).

Verstreute Fenster ueber die GANZE Datei (silence=Mittel, peak=max) + bounded Voll-Peak-Pass
NUR fuer stille-aber-impulslose Kandidaten -> spaerliche Fusspedal-Klicks (z.B. erst nach
120s) werden gefunden, ohne 188 SFX teuer zu scannen (kurze SFX sind nicht Episoden-Laenge
-> audio_silence_peak wird fuer sie gar nicht gerufen). Scanner bleibt Evidence, Confirm
bleibt Wahrheit, Pin-1/#71a unberuehrt.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import soundfile as sf

from core.material_scanner import (  # noqa: E402
    audio_silence_peak,
    scan_material,
    MARKER_SILENCE_THRESHOLD,
    MARKER_PEAK_THRESHOLD,
    EMPTY_PEAK_THRESHOLD,
)
from core.import_classifier import ROLE_MARKER  # noqa: E402

SR = 8000


def _wav(path, dur_s, impulse_at_s=None, continuous=False):
    n = int(dur_s * SR)
    if continuous:
        data = (np.sin(2 * np.pi * 200 * np.arange(n) / SR) * 0.3).astype("float32")
    else:
        data = np.zeros(n, dtype="float32")  # Stille
        if impulse_at_s is not None:
            i = int(impulse_at_s * SR)
            data[i:i + int(0.05 * SR)] = 0.8  # 50 ms lauter Klick
    sf.write(str(path), data, SR)
    return str(path)


def test_klick_nach_120s_wird_erkannt(tmp_path):
    # 200s still + EIN Klick bei 150s. Verstreute Fenster verfehlen ihn -> Voll-Pass faengt ihn.
    sig = audio_silence_peak(_wav(tmp_path / "marker.wav", 200, impulse_at_s=150))
    assert sig is not None
    silence, peak = sig
    assert silence >= MARKER_SILENCE_THRESHOLD   # sehr still
    assert peak >= MARKER_PEAK_THRESHOLD          # Impuls trotz 150s gefunden


def test_leerer_langer_kanal_bleibt_ignore(tmp_path):
    silence, peak = audio_silence_peak(_wav(tmp_path / "leer.wav", 200))  # nur Stille
    assert silence >= MARKER_SILENCE_THRESHOLD
    assert peak < EMPTY_PEAK_THRESHOLD            # auch nach Voll-Pass kein Impuls -> leer


def test_speech_mix_wird_nicht_marker(tmp_path):
    silence, _peak = audio_silence_peak(_wav(tmp_path / "speech.wav", 200, continuous=True))
    assert silence < MARKER_SILENCE_THRESHOLD     # kontinuierlich -> niedrige Stille -> kein Marker


def test_scan_schlaegt_marker_vor(tmp_path):
    # Integration: der Klick-nach-150s-Kanal wird als Marker vorgeschlagen (echtes
    # audio_silence_peak; Dauer injiziert, damit der Test kein ffprobe braucht).
    marker = _wav(tmp_path / "MIC4.wav", 200, impulse_at_s=150)
    mic = _wav(tmp_path / "MIC1.wav", 200, continuous=True)
    cands = scan_material([marker, mic], probe_duration=lambda p: 200_000)
    roles = {os.path.basename(c.path): c.suggested_role for c in cands}
    assert roles["MIC4.wav"] == ROLE_MARKER
    assert roles["MIC1.wav"] != ROLE_MARKER
