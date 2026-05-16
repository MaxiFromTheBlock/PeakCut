import os

# Must be set before PyQt6 is imported anywhere (conftest loads before test
# modules). Without this the documented `pytest tests/` command segfaults on
# headless/CI machines because Qt picks the native platform. setdefault keeps
# an explicit override (e.g. a dev wanting a visible run) intact.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest

from core.project import PeakCutProject
from core.peak import Peak


@pytest.fixture(scope="session", autouse=True)
def _qt_app():
    """One QApplication, held for the whole session.

    PyQt6 garbage-collects a discarded QApplication wrapper, which destroys
    the C++ app and aborts the next QWidget ("Must construct a QApplication
    before a QWidget"). A session-scoped fixture keeps a live reference so
    the per-test ``_app()`` helpers just find this instance.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def tmp_export_dir(tmp_path):
    """Temporary export directory."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    return str(export_dir)


@pytest.fixture
def sample_project(tmp_export_dir):
    """Project with fake file paths (files don't need to exist for name extraction)."""
    project = PeakCutProject()
    project.export_dir = tmp_export_dir
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
