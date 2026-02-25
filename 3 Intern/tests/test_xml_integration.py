"""Integration tests for the XML export pipeline.

These tests verify that the full pipeline (peaks → offsets → XML) produces
structurally correct FCP XML. They caught the bugs that unit tests missed:
- Video offsets not applied (all in/out identical to audio)
- max(0,...) asymmetry causing duration mismatch
- Frame rounding errors from ms-based duration calculation
"""
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from core.exporters import XMLExporter
from core.peak import Peak
from core.sync import format_offset
from utils import parse_timecode_to_ms, ms_to_frames


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(peaks, video_offsets, videos, mics, export_dir, fps=25):
    """Build a mock session with the given peaks and offsets."""
    session = MagicMock()
    session.config = {"fps": fps}
    session.video_offsets = video_offsets
    session.get_active_peaks.return_value = [(i + 1, p) for i, p in enumerate(peaks)]

    project = MagicMock()
    project.export_dir = export_dir
    project.guest_name = "Test"
    project.videos = videos
    project.mic_tracks = mics
    session.project = project

    return session


def _export_and_parse(session):
    """Run XMLExporter and return parsed ElementTree root."""
    with patch("core.exporters._probe_video_info", return_value=(1920, 1080)), \
         patch("core.exporters._probe_audio_info", return_value=48000):
        xml_path = XMLExporter().export(session)
    assert xml_path, "Export returned empty path"
    return ET.parse(xml_path).getroot()


