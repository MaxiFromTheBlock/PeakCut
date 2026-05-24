"""#71a Task 4 — session.play_current Mic-Mode via audio_routing-Helper.

Der Mic-Mode-Pfad in ``PeakCutSession.play_current()`` hatte
historisch dieselbe Mix-mit-Mics-Overlay-Logik wie der MP3Exporter
(Phasing-Wurzel). Quickfix vom 2026-05-21 hat nur den Export-Pfad
behoben; die Review-Wiedergabe im Speak-Mode hat das Phasing bis
zu diesem Task weiter.

Task 4: ``play_current`` Mic-Mode delegiert an
``audio_routing.get_speech_audio_segment`` — derselbe Helper wie
MP3Exporter, eine Wahrheit. Keyboard-Mode bleibt unverändert.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from pydub import AudioSegment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402


def _session_with_setup():
    """Minimale Session mit Mix in mic_tracks, audio bereits gestubt
    (keine ffmpeg-Loads im Test)."""
    p = PeakCutProject()
    p.set_files(
        "/x/KB.wav",
        ["/x/MIC1.wav", "/x/MIC2.wav", "/x/Sheila Mix.mp3"],
        [],
    )
    p.guest_name = "Test"
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
    s.current_peak = 0
    s.keyboard_audio = AudioSegment.silent(180_000)
    s.mic_audios = [AudioSegment.silent(180_000) for _ in p.mic_tracks]
    s.load_audio_lazy = lambda: None
    return s


def test_play_current_mic_mode_uses_get_speech_audio_segment():
    """Mic-Mode (jetzt: 'mic') delegiert die Audio-Wahl an den
    zentralen Helper, ruft play_audio mit dessen Rückgabe auf."""
    s = _session_with_setup()
    s.mode = "mic"

    called = []

    def fake_helper(session_arg, start_ms, end_ms):
        called.append((start_ms, end_ms))
        return AudioSegment.silent(1000)

    with patch(
        "core.session.get_speech_audio_segment", side_effect=fake_helper,
    ), patch("core.session.play_audio") as play_mock:
        s.play_current()

    assert len(called) == 1, (
        f"Mic-Mode rief get_speech_audio_segment {len(called)}× auf, "
        f"erwartet 1."
    )
    play_mock.assert_called_once()


def test_play_current_keyboard_mode_does_not_call_helper():
    """Pin: Keyboard-Mode-Pfad ist durch Task 4 NICHT betroffen.
    Helper darf gar nicht erst gerufen werden."""
    s = _session_with_setup()
    s.mode = "keyboard"

    with patch(
        "core.session.get_speech_audio_segment",
    ) as mock_helper, patch("core.session.play_audio"):
        s.play_current()

    mock_helper.assert_not_called()


def test_play_current_mic_mode_skips_when_helper_returns_none():
    """Pin: wenn Helper None liefert (Mismatch-Fall, Carl-P2-Linie),
    spielt play_current nichts ab — kein Crash mit AttributeError
    auf None."""
    s = _session_with_setup()
    s.mode = "mic"

    with patch(
        "core.session.get_speech_audio_segment", return_value=None,
    ), patch("core.session.play_audio") as play_mock:
        s.play_current()

    play_mock.assert_not_called()
