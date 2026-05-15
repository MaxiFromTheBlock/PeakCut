import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import EditDecision, SpeakerId
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
            speaker=SpeakerId.MATZE,
            reason="first_speaker",
        ),
        EditDecision(
            start_ms=60_000,
            end_ms=120_000,
            camera_path="/material/CAM_B.mp4",
            speaker=SpeakerId.GUEST,
            reason="speaker_change",
        ),
        EditDecision(
            start_ms=120_000,
            end_ms=180_000,
            camera_path="/material/CAM_A.mp4",
            speaker=SpeakerId.MATZE,
            reason="speaker_change",
        ),
    ]

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


def test_exports_flat_video_timeline_from_edit_decisions(tmp_export_dir):
    session = _make_session(tmp_export_dir)

    root = _parse_export(session)
    video_clips = _clipitems(root, "video")

    assert root.find("sequence/name").text == "Folgenschnitt - Testgast"
    assert int(root.find("sequence/duration").text) == ms_to_frames(180_000, 25)
    assert len(video_clips) == 3

    assert video_clips[0].find("name").text == "CAM_A"
    assert video_clips[0].find("start").text == "0"
    assert video_clips[0].find("end").text == str(ms_to_frames(60_000, 25))

    assert video_clips[1].find("name").text == "CAM_B"
    assert video_clips[1].find("start").text == str(ms_to_frames(60_000, 25))
    assert video_clips[1].find("end").text == str(ms_to_frames(120_000, 25))


def test_applies_per_camera_offsets_to_video_in_out(tmp_export_dir):
    session = _make_session(tmp_export_dir)

    root = _parse_export(session)
    video_clips = _clipitems(root, "video")

    offset_a = ms_to_frames(parse_timecode_to_ms("00:00:02:00", 25), 25)
    offset_b = ms_to_frames(parse_timecode_to_ms("00:00:05:00", 25), 25)

    assert int(video_clips[0].find("in").text) == offset_a
    assert int(video_clips[0].find("out").text) == ms_to_frames(60_000, 25) + offset_a
    assert int(video_clips[1].find("in").text) == ms_to_frames(60_000, 25) + offset_b
    assert int(video_clips[1].find("out").text) == ms_to_frames(120_000, 25) + offset_b


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


def test_empty_decisions_return_empty_string(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.folgenschnitt_edit_decisions = []

    assert FolgenschnittXMLExporter().export(session) == ""


def test_negative_video_offset_at_sequence_start_preserves_gapless_timeline_and_clip_duration(tmp_export_dir):
    session = _make_session(tmp_export_dir)
    session.video_offsets = [("CAM_NEG.mp4", "-00:00:02:00")]
    session.project.videos = ["/material/CAM_NEG.mp4"]
    session.folgenschnitt_edit_decisions = [
        EditDecision(
            start_ms=0,
            end_ms=60_000,
            camera_path="/material/CAM_NEG.mp4",
            speaker=SpeakerId.MATZE,
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
