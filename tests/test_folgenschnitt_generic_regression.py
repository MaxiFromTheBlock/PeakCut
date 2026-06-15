import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import CameraAssignment, EditDecision
from core.folgenschnitt_multitrack_layout import UNUSED_CLIPS_DISABLE


def _tracks(root, media_type):
    return root.find("sequence/media").find(media_type).findall("track")


def test_hm_folgenschnitt_xml_structure_stays_stable_after_generic_refactor(tmp_export_dir):
    session = MagicMock()
    session.config = {"fps": 25}
    session.video_offsets = [
        ("CAM_MATZE.mp4", "00:00:00:00"),
        ("CAM_GUEST.mp4", "00:00:02:00"),
    ]
    session.folgenschnitt_edit_decisions = [
        EditDecision(0, 10_000, "/material/CAM_MATZE.mp4", "Matze", "first_speaker"),
        EditDecision(10_000, 13_000, "/material/CAM_GUEST.mp4", "Hartmut Rosa", "speaker_change"),
        EditDecision(13_000, 22_000, "/material/CAM_MATZE.mp4", "Matze", "speaker_change"),
    ]
    session.folgenschnitt_camera_assignments = [
        CameraAssignment("/material/CAM_MATZE.mp4", "weit", "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", "weit", "Hartmut Rosa"),
    ]
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_DISABLE

    project = MagicMock()
    project.export_dir = tmp_export_dir
    project.guest_name = "Hartmut Rosa"
    project.videos = ["/material/CAM_MATZE.mp4", "/material/CAM_GUEST.mp4"]
    project.mic_tracks = ["/material/MIC1.wav", "/material/MIC2.wav"]
    session.project = project

    with patch("core.folgenschnitt_exporter._probe_video_info", return_value=(1920, 1080)), \
         patch("core.folgenschnitt_exporter._probe_audio_info", return_value=(48000, 16, 1)):
        xml_path = FolgenschnittXMLExporter().export(session)

    root = ET.parse(xml_path).getroot()
    video_tracks = _tracks(root, "video")

    assert len(video_tracks) == 2
    matze_clips = video_tracks[0].findall("clipitem")
    guest_clips = video_tracks[1].findall("clipitem")

    assert [clip.find("name").text for clip in matze_clips] == [
        "Matze weit",
        "Matze weit",
        "Matze weit",
    ]
    assert [clip.find("name").text for clip in guest_clips] == [
        "Hartmut Rosa weit",
        "Hartmut Rosa weit",
        "Hartmut Rosa weit",
    ]
    assert [(clip.find("start").text, clip.find("end").text) for clip in matze_clips] == [
        ("0", "250"),
        ("250", "325"),
        ("325", "550"),
    ]
    assert [(clip.find("start").text, clip.find("end").text) for clip in guest_clips] == [
        ("0", "250"),
        ("250", "325"),
        ("325", "550"),
    ]
    assert [(clip.find("in").text, clip.find("out").text) for clip in matze_clips] == [
        ("0", "250"),
        ("250", "325"),
        ("325", "550"),
    ]
    assert [(clip.find("in").text, clip.find("out").text) for clip in guest_clips] == [
        ("50", "300"),
        ("300", "375"),
        ("375", "600"),
    ]
    assert matze_clips[0].find("enabled") is None
    assert matze_clips[1].find("enabled").text == "FALSE"
    assert matze_clips[2].find("enabled") is None
    assert guest_clips[0].find("enabled").text == "FALSE"
    assert guest_clips[1].find("enabled") is None
    assert guest_clips[2].find("enabled").text == "FALSE"