def _get_clipitems(root, media_type):
    """Extract all clipitems from video or audio tracks."""
    seq = root.find("sequence")
    media = seq.find("media")
    section = media.find(media_type)
    clips = []
    for track in section.findall("track"):
        for clip in track.findall("clipitem"):
            clips.append(clip)
    return clips


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestXMLVideoOffsets:
    """Video clips must use offset-shifted in/out, audio clips must not."""

    @pytest.fixture
    def peaks(self):
        return [
            Peak(index=0, position_ms=60_000, context_ms=15_000),
            Peak(index=1, position_ms=120_000, context_ms=15_000),
        ]

    def test_video_in_out_differs_from_audio(self, peaks, tmp_export_dir):
        """With a +2s offset, video in/out must be shifted by 2s relative to audio."""
        offset_tc = "00:00:02:00"  # +2 seconds = +50 frames at 25fps
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM_A.mp4", offset_tc)],
            videos=["/fake/CAM_A.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        video_clips = _get_clipitems(root, "video")
        audio_clips = _get_clipitems(root, "audio")

        assert len(video_clips) == 2
        assert len(audio_clips) == 2

        offset_ms = parse_timecode_to_ms(offset_tc, 25)
        offset_frames = ms_to_frames(offset_ms, 25)

        for v_clip, a_clip in zip(video_clips, audio_clips):
            v_in = int(v_clip.find("in").text)
            a_in = int(a_clip.find("in").text)
            # Video source position = audio source position + offset
            assert v_in == a_in + offset_frames, \
                f"Video in ({v_in}) should be audio in ({a_in}) + offset ({offset_frames})"

    def test_zero_offset_gives_identical_in_out(self, peaks, tmp_export_dir):
        """With zero offset, video and audio in/out should match."""
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM_A.mp4", "00:00:00:00")],
            videos=["/fake/CAM_A.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        video_clips = _get_clipitems(root, "video")
        audio_clips = _get_clipitems(root, "audio")

        for v_clip, a_clip in zip(video_clips, audio_clips):
            assert int(v_clip.find("in").text) == int(a_clip.find("in").text)
            assert int(v_clip.find("out").text) == int(a_clip.find("out").text)


class TestXMLClipConsistency:
    """Each clipitem must be internally consistent."""

    @pytest.fixture
    def peaks(self):
        return [
            Peak(index=0, position_ms=30_000, context_ms=15_000),
            Peak(index=1, position_ms=90_000, context_ms=15_000),
            Peak(index=2, position_ms=150_000, context_ms=15_000),
        ]

    def test_duration_equals_out_minus_in(self, peaks, tmp_export_dir):
        """<duration> must equal <out> - <in> for every clip."""
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM.mp4", "00:00:05:12")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)

        for media_type in ("video", "audio"):
            for clip in _get_clipitems(root, media_type):
                dur = int(clip.find("duration").text)
                in_f = int(clip.find("in").text)
                out_f = int(clip.find("out").text)
                assert dur == out_f - in_f, \
                    f"{clip.get('id')}: duration ({dur}) != out ({out_f}) - in ({in_f})"

    def test_end_minus_start_equals_duration(self, peaks, tmp_export_dir):
        """<end> - <start> must equal <duration> (timeline placement)."""
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM.mp4", "00:00:03:00")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)

        for media_type in ("video", "audio"):
            for clip in _get_clipitems(root, media_type):
                dur = int(clip.find("duration").text)
                start = int(clip.find("start").text)
                end = int(clip.find("end").text)
                assert end - start == dur, \
                    f"{clip.get('id')}: end-start ({end - start}) != duration ({dur})"

    def test_clips_contiguous_on_timeline(self, peaks, tmp_export_dir):
        """Clips must be placed back-to-back: clip[n].end == clip[n+1].start."""
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM.mp4", "00:00:01:00")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)

        for media_type in ("video", "audio"):
            clips = _get_clipitems(root, media_type)
            for i in range(len(clips) - 1):
                end_a = int(clips[i].find("end").text)
                start_b = int(clips[i + 1].find("start").text)
                assert end_a == start_b, \
                    f"Gap between clip {i} and {i+1}: end={end_a}, next start={start_b}"


class TestXMLTimelineAlignment:
    """Video and audio clips for the same peak must share timeline position."""

    def test_same_start_end_on_timeline(self, tmp_export_dir):
        """For any peak, video start/end must match audio start/end."""
        peaks = [
            Peak(index=0, position_ms=50_000, context_ms=15_000),
            Peak(index=1, position_ms=100_000, context_ms=15_000),
        ]
        session = _make_session(
            peaks=peaks,
            video_offsets=[("CAM.mp4", "00:00:10:00")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        video_clips = _get_clipitems(root, "video")
        audio_clips = _get_clipitems(root, "audio")

        for v_clip, a_clip in zip(video_clips, audio_clips):
            v_start = int(v_clip.find("start").text)
            a_start = int(a_clip.find("start").text)
            v_end = int(v_clip.find("end").text)
            a_end = int(a_clip.find("end").text)
            assert v_start == a_start, f"start mismatch: video={v_start}, audio={a_start}"
            assert v_end == a_end, f"end mismatch: video={v_end}, audio={a_end}"


class TestXMLNegativeOffset:
    """Negative offsets must be clamped to 0 for source positions."""

    def test_negative_offset_clamps_source_in(self, tmp_export_dir):
        """If offset pushes source_in below 0, it should clamp to 0."""
        peak = Peak(index=0, position_ms=5_000, context_ms=15_000)
        # in_point_ms = max(0, 5000-15000) = 0ms
        # With -10s offset: source_in = max(0, 0 + (-10000)) = 0
        session = _make_session(
            peaks=[peak],
            video_offsets=[("CAM.mp4", "-00:00:10:00")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        video_clips = _get_clipitems(root, "video")

        assert len(video_clips) == 1
        v_in = int(video_clips[0].find("in").text)
        assert v_in >= 0, f"Video source in should not be negative: {v_in}"

    def test_negative_offset_duration_still_consistent(self, tmp_export_dir):
        """Even with negative offset clamping, duration = out - in."""
        peak = Peak(index=0, position_ms=10_000, context_ms=15_000)
        session = _make_session(
            peaks=[peak],
            video_offsets=[("CAM.mp4", "-00:00:05:00")],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        for clip in _get_clipitems(root, "video"):
            dur = int(clip.find("duration").text)
            in_f = int(clip.find("in").text)
            out_f = int(clip.find("out").text)
            assert dur == out_f - in_f
            assert dur > 0, "Clip duration should be positive"


class TestXMLSequenceDuration:
    """Sequence total duration must match sum of clip durations."""

    def test_total_frames_matches_clips(self, tmp_export_dir):
        peaks = [
            Peak(index=0, position_ms=30_000, context_ms=15_000),
            Peak(index=1, position_ms=80_000, context_ms=15_000),
        ]
        session = _make_session(
            peaks=peaks,
            video_offsets=[],
            videos=["/fake/CAM.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        seq_duration = int(root.find("sequence/duration").text)

        audio_clips = _get_clipitems(root, "audio")
        clip_sum = sum(int(c.find("duration").text) for c in audio_clips)
        assert seq_duration == clip_sum, \
            f"Sequence duration ({seq_duration}) != sum of clip durations ({clip_sum})"


class TestSyncOffsetRoundtrip:
    """Offset timecodes must survive format → parse roundtrip."""

    @pytest.mark.parametrize("offset_seconds,fps", [
        (0.0, 25),
        (1.5, 25),
        (-3.2, 25),
        (125.0, 25),
        (0.04, 25),      # exactly 1 frame
        (-0.04, 25),     # exactly -1 frame
    ])
    def test_format_parse_roundtrip(self, offset_seconds, fps):
        """format_offset → parse_timecode_to_ms should preserve the value to frame precision."""
        tc = format_offset(offset_seconds, fps)
        ms_back = parse_timecode_to_ms(tc, fps)

        # The original value quantized to frames
        frame_duration_ms = 1000 / fps
        expected_frames = int(offset_seconds * fps)
        expected_ms = int(expected_frames * 1000 / fps)

        assert ms_back == expected_ms, \
            f"Roundtrip failed: {offset_seconds}s → '{tc}' → {ms_back}ms (expected {expected_ms}ms)"


class TestXMLMultipleVideos:
    """Each video track must use its own offset."""

    def test_different_offsets_per_camera(self, tmp_export_dir):
        """Two cameras with different offsets must produce different in/out values."""
        peak = Peak(index=0, position_ms=60_000, context_ms=15_000)
        session = _make_session(
            peaks=[peak],
            video_offsets=[
                ("CAM_A.mp4", "00:00:02:00"),
                ("CAM_B.mp4", "00:00:05:00"),
            ],
            videos=["/fake/CAM_A.mp4", "/fake/CAM_B.mp4"],
            mics=["/fake/mix.wav"],
            export_dir=tmp_export_dir,
        )

        root = _export_and_parse(session)
        video_clips = _get_clipitems(root, "video")

        # 2 cameras x 1 peak = 2 clips
        assert len(video_clips) == 2

        in_a = int(video_clips[0].find("in").text)
        in_b = int(video_clips[1].find("in").text)
        assert in_a != in_b, \
            f"Different cameras should have different in values: CAM_A={in_a}, CAM_B={in_b}"
