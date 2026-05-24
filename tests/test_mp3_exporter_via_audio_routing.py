"""#71a Task 3 — MP3Exporter delegiert an audio_routing-Helper.

Geschichte: Der Quickfix vom 2026-05-21 (eigene Mix-Index-Berechnung
inline in MP3Exporter) wird hier durch den sauberen Helper-Pfad
ersetzt. ``MP3Exporter.export()`` ruft pro aktivem Peak
``audio_routing.get_speech_audio_segment(session, start, end)`` auf
— die Mix-Wahl-Logik lebt jetzt zentral im Helper.

Verhaltens-Pins (überleben den Refactor):
- Mix in ``mic_tracks`` → 0 overlay-Aufrufe (Phasing weg).
- Kein Mix in ``mic_tracks`` → 1 overlay-Aufruf (MIC2 auf MIC1,
  Backward-Compat).
- ``MP3Exporter`` ruft den Helper exakt einmal pro aktivem Peak
  (Carl P2-Lock 2026-05-21: kein Schleifen-Drift, kein Skip).

Pin-1-Schutz: ``XMLExporter`` wird *nicht* berührt, der Pin-Hash in
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


# --- #71a Task 3: MP3Exporter delegiert an Helper (Carl P2-Lock) -----


def test_mp3_exporter_calls_get_speech_audio_segment_per_active_peak(tmp_path):
    """Carl-P2-Lock (Plan-Cross-Review 2026-05-21): MP3Exporter
    delegiert die Audio-Wahl an audio_routing.get_speech_audio_segment
    und ruft den Helper EXAKT EINMAL pro aktivem Peak — nicht nur
    ‚mindestens einmal'. Fängt versehentliche Doppel-Schleifen oder
    Skip-Bugs auf."""
    s = _session_with_files(tmp_path / "exact_count", with_mix=True)
    # Setup mit drei Peaks, einer davon ignored → zwei aktive
    s.load_analysis_results(
        {
            "peaks": [
                {"index": 0, "position_ms": 60_000,
                 "context_ms": 15_000, "ignored": False},
                {"index": 1, "position_ms": 90_000,
                 "context_ms": 15_000, "ignored": True},
                {"index": 2, "position_ms": 120_000,
                 "context_ms": 15_000, "ignored": False},
            ],
            "video_offsets": [],
        }
    )
    # Re-stub audio nach load_analysis_results (resetet alles)
    s.keyboard_audio = _silent_segment()
    s.mic_audios = [_silent_segment() for _ in s.project.mic_tracks]
    s.load_audio_lazy = lambda: None

    active = s.get_active_peaks()
    assert len(active) == 2, "Test-Setup: 2 aktive Peaks erwartet"

    mock_seg = _silent_segment(1000)
    with patch(
        "core.exporters.get_speech_audio_segment",
        return_value=mock_seg,
    ) as mock_helper:
        MP3Exporter().export(s)

    assert mock_helper.call_count == len(active), (
        f"MP3Exporter ruft get_speech_audio_segment "
        f"{mock_helper.call_count}× auf, erwartet "
        f"{len(active)} (= active peaks). Schleife driftet oder "
        f"Quickfix-Code noch nicht ersetzt."
    )


def test_mp3_exporter_skips_peak_when_helper_returns_none(tmp_path):
    """Pin: wenn get_speech_audio_segment None liefert
    (mic_tracks/mic_audios-Mismatch laut Carl-P2-Linie), überspringt
    MP3Exporter diesen Peak still — kein Crash, keine kaputten
    Segments im Export."""
    s = _session_with_files(tmp_path / "helper_none", with_mix=True)
    with patch(
        "core.exporters.get_speech_audio_segment",
        return_value=None,
    ):
        # Export läuft durch ohne Exception, MP3 ist (fast) leer.
        result = MP3Exporter().export(s)
    # Result kann leerer String oder Pfad zu winziger MP3 sein —
    # Hauptsache kein Crash.
    assert result == "" or result.endswith(".mp3")
