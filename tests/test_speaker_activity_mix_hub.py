"""AUD-1a — speaker_activity nutzt den zentralen Mix-Klassifizierer.

Insel A (Health-Check): _is_speaker_mic_candidate erkannte Mix per naivem
'mix in basename' — 'mixer_recording.wav' wurde fälschlich als Mix
ausgeschlossen. Jetzt über audio_routing.is_mix_track (token-bewusst).
#77 Task 6: keyboard/Marker laufen ebenfalls zentral über
import_classifier.is_marker_track (keine lokale Substring-Insel mehr);
guest_name nutzt import_classifier.is_mix_track. Nur _categorize_files
(main_window) bleibt als Import-Vorläufer Task-7-Scope.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.speaker_activity import (  # noqa: E402
    _is_speaker_mic_candidate, build_default_mic_assignments,
)


def test_mixer_recording_is_not_excluded_as_mix():
    # Der eigentliche Live-Bug: 'mixer' ist kein Mix-Token.
    assert _is_speaker_mic_candidate("/m/mixer_recording.wav") is True


def test_real_mix_files_excluded():
    assert _is_speaker_mic_candidate("/m/Sheila Mix.mp3") is False
    assert _is_speaker_mic_candidate("/m/Podcast_mixdown.wav") is False
    assert _is_speaker_mic_candidate("/m/MIXDOWN.wav") is False


def test_marker_island_unified_via_import_classifier():
    # #77 Task 6: keyboard/marker zentral & token-bewusst (kein Substring mehr).
    assert _is_speaker_mic_candidate("/m/Marker.wav") is False    # 'marker'-Token zählt jetzt
    assert _is_speaker_mic_candidate("/m/monkeys.wav") is True    # Substring 'keys' war ein Fehlausschluss


def test_plain_mic_is_candidate():
    assert _is_speaker_mic_candidate("/m/MIC1.wav") is True


def test_keyboard_marker_excluded_via_classifier():
    # #77 Task 6: jetzt zentral über import_classifier.is_marker_track (token).
    assert _is_speaker_mic_candidate("/m/MIC3_Keyboard.wav") is False
    assert _is_speaker_mic_candidate("/m/klavier.wav") is False
    assert _is_speaker_mic_candidate("/m/keys.wav") is False


def test_build_default_keeps_mixer_false_positive_drops_real_mix():
    a = build_default_mic_assignments(
        ["/m/Hotel - Gast Mix.mp3", "/m/mixer_recording.wav", "/m/MIC1.wav"])
    paths = [x.path for x in a]
    assert "/m/mixer_recording.wav" in paths    # echter Sprecher-Mic
    assert "/m/Hotel - Gast Mix.mp3" not in paths
