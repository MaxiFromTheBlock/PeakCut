"""End-to-end pipeline test with synthetic test material.

Generates small audio/video files, runs the full analysis subprocess,
loads results into a session, and runs all exporters. This tests
everything except the GUI.

Test material:
- Keyboard WAV (~2s): 3 loud impulses at known positions
- Mic WAV (~2s): low-level noise (simulates speech)
- Video MP4 (~2s): silent black video with audio tone for sync
"""
import os
import sys
import json
import subprocess

import numpy as np
import pytest
from pydub import AudioSegment

from core.session import PeakCutSession
from core.project import PeakCutProject
from core.audio import detect_peaks
from core.sync import calculate_offset, load_audio_as_array, format_offset
from core.exporters import MP3Exporter, TXTExporter, XMLExporter
from utils import ms_to_timecode, parse_timecode_to_ms, validate_media_file


# ---------------------------------------------------------------------------
# Synthetic test material generators
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100
DURATION_MS = 2000
# Peak positions in the keyboard track (ms)
PEAK_POSITIONS_MS = [400, 1000, 1600]


def _generate_keyboard_wav(path):
    """Generate a short WAV with 3 loud impulses (peaks) at known positions."""
    num_samples = int(SAMPLE_RATE * DURATION_MS / 1000)
    samples = np.zeros(num_samples, dtype=np.int16)

    # Insert loud impulses at peak positions
    for peak_ms in PEAK_POSITIONS_MS:
        center = int(peak_ms * SAMPLE_RATE / 1000)
        # 20ms burst of loud signal
        burst_len = int(0.020 * SAMPLE_RATE)
        start = max(0, center - burst_len // 2)
        end = min(num_samples, start + burst_len)
        samples[start:end] = 30000  # loud

    audio = AudioSegment(
        data=samples.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )
    audio.export(path, format="wav")


def _generate_mic_wav(path):
    """Generate a short WAV with low-level noise (simulates speech/ambient)."""
    num_samples = int(SAMPLE_RATE * DURATION_MS / 1000)
    rng = np.random.RandomState(42)
    samples = (rng.randn(num_samples) * 500).astype(np.int16)

    audio = AudioSegment(
        data=samples.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )
    audio.export(path, format="wav")


def _generate_video_mp4(path, audio_path):
    """Generate a 2-second black video with audio from the mic track."""
    duration_s = DURATION_MS / 1000
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=black:s=320x240:d={duration_s}:r=25",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-shortest",
            path,
        ],
        capture_output=True,
        timeout=30,
    )
    assert os.path.exists(path), f"ffmpeg failed to create {path}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_material(tmp_path):
    """Generate all synthetic test files and return their paths."""
    keyboard_path = str(tmp_path / "keyboard.wav")
    mic_path = str(tmp_path / "Podcast - Testgast mix.wav")
    video_path = str(tmp_path / "CAM_A.mp4")
    export_dir = str(tmp_path / "export")
    temp_dir = str(tmp_path / "temp")

    os.makedirs(export_dir)
    os.makedirs(temp_dir)

    _generate_keyboard_wav(keyboard_path)
    _generate_mic_wav(mic_path)
    _generate_video_mp4(video_path, mic_path)

    return {
        "keyboard": keyboard_path,
        "mic": mic_path,
        "video": video_path,
        "export_dir": export_dir,
        "temp_dir": temp_dir,
    }


@pytest.fixture
def test_config():
    return {
        "threshold_factor": 0.3,
        "min_gap_ms": 200,  # short gap for 2-second test material
        "preview_duration_ms": 100,
        "context_duration_ms": 300,
        "fps": 25,
        "tts_voice": "Anna",
        "lut_path": "",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPeakDetection:
    """Test peak detection on synthetic keyboard audio."""

    def test_finds_peaks(self, test_material):
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.3, min_gap_ms=200)
        assert len(peaks) == 3, f"Expected 3 peaks, got {len(peaks)}"

    def test_peak_positions_are_close(self, test_material):
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.3, min_gap_ms=200)
        for expected_ms, actual_ms in zip(PEAK_POSITIONS_MS, peaks):
            assert abs(expected_ms - actual_ms) < 50, (
                f"Peak at {actual_ms}ms too far from expected {expected_ms}ms"
            )


