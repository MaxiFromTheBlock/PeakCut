import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import CameraAssignment, EditDecision
from core.folgenschnitt_multitrack_layout import (
    UNUSED_CLIPS_DISABLE,
    UNUSED_CLIPS_REMOVE,
)
from utils import ms_to_frames, parse_timecode_to_ms


def _make_session(export_dir):
    session = MagicMock()
    session.config = {"fps": 25}
    session.video_offsets = [
        ("CAM_A.mp4", "00:00:02:00"),
        ("CAM_B.mp4", "00:00:05:00"),
    ]
    session.folgenschnitt_edit_decisions = [
        EditDecision(
            start_ms=0,
            end_ms=60_000,
            camera_path="/material/CAM_A.mp4",
            speaker="Matze",
            reason="first_speaker",
        ),
        EditDecision(
            start_ms=60_000,
            end_ms=120_000,
            camera_path="/material/CAM_B.mp4",
            speaker="Hartmut Rosa",
            reason="speaker_change",
        ),
        EditDecision(
            start_ms=120_000,
            end_ms=180_000,
            camera_path="/material/CAM_A.mp4",
            speaker="Matze",
            reason="speaker_change",
        ),
    ]
    session.folgenschnitt_camera_assignments = [
        CameraAssignment(
            path="/material/CAM_A.mp4",
            shot_type="weit",
            person="Matze",
        ),
        CameraAssignment(
            path="/material/CAM_B.mp4",
            shot_type="weit",
            person="Hartmut Rosa",
        ),
    ]
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_DISABLE

    project = MagicMock()
    project.export_dir = export_dir
    project.guest_name = "Testgast"
    project.videos = ["/material/CAM_A.mp4", "/material/CAM_B.mp4"]
    project.mic_tracks = ["/material/MIC1.wav", "/material/MIC2.wav"]
    session.project = project
    return session


def _parse_export(session):
    with patch("core.folgenschnitt_exporter._probe_video_info", return_value=(1920, 1080)), \
         patch("core.folgenschnitt_exporter._probe_audio_info", return_value=(48000, 16, 1)):
        xml_path = FolgenschnittXMLExporter().export(session)
    assert xml_path.endswith("Folgenschnitt - Testgast.xml")
    return ET.parse(xml_path).getroot()


def _clipitems(root, media_type):
    section = root.find("sequence/media").find(media_type)
    clips = []
    for track in section.findall("track"):
        clips.extend(track.findall("clipitem"))
    return clips


def _tracks(root, media_type):
    return root.find("sequence/media").find(media_type).findall("track")


def _enabled_false_count(track):
    return sum(1 for c in track.findall("clipitem")
               if c.find("enabled") is not None
               and c.find("enabled").text == "FALSE")


