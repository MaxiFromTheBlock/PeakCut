"""#77 Task 2 - PeakCutProject structural import slots."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydub import AudioSegment  # noqa: E402

from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402


def test_keyboard_track_aliases_marker_track_both_directions():
    project = PeakCutProject()
    project.marker_track = "/m/Marker.wav"
    assert project.keyboard_track == "/m/Marker.wav"

    project.keyboard_track = "/m/Keyboard.wav"
    assert project.marker_track == "/m/Keyboard.wav"


def test_set_files_accepts_structural_mix_and_transcript_slots():
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav", "/m/MIC2.wav"],
        videos=["/m/CAM1.mov"],
        mix="/m/Sheila Mix.mp3",
        transcript="/m/Transcript.docx",
    )

    assert project.marker_track == "/m/Marker.wav"
    assert project.keyboard_track == "/m/Marker.wav"
    assert project.mic_tracks == ["/m/MIC1.wav", "/m/MIC2.wav"]
    assert project.mix_track == "/m/Sheila Mix.mp3"
    assert project.transcript_path == "/m/Transcript.docx"
    assert project.videos == ["/m/CAM1.mov"]


def test_set_files_legacy_mics_exposes_mix_track_before_schema_migration():
    """Task 2 prepares the structural slot but does not yet rewrite legacy
    payloads. Task 5 completes the split after exporters read the new
    audio-source model."""
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav", "/m/Sheila Mix.mp3", "/m/MIC2.wav"],
        videos=[],
    )

    assert project.mix_track == "/m/Sheila Mix.mp3"
    assert project.mic_tracks == [
        "/m/MIC1.wav",
        "/m/Sheila Mix.mp3",
        "/m/MIC2.wav",
    ]


def test_get_all_file_paths_includes_each_slot_once():
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav", "/m/Sheila Mix.mp3"],
        videos=["/m/CAM1.mov"],
        mix="/m/Sheila Mix.mp3",
        transcript="/m/Transcript.docx",
    )

    assert project.get_all_file_paths() == [
        "/m/MIC1.wav",
        "/m/Sheila Mix.mp3",
        "/m/CAM1.mov",
        "/m/Marker.wav",
        "/m/Transcript.docx",
    ]


def test_get_reference_track_prefers_structural_mix_over_legacy_mic_scan():
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/Old Mix.mp3", "/m/MIC1.wav"],
        videos=[],
        mix="/m/New Mix.mp3",
    )

    assert project.get_reference_track() == "/m/New Mix.mp3"


def test_get_reference_track_legacy_fallback_still_works():
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav", "/m/Legacy Mix.mp3"],
        videos=[],
    )

    assert project.get_reference_track() == "/m/Legacy Mix.mp3"


def test_guest_name_cache_resets_when_files_change():
    project = PeakCutProject()
    project.guest_name = "Old"
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav"],
        videos=[],
        mix="/m/Hotel Matze - Sheila de Liz Mix.mp3",
    )

    assert project.guest_name == "Sheila de Liz"


def test_session_load_audio_lazy_loads_structural_mix_without_shifting_mics(monkeypatch):
    """#77 Task 3: load_audio_lazy bekommt ein eigenes mix_audio-Feld,
    hält mic_audios im Gate-B-Zwischenzustand aber 1:1 aligned zu
    project.mic_tracks."""
    project = PeakCutProject()
    project.set_files(
        keyboard="/m/Marker.wav",
        mics=["/m/MIC1.wav", "/m/Sheila Mix.mp3", "/m/MIC2.wav"],
        videos=[],
        mix="/m/Sheila Mix.mp3",
    )
    session = PeakCutSession(project, {})

    audio_by_path = {
        "/m/Marker.wav": AudioSegment.silent(3000),
        "/m/MIC1.wav": AudioSegment.silent(3000) + 1,
        "/m/Sheila Mix.mp3": AudioSegment.silent(3000) + 2,
        "/m/MIC2.wav": AudioSegment.silent(3000) + 3,
    }

    calls = []

    def fake_from_file(path):
        calls.append(path)
        return audio_by_path[path]

    monkeypatch.setattr(AudioSegment, "from_file", fake_from_file)

    session.load_audio_lazy()

    assert session.marker_audio is audio_by_path["/m/Marker.wav"]
    assert session.mix_audio is audio_by_path["/m/Sheila Mix.mp3"]
    assert session.mic_audios == [
        audio_by_path["/m/MIC1.wav"],
        audio_by_path["/m/Sheila Mix.mp3"],
        audio_by_path["/m/MIC2.wav"],
    ]
    assert calls.count("/m/Sheila Mix.mp3") == 1
