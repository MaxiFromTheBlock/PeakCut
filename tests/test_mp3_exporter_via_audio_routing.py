"""Quickfix 2026-05-21 — MP3Exporter darf nicht Mix + Einzel-Mics
overlay-summieren, weil dadurch Phasing entsteht (Mix enthält die
Mic-Signale schon).

Hintergrund: Beim Cross-Review der #71a-Spec wurde 2026-05-21
verifiziert, dass die Mix-Datei beim Import in ``project.mic_tracks``
einsortiert wird (``main_window._categorize_files`` 232–237) und
damit ``session.mic_audios`` enthält. MP3Exporter (``exporters.py``
142–144) und ``session.play_current()`` Mic-Mode overlay-summieren
``mic_audios[0]`` + ``mic_audios[1:]``, also Mix on-top zu allen
Einzel-Mics → jeder Sprecher zweimal addiert → Phasing.

Dieser Quickfix zieht den Mix als alleinige Sprach-Quelle vor das
Overlay, wenn er vorhanden ist. Der saubere audio_routing.py-Helper
folgt mit #71a Task 1 (Carl-Plan).

Pin-1-Schutz: XMLExporter wird *nicht* berührt, der Pin-Hash in
``tests/test_audio_routing_safety.py`` darf nicht driften.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from pydub import AudioSegment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import MP3Exporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402


def _silent_segment(duration_ms: int = 180_000) -> AudioSegment:
    """Reproduzierbarer Stille-AudioSegment für die Tests. Wir
    interessieren uns nicht für den Inhalt, sondern dafür, OB
    overlay aufgerufen wird."""
    return AudioSegment.silent(duration=duration_ms)


def _session_with_files(tmp_path, with_mix: bool):
    """Setup einer minimalen Session mit/ohne Mix-Datei in der
    mic_tracks-Liste — exakt wie main_window._categorize_files
    sortiert (Mix wird als Mic einsortiert)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    files = ["KB.wav", "MIC1.wav", "MIC2.wav"]
    if with_mix:
        files.append("Sheila Mix.mp3")
    files.append("CAM.mp4")
    for n in files:
        (tmp_path / n).write_bytes(b"\x00")

    p = PeakCutProject()
    mics = [str(tmp_path / "MIC1.wav"), str(tmp_path / "MIC2.wav")]
    if with_mix:
        mics.append(str(tmp_path / "Sheila Mix.mp3"))
    p.set_files(
        str(tmp_path / "KB.wav"),
        mics,
        [str(tmp_path / "CAM.mp4")],
    )
    p.guest_name = "Sheila"
    p.export_dir = str(tmp_path / "exp")

    s = PeakCutSession(p, {"fps": 25, "context_duration_ms": 15000})
    s.load_analysis_results(
        {
            "peaks": [
                {"index": 0, "position_ms": 60_000,
                 "context_ms": 15_000, "ignored": False},
            ],
            "video_offsets": [],
        }
    )
    # Audio direkt einsetzen, ohne ffmpeg-Loading-Pfad anzustoßen.
    s.keyboard_audio = _silent_segment()
    s.mic_audios = [_silent_segment() for _ in mics]
    s.load_audio_lazy = lambda: None  # No-Op, bleibt bei unseren Stubs
    return s


def _count_overlay_calls(action):
    """Patcht AudioSegment.overlay und zählt seine Aufrufe während
    ``action()`` läuft. Originale Implementierung bleibt intakt
    (delegiert), damit der Export weiter funktioniert."""
    original = AudioSegment.overlay
    calls = []

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    with patch.object(AudioSegment, "overlay", counting):
        action()
    return len(calls)


def test_mp3_exporter_does_not_overlay_when_mix_in_mic_tracks(tmp_path):
    """Quickfix-Pin: wenn die Mix-Datei in ``mic_tracks`` ist
    (heutiges _categorize_files-Verhalten), darf MP3Exporter sie
    *nicht* mit den Einzel-Mics overlay-summieren. Statt dessen
    soll nur der Mix als Sprach-Quelle dienen.

    Pre-Fix: dieser Test ist ROT (alter Code overlay-summiert
    immer alle mic_audios).
    Post-Fix: dieser Test ist GRÜN (Mix wird vorgezogen).
    """
    s = _session_with_files(tmp_path / "with_mix", with_mix=True)
    count = _count_overlay_calls(lambda: MP3Exporter().export(s))
    assert count == 0, (
        f"MP3Exporter macht weiterhin Overlay-Summierung obwohl "
        f"Mix in mic_tracks vorhanden ist ({count} overlay-Aufrufe). "
        f"Phasing-Bug (Mix + Einzel-Mics) ist nicht behoben."
    )


def test_mp3_exporter_still_overlays_when_no_mix_in_mic_tracks(tmp_path):
    """Pin: Backward-Compat. Wenn KEIN Mix in mic_tracks ist
    (Produktion ohne Mix-Datei), soll altes Overlay-Verhalten
    bleiben — MIC2 wird auf MIC1 overlay-summiert. Das ist heute
    noch der einzige Weg ohne Mix; Auto-Mix-Generierung kommt mit
    späterem Roadmap-Punkt.

    Erwartung: bei zwei Mics und einem Peak genau 1 overlay-Aufruf.
    """
    s = _session_with_files(tmp_path / "no_mix", with_mix=False)
    count = _count_overlay_calls(lambda: MP3Exporter().export(s))
    assert count == 1, (
        f"Ohne Mix sollte MP3Exporter MIC2 auf MIC1 overlayen — "
        f"erwartet 1 overlay-Aufruf, tatsächlich {count}. "
        f"Backward-Compat gebrochen."
    )
