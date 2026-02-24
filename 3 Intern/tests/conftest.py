import pytest

from core.project import PeakCutProject
from core.peak import Peak


@pytest.fixture
def tmp_export_dir(tmp_path):
    """Temporary export directory."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    return str(export_dir)


@pytest.fixture
def sample_project(tmp_export_dir):
    """Project with fake file paths (files don't need to exist for name extraction)."""
    project = PeakCutProject(tmp_export_dir)
    project.set_files(
        keyboard="/external/recordings/keys.wav",
        mics=[
            "/external/recordings/Podcast - Max Mustermann mix.wav",
            "/external/recordings/Podcast - Max Mustermann mic1.wav",
        ],
        videos=[
            "/external/recordings/CAM_A.mp4",
        ],
    )
    return project


@pytest.fixture
def sample_config():
    """Minimal config dict."""
    return {
        "threshold_factor": 0.3,
        "min_gap_ms": 12000,
        "preview_duration_ms": 1000,
        "context_duration_ms": 15000,
        "fps": 25,
        "tts_voice": "Anna",
        "lut_path": "",
    }


@pytest.fixture
def sample_peaks():
    """List of test peaks (peak at index 1 is ignored)."""
    peaks = [
        Peak(index=0, position_ms=10000, context_ms=15000),
        Peak(index=1, position_ms=30000, context_ms=15000),
        Peak(index=2, position_ms=55000, context_ms=15000),
    ]
    peaks[1].ignored = True
    return peaks
