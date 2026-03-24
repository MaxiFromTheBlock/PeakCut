"""End-to-end pipeline test with realistic synthetic test material.

Generates audio/video files that mimic real podcast recording conditions,
runs the full analysis subprocess, loads results into a session, and runs
all exporters. This tests everything except the GUI.

Test material (30 seconds, 44100 Hz):
- Keyboard WAV: 3 peaks with realistic attack/decay envelope + ambient noise
- 2x Mic WAV: simulated speech pattern (bursts + pauses) with room noise
- 2x Video MP4: black video with offset audio for sync testing
- Mix WAV: combined mic tracks (stereo, named for guest name extraction)
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
from core.detection import detect_peaks
from core.sync import calculate_offset, load_audio_as_array, format_offset
from core.exporters import MP3Exporter, TXTExporter, XMLExporter
from utils import ms_to_timecode, parse_timecode_to_ms, validate_media_file


# ---------------------------------------------------------------------------
# Synthetic test material generators — realistic conditions
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100
DURATION_S = 30
DURATION_MS = DURATION_S * 1000
# Peak positions in the keyboard track (ms) — spaced like real foot pedal hits
PEAK_POSITIONS_MS = [5000, 15000, 24000]
# Known video offsets in seconds (camera started N seconds after audio)
VIDEO_OFFSET_A_S = 1.5
VIDEO_OFFSET_B_S = 3.2


def _generate_keyboard_wav(path):
    """Generate keyboard track: loud peaks with attack/decay + ambient noise.

    Mimics a real foot pedal signal: short, sharp hits with exponential decay
    on top of low-level room noise. Both positive and negative amplitudes.
    """
    rng = np.random.RandomState(42)
    num_samples = int(SAMPLE_RATE * DURATION_S)

    # Ambient room noise (low level, ~2% of max)
    samples = (rng.randn(num_samples) * 600).astype(np.float64)

    for peak_ms in PEAK_POSITIONS_MS:
        center = int(peak_ms * SAMPLE_RATE / 1000)
        # Attack: 5ms ramp up, Sustain: 15ms, Decay: 30ms exponential
        attack_len = int(0.005 * SAMPLE_RATE)
        sustain_len = int(0.015 * SAMPLE_RATE)
        decay_len = int(0.030 * SAMPLE_RATE)
        total_len = attack_len + sustain_len + decay_len

        start = max(0, center - attack_len)
        if start + total_len > num_samples:
            continue

        # Build envelope
        envelope = np.zeros(total_len)
        # Attack: linear ramp 0 → 1
        envelope[:attack_len] = np.linspace(0, 1, attack_len)
        # Sustain: hold at 1
        envelope[attack_len:attack_len + sustain_len] = 1.0
        # Decay: exponential falloff
        envelope[attack_len + sustain_len:] = np.exp(-np.linspace(0, 5, decay_len))

        # Apply with high amplitude + some frequency content (not just DC)
        t = np.arange(total_len) / SAMPLE_RATE
        peak_signal = envelope * 28000 * np.sin(2 * np.pi * 200 * t)
        samples[start:start + total_len] += peak_signal

    samples = np.clip(samples, -32768, 32767).astype(np.int16)

    audio = AudioSegment(
        data=samples.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )
    audio.export(path, format="wav")


def _generate_speech_wav(path, seed=42):
    """Generate mic track: simulated speech pattern with pauses.

    Creates bursts of bandpass-filtered noise (mimics vocal frequencies)
    with natural pauses between phrases, on top of room tone.
    """
    rng = np.random.RandomState(seed)
    num_samples = int(SAMPLE_RATE * DURATION_S)

    # Room tone (very low level)
    samples = (rng.randn(num_samples) * 100).astype(np.float64)

    # Generate speech-like bursts at random intervals
    pos = 0
    while pos < num_samples:
        # Speech burst: 0.5-2s of filtered noise
        burst_len = int(rng.uniform(0.5, 2.0) * SAMPLE_RATE)
        burst_len = min(burst_len, num_samples - pos)
        if burst_len <= 0:
            break

        # Bandpass-like signal (mix of vocal frequencies 100-3000 Hz)
        t = np.arange(burst_len) / SAMPLE_RATE
        burst = np.zeros(burst_len)
        for freq in [150, 300, 600, 1200, 2400]:
            amp = rng.uniform(500, 3000)
            burst += amp * np.sin(2 * np.pi * freq * t + rng.uniform(0, 2 * np.pi))

        # Apply smooth envelope (fade in/out)
        fade = int(0.02 * SAMPLE_RATE)
        if burst_len > 2 * fade:
            burst[:fade] *= np.linspace(0, 1, fade)
            burst[-fade:] *= np.linspace(1, 0, fade)

        # Vary amplitude (some words louder than others)
        burst *= rng.uniform(0.5, 1.0)
        samples[pos:pos + burst_len] += burst

        # Pause: 0.2-1.0s of silence between phrases
        pause_len = int(rng.uniform(0.2, 1.0) * SAMPLE_RATE)
        pos += burst_len + pause_len

    samples = np.clip(samples, -32768, 32767).astype(np.int16)

    audio = AudioSegment(
        data=samples.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1,
    )
    audio.export(path, format="wav")


def _generate_mix_wav(mic_paths, output_path):
    """Generate stereo mix from mic tracks (like a real podcast mix)."""
    segments = [AudioSegment.from_file(p) for p in mic_paths]
    # Mix down to stereo: mic1 slightly left, mic2 slightly right
    mixed = segments[0]
    for seg in segments[1:]:
        mixed = mixed.overlay(seg)
    mixed = mixed.set_channels(2)
    mixed.export(output_path, format="wav")


def _generate_video_mp4(path, speech_path, offset_s=0.0):
    """Generate video with speech audio, offset by a known amount.

    The offset simulates a camera that started recording N seconds after
    the audio recorder. We prepend silence to shift the audio.
    """
    duration_s = DURATION_S + offset_s + 1  # slightly longer than audio
    # Create offset audio: prepend silence, then speech
    speech = AudioSegment.from_file(speech_path)
    offset_audio = AudioSegment.silent(duration=int(offset_s * 1000)) + speech
    temp_audio = path + ".offset.wav"
    offset_audio.export(temp_audio, format="wav")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=black:s=1920x1080:d={duration_s}:r=25",
            "-i", temp_audio,
            "-c:v", "libx264",  "-preset", "ultrafast",
            "-c:a", "aac", "-shortest",
            path,
        ],
        capture_output=True,
        timeout=60,
    )
    os.remove(temp_audio)
    assert os.path.exists(path), f"ffmpeg failed to create {path}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_material(tmp_path):
    """Generate all synthetic test files and return their paths."""
    keyboard_path = str(tmp_path / "keyboard.wav")
    mic1_path = str(tmp_path / "mic1.wav")
    mic2_path = str(tmp_path / "mic2.wav")
    mix_path = str(tmp_path / "Hotel Matze - Testgast mix.wav")
    video_a_path = str(tmp_path / "CAM_A.mp4")
    video_b_path = str(tmp_path / "CAM_B.mp4")
    export_dir = str(tmp_path / "export")
    temp_dir = str(tmp_path / "temp")

    os.makedirs(export_dir)
    os.makedirs(temp_dir)

    _generate_keyboard_wav(keyboard_path)
    _generate_speech_wav(mic1_path, seed=42)
    _generate_speech_wav(mic2_path, seed=99)
    _generate_mix_wav([mic1_path, mic2_path], mix_path)
    _generate_video_mp4(video_a_path, mic1_path, offset_s=VIDEO_OFFSET_A_S)
    _generate_video_mp4(video_b_path, mic1_path, offset_s=VIDEO_OFFSET_B_S)

    return {
        "keyboard": keyboard_path,
        "mic": mix_path,
        "mic1": mic1_path,
        "mic2": mic2_path,
        "video": video_a_path,
        "video_a": video_a_path,
        "video_b": video_b_path,
        "export_dir": export_dir,
        "temp_dir": temp_dir,
    }


@pytest.fixture
def test_config():
    return {
        "threshold_factor": 0.3,
        "min_gap_ms": 3000,
        "preview_duration_ms": 1000,
        "context_duration_ms": 5000,
        "fps": 25,
        "tts_voice": "Anna",
        "lut_path": "",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPeakDetection:
    """Test peak detection on synthetic keyboard audio."""

    def test_finds_correct_number_of_peaks(self, test_material):
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.3, min_gap_ms=3000)
        assert len(peaks) == 3, f"Expected 3 peaks, got {len(peaks)}: {peaks}"

    def test_peak_positions_are_close(self, test_material):
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.3, min_gap_ms=3000)
        for expected_ms, actual_ms in zip(PEAK_POSITIONS_MS, peaks):
            assert abs(expected_ms - actual_ms) < 100, (
                f"Peak at {actual_ms}ms too far from expected {expected_ms}ms"
            )

    def test_high_threshold_finds_no_peaks(self, test_material):
        """Threshold at 100% means nothing exceeds max*1.0, so zero peaks."""
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=1.0, min_gap_ms=3000)
        assert len(peaks) == 0

    def test_low_threshold_finds_more_peaks(self, test_material):
        """Very low threshold should find more peaks (ambient noise)."""
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.05, min_gap_ms=3000)
        assert len(peaks) >= 3

    def test_gap_filtering_works(self, test_material):
        """Large gap should merge nearby peaks."""
        peaks = detect_peaks(test_material["keyboard"], threshold_factor=0.3, min_gap_ms=20000)
        assert len(peaks) < 3


class TestAnalysisSubprocess:
    """Test the analysis subprocess end-to-end."""

    def _run_analysis(self, test_material, test_config, videos=None):
        if videos is None:
            videos = [test_material["video_a"], test_material["video_b"]]
        config_data = {
            "keyboard_track": test_material["keyboard"],
            "mic_tracks": [test_material["mic"]],
            "videos": videos,
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
            timeout=120,
        )

        assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
        return json.loads(result.stdout)

    def test_subprocess_returns_peaks(self, test_material, test_config):
        results = self._run_analysis(test_material, test_config)
        assert results["error"] is None
        assert len(results["peaks"]) == 3

    def test_subprocess_returns_video_offsets(self, test_material, test_config):
        results = self._run_analysis(test_material, test_config)
        assert len(results["video_offsets"]) == 2

        # Verify both cameras have offsets
        filenames = {vo[0] for vo in results["video_offsets"]}
        assert "CAM_A.mp4" in filenames
        assert "CAM_B.mp4" in filenames

    def test_subprocess_audio_only(self, test_material, test_config):
        """Full pipeline without videos (audio-only)."""
        results = self._run_analysis(test_material, test_config, videos=[])
        assert results["error"] is None
        assert len(results["peaks"]) == 3
        assert results["video_offsets"] == []


class TestSessionLoading:
    """Test loading analysis results into a session."""

    def _make_session(self, test_material, test_config):
        project = PeakCutProject()
        project.export_dir = test_material["export_dir"]
        project.set_files(
            test_material["keyboard"],
            [test_material["mic"]],
            [test_material["video_a"], test_material["video_b"]],
        )
        return PeakCutSession(project, test_config)

    def test_session_loads_peaks(self, test_material, test_config):
        session = self._make_session(test_material, test_config)

        results = {
            "peaks": [
                {"index": 0, "position_ms": 5000, "in_point_ms": 2500, "out_point_ms": 7500, "context_ms": 5000, "ignored": False},
                {"index": 1, "position_ms": 15000, "in_point_ms": 12500, "out_point_ms": 17500, "context_ms": 5000, "ignored": False},
                {"index": 2, "position_ms": 24000, "in_point_ms": 21500, "out_point_ms": 26500, "context_ms": 5000, "ignored": False},
            ],
            "video_offsets": [("CAM_A.mp4", "00:00:01:12"), ("CAM_B.mp4", "00:00:03:05")],
        }

        session.load_analysis_results(results)

        assert len(session.peaks) == 3
        assert session.current_peak == 0
        assert session.get_video_offset_ms(test_material["video_a"]) == 1480  # 1s + 12 frames at 25fps
        assert session.get_video_offset_ms(test_material["video_b"]) == 3200  # 3s + 5 frames at 25fps

    def test_session_loads_audio(self, test_material, test_config):
        session = self._make_session(test_material, test_config)
        session.load_analysis_results({"peaks": [
            {"index": 0, "position_ms": 5000, "context_ms": 5000, "ignored": False},
        ], "video_offsets": []})

        session.load_audio_lazy()

        assert session.keyboard_audio is not None
        assert len(session.mic_audios) == 1
        # Audio should be roughly the expected duration
        assert abs(len(session.keyboard_audio) - DURATION_MS) < 100

    def test_session_status_callback(self, test_material, test_config):
        """Status updates should fire callbacks (Qt-free)."""
        session = self._make_session(test_material, test_config)
        session.load_analysis_results({"peaks": [
            {"index": 0, "position_ms": 5000, "context_ms": 5000, "ignored": False},
        ], "video_offsets": []})

        messages = []
        session.status_update.connect(messages.append)
        session.load_audio_lazy()

        assert len(messages) == 2
        assert "Lade Audio" in messages[0]
        assert "geladen" in messages[1]


class TestExportPipeline:
    """Test all exporters with synthetic audio files."""

    def _make_session_with_audio(self, test_material, test_config):
        project = PeakCutProject()
        project.export_dir = test_material["export_dir"]
        project.set_files(
            test_material["keyboard"],
            [test_material["mic"]],
            [test_material["video_a"]],
        )
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 5000, "in_point_ms": 2500, "out_point_ms": 7500, "context_ms": 5000, "ignored": False},
                {"index": 1, "position_ms": 15000, "in_point_ms": 12500, "out_point_ms": 17500, "context_ms": 5000, "ignored": True},
                {"index": 2, "position_ms": 24000, "in_point_ms": 21500, "out_point_ms": 26500, "context_ms": 5000, "ignored": False},
            ],
            "video_offsets": [("CAM_A.mp4", "00:00:01:12")],
        })
        return session

    def test_mp3_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        result = MP3Exporter().export(session)

        assert result != ""
        assert os.path.exists(result)
        assert result.endswith(".mp3")
        assert "Testgast" in result

        # Exported MP3 should have reasonable size (not empty, not huge)
        size = os.path.getsize(result)
        assert size > 1000, f"MP3 too small: {size} bytes"

    def test_txt_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        result = TXTExporter().export(session)

        assert result != ""
        assert os.path.exists(result)

        content = open(result).read()
        assert "KEYBOARD PEAKS" in content
        # 2 active peaks (peak at index 1 is ignored)
        peak_headers = [l for l in content.splitlines() if l.strip().startswith("[PEAK")]
        assert len(peak_headers) == 2

        # Verify timecodes are present
        assert "peak_time" in content
        assert "clip_start" in content
        assert "clip_end" in content

        # Video offset should be in the file
        assert "VIDEO OFFSETS" in content
        assert "CAM_A" in content

    def test_xml_export(self, test_material, test_config):
        session = self._make_session_with_audio(test_material, test_config)
        result = XMLExporter().export(session)

        assert result != ""
        assert os.path.exists(result)
        assert result.endswith(".xml")

        # Verify it's valid XML with correct structure
        import xml.etree.ElementTree as ET
        tree = ET.parse(result)
        root = tree.getroot()
        assert root.tag == "xmeml"

        # Should have video and audio sections
        media = root.find(".//media")
        assert media is not None
        assert media.find("video") is not None
        assert media.find("audio") is not None

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

    def test_all_peaks_ignored_export(self, test_material, test_config):
        """Export with all peaks ignored should return empty string."""
        project = PeakCutProject()
        project.export_dir = test_material["export_dir"]
        project.set_files(test_material["keyboard"], [test_material["mic"]], [])
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 5000, "context_ms": 5000, "ignored": True},
                {"index": 1, "position_ms": 15000, "context_ms": 5000, "ignored": True},
            ],
            "video_offsets": [],
        })
        assert TXTExporter().export(session) == ""
        assert MP3Exporter().export(session) == ""

    def test_single_peak_export(self, test_material, test_config):
        """Export with just one peak."""
        project = PeakCutProject()
        project.export_dir = test_material["export_dir"]
        project.set_files(test_material["keyboard"], [test_material["mic"]], [])
        session = PeakCutSession(project, test_config)
        session.load_analysis_results({
            "peaks": [
                {"index": 0, "position_ms": 5000, "in_point_ms": 2500, "out_point_ms": 7500, "context_ms": 5000, "ignored": False},
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
# Sync tests
# ---------------------------------------------------------------------------

class TestSyncUnits:
    """Unit tests for sync.py functions."""

    def test_load_audio_mono(self, test_material):
        data, sr = load_audio_as_array(test_material["mic"])
        assert len(data.shape) == 1  # mono (stereo gets averaged)
        assert sr == SAMPLE_RATE
        assert len(data) > 0

    def test_load_audio_with_limit(self, test_material):
        """Loading with max_seconds should truncate."""
        data_full, sr = load_audio_as_array(test_material["mic"])
        data_short, _ = load_audio_as_array(test_material["mic"], max_seconds=1.0)
        assert len(data_short) == sr  # exactly 1 second
        assert len(data_short) < len(data_full)

    def test_calculate_offset_identical(self, test_material):
        """Identical signals should have zero offset."""
        data, sr = load_audio_as_array(test_material["mic"])
        offset, confidence = calculate_offset(data, data)
        assert abs(offset) < 100
        assert confidence > 0

    def test_calculate_offset_with_known_shift(self, test_material):
        """Shifting a signal by N samples should give offset ~N."""
        data, sr = load_audio_as_array(test_material["mic1"])
        shift_samples = 4410  # 100ms
        shifted = np.concatenate([np.zeros(shift_samples), data])
        offset, confidence = calculate_offset(data, shifted)
        # Should detect the shift (with some tolerance due to downsampling)
        assert abs(offset - shift_samples) < 200, f"Expected ~{shift_samples}, got {offset}"

    def test_format_offset_zero(self):
        assert format_offset(0.0, 25) == "00:00:00:00"

    def test_format_offset_positive(self):
        result = format_offset(1.5, 25)
        assert result == "00:00:01:12"  # 1.5s * 25fps = 37.5 → 37 frames → 1s 12f

    def test_format_offset_negative(self):
        result = format_offset(-2.0, 25)
        assert result.startswith("-")
        assert "00:00:02:00" in result


class TestSyncIntegration:
    """Integration test: sync videos with known offsets."""

    def test_sync_detects_offset(self, test_material, test_config):
        """Sync should detect the known offset between video and reference audio."""
        from core.sync import sync_videos

        results = sync_videos(
            video_files=[test_material["video_a"]],
            reference_path=test_material["mic1"],
            temp_dir=test_material["temp_dir"],
            fps=25,
        )

        assert len(results) == 1
        filename, offset_tc = results[0]
        assert filename == "CAM_A.mp4"

        # Parse offset and verify it's close to the known offset
        offset_ms = parse_timecode_to_ms(offset_tc, 25)
        expected_ms = int(VIDEO_OFFSET_A_S * 1000)
        assert abs(offset_ms - expected_ms) < 500, (
            f"Detected offset {offset_ms}ms, expected ~{expected_ms}ms"
        )

    def test_sync_multiple_cameras(self, test_material, test_config):
        """Multi-camera sync should return offsets for all cameras."""
        from core.sync import sync_videos

        results = sync_videos(
            video_files=[test_material["video_a"], test_material["video_b"]],
            reference_path=test_material["mic1"],
            temp_dir=test_material["temp_dir"],
            fps=25,
        )

        assert len(results) == 2
        offsets = {r[0]: parse_timecode_to_ms(r[1], 25) for r in results}
        assert "CAM_A.mp4" in offsets
        assert "CAM_B.mp4" in offsets

        # Camera B should have a larger offset than Camera A
        assert offsets["CAM_B.mp4"] > offsets["CAM_A.mp4"]
