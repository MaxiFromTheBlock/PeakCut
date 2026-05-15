import csv

import numpy as np
import soundfile as sf

from core.folgenschnitt_models import MicAssignment, SpeakerId
from core.speaker_activity import (
    SPEAKER_ACTIVITY_DEFAULTS,
    analyze_speaker_activity,
    build_default_mic_assignments,
)


def _write_wav(path, samples, sample_rate=16_000):
    sf.write(str(path), samples.astype(np.float32), sample_rate)


def test_build_default_mic_assignments_ignores_mix_track():
    assignments = build_default_mic_assignments([
        "/material/Podcast - Hartmut Rosa mix.wav",
        "/material/MIC1.wav",
        "/material/MIC2.wav",
    ])

    assert [a.path for a in assignments] == ["/material/MIC1.wav", "/material/MIC2.wav"]
    assert [a.speaker for a in assignments] == [SpeakerId.MATZE, SpeakerId.GUEST]


def test_build_default_mic_assignments_handles_hm_multitrack_layout():
    assignments = build_default_mic_assignments([
        "/material/Podcast - Hartmut Rosa MIX.wav",
        "/material/MIC1.wav",
        "/material/MIC2.wav",
        "/material/MIC3_Keyboard.WAV",
        "/material/MIC4.wav",
    ])

    assert [a.path for a in assignments] == ["/material/MIC1.wav", "/material/MIC2.wav"]
    assert [a.speaker for a in assignments] == [SpeakerId.MATZE, SpeakerId.GUEST]


def test_analyze_speaker_activity_detects_dominant_tracks_and_writes_csv(tmp_path):
    sr = 16_000
    duration_s = 3
    t = np.arange(sr * duration_s) / sr

    mic1 = np.random.RandomState(1).normal(0, 0.002, sr * duration_s)
    mic2 = np.random.RandomState(2).normal(0, 0.002, sr * duration_s)

    matze_signal = 0.30 * np.sin(2 * np.pi * 220 * t[:sr])
    guest_signal = 0.25 * np.sin(2 * np.pi * 180 * t[:sr])

    mic1[0:sr] += matze_signal
    mic2[0:sr] += matze_signal * 0.08

    mic2[int(1.5 * sr):int(2.5 * sr)] += guest_signal
    mic1[int(1.5 * sr):int(2.5 * sr)] += guest_signal * 0.08

    mic1_path = tmp_path / "MIC1.wav"
    mic2_path = tmp_path / "MIC2.wav"
    csv_path = tmp_path / "speaker_activity.csv"
    _write_wav(mic1_path, mic1, sr)
    _write_wav(mic2_path, mic2, sr)

    assignments = [
        MicAssignment(track_index=0, path=str(mic1_path), speaker=SpeakerId.MATZE),
        MicAssignment(track_index=1, path=str(mic2_path), speaker=SpeakerId.GUEST),
    ]

    frames = analyze_speaker_activity(
        assignments,
        params=SPEAKER_ACTIVITY_DEFAULTS,
        csv_path=str(csv_path),
    )

    assert frames
    matze_frames = [f for f in frames if 200 <= f.start_ms <= 800]
    guest_frames = [f for f in frames if 1_700 <= f.start_ms <= 2_300]

    assert any(f.raw_speaker is SpeakerId.MATZE for f in matze_frames)
    assert any(f.raw_speaker is SpeakerId.GUEST for f in guest_frames)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    assert rows
    assert rows[0].keys() >= {
        "start_ms",
        "end_ms",
        "matze_db",
        "guest_db",
        "matze_noise_floor_db",
        "guest_noise_floor_db",
        "dominance_db",
        "raw_speaker",
        "smoothed_speaker",
        "confidence",
    }
