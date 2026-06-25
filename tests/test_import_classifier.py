"""#77 Task 1 - import classifier contracts.

The classifier is the new central truth for the import dialog's file-role
suggestions. It is intentionally pure core code: no Qt, no project/archive
side effects.
"""

from __future__ import annotations

import os
import sys
from dataclasses import FrozenInstanceError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.import_classifier import (  # noqa: E402
    ROLE_CAMERA,
    ROLE_IGNORE,
    ROLE_MARKER,
    ROLE_MIC,
    ROLE_MIX,
    ROLE_TRANSCRIPT,
    ImportCandidate,
    ImportSlots,
    is_audio_path,
    is_marker_track,
    is_mix_track,
    is_transcript_path,
    is_video_path,
    normalize_import_slots,
    suggest_import_slots,
    suggest_role,
    validate_import_slots,
)


def test_role_contracts_are_plain_strings():
    assert ROLE_MARKER == "marker"
    assert ROLE_MIC == "mic"
    assert ROLE_MIX == "mix"
    assert ROLE_TRANSCRIPT == "transcript"
    assert ROLE_CAMERA == "camera"
    assert ROLE_IGNORE == "ignore"


def test_import_candidate_is_frozen_and_validates_role():
    c = ImportCandidate("/m/MIC1.wav", ROLE_MIC, "audio")
    assert c.path == "/m/MIC1.wav"
    assert c.suggested_role == ROLE_MIC
    with pytest.raises(FrozenInstanceError):
        c.suggested_role = ROLE_MIX
    with pytest.raises(ValueError):
        ImportCandidate("/m/x.wav", "bogus")


def test_import_slots_are_frozen_and_tuple_backed():
    slots = ImportSlots(
        marker_track="/m/Marker.wav",
        mic_tracks=["/m/MIC1.wav", "/m/MIC2.wav"],
        mix_track="/m/Mix.mp3",
        transcript_path="/m/Transcript.docx",
        videos=["/m/CAM1.mov"],
        ignored=["/m/readme.txt"],
    )
    assert slots.mic_tracks == ("/m/MIC1.wav", "/m/MIC2.wav")
    assert slots.videos == ("/m/CAM1.mov",)
    assert slots.ignored == ("/m/readme.txt",)
    with pytest.raises(FrozenInstanceError):
        slots.mix_track = None


@pytest.mark.parametrize(
    "path",
    [
        "Sheila Mix.mp3",
        "Hotel Matze - Sheila de Liz Mix.mp3",
        "Episode - Mix.mp3",
        "Podcast_mixdown.wav",
        "/Users/max/material/HM_2026-05_Mix.wav",
        "episode.42.mix.mp3",
        "episode(mix).mp3",
    ],
)
def test_is_mix_track_matches_hm_and_tokenized_names(path):
    assert is_mix_track(path)


@pytest.mark.parametrize(
    "path",
    ["MIC1.wav", "mixer_recording.wav", "mixedfeelings.wav", "", None],
)
def test_is_mix_track_rejects_false_positives(path):
    assert not is_mix_track(path)


# B1 (Carl): Recorder-Mixdown-Praefix p\d+mix / p\d+mixdown erkennen — die HM-Studio-
# Konvention "P8Mix" (ein Token) rutschte sonst als Mic durch -> Phasing-Wurzel (#71a).
@pytest.mark.parametrize(
    "path",
    [
        "_20260624_HotelMatze_JohannaKlug_P8Mix_2026_0623_1009.WAV",
        "P8Mix.wav",
        "P8Mixdown.wav",
        "P4Mix.mp3",
        "recording_p16mix.wav",
    ],
)
def test_is_mix_track_matches_recorder_device_prefix(path):
    assert is_mix_track(path)


@pytest.mark.parametrize(
    "path",
    ["remix.wav", "Summer_Remix_V1.wav", "p8mixer.wav", "pmix.wav", "8mix.wav"],
)
def test_is_mix_track_device_prefix_no_false_positives(path):
    # ENG: braucht p + Ziffer(n) + "mix"/"mixdown" als ganzes Token. remix/mixer/pmix/8mix raus.
    assert not is_mix_track(path)


@pytest.mark.parametrize(
    "path",
    [
        "keyboard.wav",
        "Keys.wav",
        "Klavier.wav",
        "Marker.wav",
        "/m/show-keyboard-take.mp3",
    ],
)
def test_is_marker_track_matches_allowed_marker_tokens(path):
    assert is_marker_track(path)


@pytest.mark.parametrize(
    "path",
    ["Key Largo.wav", "monkey.wav", "keynote.mov", "key.wav", "", None],
)
def test_is_marker_track_rejects_key_false_positives(path):
    assert not is_marker_track(path)