class TestAnalysisSubprocess:
    """Test the analysis subprocess end-to-end."""

    def test_subprocess_returns_peaks(self, test_material, test_config):
        config_data = {
            "keyboard_track": test_material["keyboard"],
            "mic_tracks": [test_material["mic"]],
            "videos": [test_material["video"]],
            "reference_track": test_material["mic"],
            "temp_dir": test_material["temp_dir"],
            "export_dir": test_material["export_dir"],
            "config": test_config,
        }

        script_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
        )
        script_path = os.path.join(script_dir, "core", "analysis_process.py")

        result = subprocess.run(
            [sys.executable, script_path, json.dumps(config_data)],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=60,
        )

        assert result.returncode == 0, f"Subprocess failed: {result.stderr}"

        results = json.loads(result.stdout)
        assert results["error"] is None
        assert len(results["peaks"]) == 3
        assert len(results["video_offsets"]) == 1

    def test_subprocess_returns_video_offset(self, test_material, test_config):
        config_data = {
            "keyboard_track": test_material["keyboard"],
            "mic_tracks": [test_material["mic"]],
            "videos": [test_material["video"]],
            "reference_track": test_material["mic"],
            "temp_dir": test_material["temp_dir"],
            "export_dir": test_material["export_dir"],
            "config": test_config,
        }

        script_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
        )
        script_path = os.path.join(script_dir, "core", "analysis_process.py")

        result = subprocess.run(
            [sys.executable, script_path, json.dumps(config_data)],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=60,
        )

        results = json.loads(result.stdout)
        video_filename, offset_tc = results["video_offsets"][0]
        assert video_filename == "CAM_A.mp4"
        # Offset should be parseable
        offset_ms = parse_timecode_to_ms(offset_tc, 25)
        assert isinstance(offset_ms, int)


class TestSessionLoading:
    """Test loading analysis results into a session."""

    def test_session_loads_peaks(self, test_material, test_config):
        project = PeakCutProject(test_material["export_dir"])
        project.set_files(
            test_material["keyboard"],
            [test_material["mic"]],
            [test_material["video"]],
        )
        session = PeakCutSession(project, test_config)

        # Simulate analysis results
        results = {
            "peaks": [
                {"index": 0, "position_ms": 400, "in_point_ms": 100, "out_point_ms": 700, "context_ms": 300, "ignored": False},
                {"index": 1, "position_ms": 1000, "in_point_ms": 700, "out_point_ms": 1300, "context_ms": 300, "ignored": False},
                {"index": 2, "position_ms": 1600, "in_point_ms": 1300, "out_point_ms": 1900, "context_ms": 300, "ignored": False},
            ],
            "video_offsets": [("CAM_A.mp4", "00:00:00:02")],
        }

        session.load_analysis_results(results)

        assert len(session.peaks) == 3
        assert session.current_peak == 0
        assert session.get_video_offset_ms(test_material["video"]) == 80  # 2 frames at 25fps

    def test_session_loads_audio(self, test_material, test_config):
        project = PeakCutProject(test_material["export_dir"])
        project.set_files(
            test_material["keyboard"],
            [test_material["mic"]],
            [],
        )
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({"peaks": [
            {"index": 0, "position_ms": 400, "context_ms": 300, "ignored": False},
        ], "video_offsets": []})

        session.load_audio_lazy()

        assert session.keyboard_audio is not None
        assert len(session.mic_audios) == 1


class TestExportPipeline:
    """Test all exporters with real audio files."""

    def _make_session_with_audio(self, test_material, test_config):
        project = PeakCutProject(test_material["export_dir"])
        project.set_files(
            test_material["keyboard"],
            [test_material["mic"]],
            [test_material["video"]],
        )
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 400, "in_point_ms": 100, "out_point_ms": 700, "context_ms": 300, "ignored": False},
                {"index": 1, "position_ms": 1000, "in_point_ms": 700, "out_point_ms": 1300, "context_ms": 300, "ignored": True},
                {"index": 2, "position_ms": 1600, "in_point_ms": 1300, "out_point_ms": 1900, "context_ms": 300, "ignored": False},
            ],
            "video_offsets": [("CAM_A.mp4", "00:00:00:02")],
        })
        return session

    def test_mp3_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        exporter = MP3Exporter()
        result = exporter.export(session)

        assert result != ""
        assert os.path.exists(result)
        assert result.endswith(".mp3")
        assert "Testgast" in result

    def test_txt_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        exporter = TXTExporter()
        result = exporter.export(session)

        assert result != ""
        assert os.path.exists(result)

        content = open(result).read()
        # Should contain 2 peak entries (peak 1 is ignored)
        assert "KEYBOARD PEAKS" in content
        # Count [PEAK N] headers
        peak_headers = [l for l in content.splitlines() if l.strip().startswith("[PEAK")]
        assert len(peak_headers) == 2

    def test_xml_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        exporter = XMLExporter()
        result = exporter.export(session)

        assert result != ""
        assert os.path.exists(result)
        assert result.endswith(".xml")

        # Verify it's valid XML
        import xml.etree.ElementTree as ET
        tree = ET.parse(result)
        root = tree.getroot()
        assert root.tag == "xmeml"

    def test_all_exports_create_files(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)

        results = []
        for ExporterClass in [MP3Exporter, TXTExporter, XMLExporter]:
            result = ExporterClass().export(session)
            results.append(result)

        assert all(r != "" for r in results)
        assert all(os.path.exists(r) for r in results)

        export_files = os.listdir(test_material["export_dir"])
        assert len(export_files) == 3