def test_exports_disable_multitrack_video_timeline_from_edit_decisions(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_DISABLE

    root = _parse_export(session)
    video_tracks = _tracks(root, "video")

    assert root.find("sequence/name").text == "Folgenschnitt - Testgast"
    assert int(root.find("sequence/duration").text) == ms_to_frames(180_000, 25)
    assert len(video_tracks) == 2

    cam_a_clips = video_tracks[0].findall("clipitem")
    cam_b_clips = video_tracks[1].findall("clipitem")
    assert len(cam_a_clips) == 3
    assert len(cam_b_clips) == 3

    assert cam_a_clips[0].find("name").text == "Matze weit"
    assert cam_a_clips[0].find("start").text == "0"
    assert cam_a_clips[0].find("end").text == str(ms_to_frames(60_000, 25))
    assert cam_a_clips[0].find("enabled") is None

    assert cam_a_clips[1].find("enabled").text == "FALSE"
    assert cam_b_clips[0].find("enabled").text == "FALSE"
    assert cam_b_clips[1].find("enabled") is None


def test_exports_remove_multitrack_video_timeline_with_gaps(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_REMOVE

    root = _parse_export(session)
    video_tracks = _tracks(root, "video")

    assert len(video_tracks) == 2
    cam_a_clips = video_tracks[0].findall("clipitem")
    cam_b_clips = video_tracks[1].findall("clipitem")

    assert len(cam_a_clips) == 2
    assert len(cam_b_clips) == 1
    assert _enabled_false_count(video_tracks[0]) == 0
    assert _enabled_false_count(video_tracks[1]) == 0
    assert cam_a_clips[0].find("start").text == "0"
    assert cam_a_clips[1].find("start").text == str(ms_to_frames(120_000, 25))
    assert cam_b_clips[0].find("start").text == str(ms_to_frames(60_000, 25))


def test_exports_totale_as_bottom_fallback_track(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_REMOVE
    session.project.videos = [
        "/material/CAM_A.mp4",
        "/material/CAM_B.mp4",
        "/material/TOTALE.mp4",
    ]
    session.folgenschnitt_camera_assignments = [
        CameraAssignment("/material/CAM_A.mp4", "weit", "Matze"),
        CameraAssignment("/material/CAM_B.mp4", "weit", "Hartmut Rosa"),
        CameraAssignment("/material/TOTALE.mp4", "totale"),
    ]

    root = _parse_export(session)
    video_tracks = _tracks(root, "video")

    assert len(video_tracks) == 3
    totale_clips = video_tracks[0].findall("clipitem")
    assert [c.find("name").text for c in totale_clips] == [
        "Totale", "Totale", "Totale",
    ]
    assert [c.find("start").text for c in totale_clips] == [
        "0",
        str(ms_to_frames(60_000, 25)),
        str(ms_to_frames(120_000, 25)),
    ]
    assert _enabled_false_count(video_tracks[0]) == 0


def test_applies_per_camera_offsets_to_video_in_out(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_DISABLE

    root = _parse_export(session)
    video_tracks = _tracks(root, "video")
    cam_a_clips = video_tracks[0].findall("clipitem")
    cam_b_clips = video_tracks[1].findall("clipitem")

    offset_a = ms_to_frames(parse_timecode_to_ms("00:00:02:00", 25), 25)
    offset_b = ms_to_frames(parse_timecode_to_ms("00:00:05:00", 25), 25)

    assert int(cam_a_clips[0].find("in").text) == offset_a
    assert int(cam_a_clips[0].find("out").text) == ms_to_frames(60_000, 25) + offset_a
    assert int(cam_b_clips[1].find("in").text) == ms_to_frames(60_000, 25) + offset_b
    assert int(cam_b_clips[1].find("out").text) == ms_to_frames(120_000, 25) + offset_b


def test_audio_tracks_are_continuous_for_full_sequence(tmp_export_dir):
    session = _make_session(tmp_export_dir)

    root = _parse_export(session)
    audio_clips = _clipitems(root, "audio")

    assert len(audio_clips) == 2
    for clip in audio_clips:
        assert clip.find("start").text == "0"
        assert clip.find("end").text == str(ms_to_frames(180_000, 25))
        assert clip.find("in").text == "0"
        assert clip.find("out").text == str(ms_to_frames(180_000, 25))


def test_audio_uses_only_mix_when_mix_is_available(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.project.mic_tracks = [
        "/material/MIC1.wav",
        "/material/MIC2.wav",
        "/material/Podcast Mix.wav",
    ]

    root = _parse_export(session)
    audio_tracks = _tracks(root, "audio")
    audio_clips = _clipitems(root, "audio")

    assert len(audio_tracks) == 1
    assert len(audio_clips) == 1
    assert audio_clips[0].find("name").text == "Mix"
    assert audio_clips[0].find("start").text == "0"
    assert audio_clips[0].find("end").text == str(ms_to_frames(180_000, 25))
    assert "Podcast Mix.wav" in audio_clips[0].find("file/name").text


def test_audio_fallback_to_mics_emits_phasing_warning_when_mix_missing(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.project.mic_tracks = ["/material/MIC1.wav", "/material/MIC2.wav"]

    root = _parse_export(session)
    audio_tracks = _tracks(root, "audio")

    assert len(audio_tracks) == 2
    messages = [
        call.args[0]
        for call in session.status_update.emit.call_args_list
        if call.args
    ]
    assert any("Mic-Spuren statt Mix" in m for m in messages)


def test_empty_decisions_return_empty_string(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_edit_decisions = []

    assert FolgenschnittXMLExporter().export(session) == ""


def test_negative_video_offset_at_sequence_start_preserves_gapless_timeline_and_clip_duration(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.video_offsets = [("CAM_NEG.mp4", "-00:00:02:00")]
    session.project.videos = ["/material/CAM_NEG.mp4"]
    session.folgenschnitt_camera_assignments = [
        CameraAssignment("/material/CAM_NEG.mp4", "weit", "Matze")
    ]
    session.folgenschnitt_edit_decisions = [
        EditDecision(
            start_ms=0,
            end_ms=60_000,
            camera_path="/material/CAM_NEG.mp4",
            speaker="Matze",
            reason="first_speaker",
        )
    ]

    root = _parse_export(session)
    video_clips = _clipitems(root, "video")

    assert len(video_clips) == 1
    clip = video_clips[0]
    assert clip.find("start").text == "0"
    assert clip.find("end").text == str(ms_to_frames(60_000, 25))
    assert clip.find("duration").text == str(ms_to_frames(60_000, 25))
    assert clip.find("in").text == "0"
    assert clip.find("out").text == str(ms_to_frames(60_000, 25))
    assert int(clip.find("end").text) - int(clip.find("start").text) == int(clip.find("duration").text)
    assert int(clip.find("out").text) - int(clip.find("in").text) == int(clip.find("duration").text)