def test_extension_helpers_are_case_insensitive():
    assert is_audio_path("MIC1.WAV")
    assert is_audio_path("Mix.mp3")
    assert not is_audio_path("Transcript.docx")
    assert is_video_path("CAM.MOV")
    assert is_video_path("CAM.mp4")
    assert not is_video_path("MIC1.wav")
    assert is_transcript_path("Transcript.DOCX")
    assert not is_transcript_path("Transcript.txt")


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("keyboard.wav", ROLE_MARKER),
        ("MIC1.wav", ROLE_MIC),
        ("Sheila Mix.mp3", ROLE_MIX),
        ("Transcript.docx", ROLE_TRANSCRIPT),
        ("CAM_A.mov", ROLE_CAMERA),
        ("notes.pdf", ROLE_IGNORE),
        ("keynote.mov", ROLE_CAMERA),
        ("Key Largo.wav", ROLE_MIC),
    ],
)
def test_suggest_role(path, role):
    assert suggest_role(path) == role


def test_suggest_import_slots_builds_complete_state_in_input_order():
    slots = suggest_import_slots([
        "/m/keyboard.wav",
        "/m/MIC2.wav",
        "/m/Sheila Mix.mp3",
        "/m/MIC1.wav",
        "/m/Transcript.docx",
        "/m/CAM_B.mp4",
        "/m/CAM_A.mov",
        "/m/readme.pdf",
    ])
    assert slots == ImportSlots(
        marker_track="/m/keyboard.wav",
        mic_tracks=("/m/MIC2.wav", "/m/MIC1.wav"),
        mix_track="/m/Sheila Mix.mp3",
        transcript_path="/m/Transcript.docx",
        videos=("/m/CAM_B.mp4", "/m/CAM_A.mov"),
        ignored=("/m/readme.pdf",),
    )


def test_suggest_import_slots_first_marker_and_mix_win_rest_ignored():
    slots = suggest_import_slots([
        "/m/Marker.wav",
        "/m/Keyboard.wav",
        "/m/A Mix.mp3",
        "/m/B Mix.mp3",
        "/m/MIC1.wav",
    ])
    assert slots.marker_track == "/m/Marker.wav"
    assert slots.mix_track == "/m/A Mix.mp3"
    assert slots.mic_tracks == ("/m/MIC1.wav",)
    assert slots.ignored == ("/m/Keyboard.wav", "/m/B Mix.mp3")


def test_normalize_import_slots_is_deterministic_and_nonfatal():
    slots = ImportSlots(
        marker_track="/m/Marker.wav",
        mic_tracks=("/m/MIC1.wav",),
        mix_track="/m/A Mix.mp3",
        transcript_path="/m/Transcript.docx",
        videos=("/m/CAM.mov",),
        ignored=("/m/old.txt",),
    )
    assert normalize_import_slots(slots) == slots

    messy = ImportSlots(
        marker_track="/m/Marker.wav",
        mic_tracks=("/m/MIC1.wav", "/m/A Mix.mp3", "/m/Keyboard.wav"),
        mix_track="/m/B Mix.mp3",
        transcript_path="/m/Transcript.docx",
        videos=["/m/CAM.mov"],
        ignored=["/m/old.txt"],
    )
    normalized = normalize_import_slots(messy)
    assert normalized.marker_track == "/m/Marker.wav"
    assert normalized.mic_tracks == ("/m/MIC1.wav",)
    assert normalized.mix_track == "/m/B Mix.mp3"
    assert normalized.videos == ("/m/CAM.mov",)
    assert normalized.ignored == (
        "/m/old.txt",
        "/m/A Mix.mp3",
        "/m/Keyboard.wav",
    )


def test_validate_import_slots_requires_marker_and_speech_source():
    assert validate_import_slots(ImportSlots()) == [
        "Marker-Spur fehlt.",
        "Keine Sprachquelle: mindestens ein Mic oder Mix erforderlich.",
    ]
    assert validate_import_slots(ImportSlots(
        marker_track="/m/Marker.wav",
        mix_track="/m/Mix.mp3",
    )) == []
    assert validate_import_slots(ImportSlots(
        marker_track="/m/Marker.wav",
        mic_tracks=("/m/MIC1.wav",),
    )) == []


def test_validate_import_slots_reports_conflicting_raw_slots():
    slots = ImportSlots(
        marker_track="/m/Marker.wav",
        mic_tracks=("/m/MIC1.wav", "/m/Other Mix.mp3", "/m/Keys.wav"),
        mix_track="/m/Mix.mp3",
    )
    messages = validate_import_slots(slots)
    assert "Mehrere Mix-Spuren erkannt." in messages
    assert "Mehrere Marker-Spuren erkannt." in messages


def test_validate_import_slots_counts_conflicts_in_ignored_bucket():
    slots = suggest_import_slots([
        "/m/Marker.wav",
        "/m/Keyboard.wav",
        "/m/A Mix.mp3",
        "/m/B Mix.mp3",
        "/m/MIC1.wav",
    ])
    assert slots.ignored == ("/m/Keyboard.wav", "/m/B Mix.mp3")
    messages = validate_import_slots(slots)
    assert "Mehrere Mix-Spuren erkannt." in messages
    assert "Mehrere Marker-Spuren erkannt." in messages