# ---------------------------------------------------------------------------
# Validate media file
# ---------------------------------------------------------------------------

class TestValidateMediaFile:
    """Test ffprobe-based file validation."""

    def test_valid_wav(self, test_material):
        assert validate_media_file(test_material["keyboard"]) is None

    def test_valid_video(self, test_material):
        assert validate_media_file(test_material["video"]) is None

    def test_nonexistent_file(self):
        result = validate_media_file("/does/not/exist.wav")
        assert result is not None
        assert "nicht gefunden" in result

    def test_not_a_media_file(self, tmp_path):
        txt = tmp_path / "fake.wav"
        txt.write_text("this is not audio")
        result = validate_media_file(str(txt))
        assert result is not None

    def test_file_without_audio_stream(self, tmp_path):
        # Create a video-only file (no audio)
        video_path = str(tmp_path / "no_audio.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=16x16:d=0.1:r=25",
             "-an", "-c:v", "libx264", "-preset", "ultrafast", video_path],
            capture_output=True, timeout=10,
        )
        result = validate_media_file(video_path)
        assert result is not None
        assert "Kein Audio" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases that could break the pipeline."""

    def test_no_peaks_found(self, test_material):
        """Threshold at 100% means nothing exceeds max*1.0, so zero peaks."""
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=1.0, min_gap_ms=200)
        assert len(peaks) == 0

    def test_all_peaks_ignored_export(self, test_material, test_config):
        """Export with all peaks ignored should return empty string."""
        project = PeakCutProject(test_material["export_dir"])
        project.set_files(test_material["keyboard"], [test_material["mic"]], [])
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 400, "context_ms": 300, "ignored": True},
                {"index": 1, "position_ms": 1000, "context_ms": 300, "ignored": True},
            ],
            "video_offsets": [],
        })
        assert TXTExporter().export(session) == ""
        assert MP3Exporter().export(session) == ""

    def test_audio_only_workflow(self, test_material, test_config):
        """Full pipeline without videos (audio-only)."""
        config_data = {
            "keyboard_track": test_material["keyboard"],
            "mic_tracks": [test_material["mic"]],
            "videos": [],
            "reference_track": test_material["mic"],
            "temp_dir": test_material["temp_dir"],
            "export_dir": test_material["export_dir"],
            "config": test_config,
        }

        script_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
        )
        script_path = os.path.join(script_dir, "core", "analysis_process.py")

        result = subprocess.run(
            [sys.executable, script_path, json.dumps(config_data)],
            capture_output=True, text=True, cwd=script_dir, timeout=60,
        )

        assert result.returncode == 0
        results = json.loads(result.stdout)
        assert results["error"] is None
        assert len(results["peaks"]) == 3
        assert results["video_offsets"] == []

    def test_single_peak_export(self, test_material, test_config):
        """Export with just one peak."""
        project = PeakCutProject(test_material["export_dir"])
        project.set_files(test_material["keyboard"], [test_material["mic"]], [])
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 400, "in_point_ms": 100, "out_point_ms": 700, "context_ms": 300, "ignored": False},
            ],
            "video_offsets": [],
        })

        mp3 = MP3Exporter().export(session)
        txt = TXTExporter().export(session)
        assert os.path.exists(mp3)
        assert os.path.exists(txt)
        content = open(txt).read()
        assert "[PEAK 1]" in content


# ---------------------------------------------------------------------------
# Sync unit tests
# ---------------------------------------------------------------------------

class TestSyncUnits:
    """Unit tests for sync.py functions."""

    def test_load_audio_mono(self, test_material):
        data, sr = load_audio_as_array(test_material["mic"])
        assert len(data.shape) == 1  # mono
        assert sr == SAMPLE_RATE
        assert len(data) > 0

    def test_calculate_offset_identical(self, test_material):
        """Identical signals should have zero offset."""
        data, sr = load_audio_as_array(test_material["mic"])
        offset = calculate_offset(data, data)
        # Allow small tolerance due to downsampling
        assert abs(offset) < 100

    def test_format_offset_zero(self):
        assert format_offset(0.0, 25) == "00:00:00:00"

    def test_format_offset_positive(self):
        result = format_offset(1.5, 25)
        assert result == "00:00:01:12"  # 1.5s * 25fps = 37.5 → 37 frames → 1s 12f

    def test_format_offset_negative(self):
        result = format_offset(-2.0, 25)
        assert result.startswith("-")
        assert "00:00:02:00" in result
