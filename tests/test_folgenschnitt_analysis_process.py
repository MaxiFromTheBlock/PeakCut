import numpy as np
import soundfile as sf

from core.analysis_process import run_analysis


def _write_wav(path, samples, sample_rate=16_000):
    sf.write(str(path), samples.astype(np.float32), sample_rate)


def test_run_analysis_includes_speaker_activity_for_two_mics(tmp_path):
    sr = 16_000
    duration_s = 1
    silence = np.zeros(sr * duration_s, dtype=np.float32)
    mic1 = np.random.RandomState(1).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic2 = np.random.RandomState(2).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic1[: sr // 2] += 0.2
    mic2[sr // 2:] += 0.2

    keyboard_path = tmp_path / "keyboard.wav"
    mic1_path = tmp_path / "MIC1.wav"
    mic2_path = tmp_path / "MIC2.wav"
    export_dir = tmp_path / "export"
    temp_dir = tmp_path / "temp"
    export_dir.mkdir()
    temp_dir.mkdir()

    _write_wav(keyboard_path, silence, sr)
    _write_wav(mic1_path, mic1, sr)
    _write_wav(mic2_path, mic2, sr)

    results = run_analysis({
        "keyboard_track": str(keyboard_path),
        "mic_tracks": [str(mic1_path), str(mic2_path)],
        "videos": [],
        "reference_track": None,
        "temp_dir": str(temp_dir),
        "export_dir": str(export_dir),
        "config": {
            "threshold_factor": 1.0,
            "min_gap_ms": 12_000,
            "context_duration_ms": 15_000,
            "fps": 25,
        },
    })

    assert "speaker_activity" in results
    assert isinstance(results["speaker_activity"], list)
    assert results["speaker_activity_csv"] == str(export_dir / "speaker_activity.csv")
