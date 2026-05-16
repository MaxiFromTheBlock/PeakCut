import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import EditDecision


def _clipitems(root, media_type):
    section = root.find("sequence/media").find(media_type)
    clips = []
    for track in section.findall("track"):
        clips.extend(track.findall("clipitem"))
    return clips


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
    video_clips = _clipitems(root, "video")

    assert [clip.find("name").text for clip in video_clips] == [
        "CAM_MATZE",
        "CAM_GUEST",
        "CAM_MATZE",
    ]
    assert [(clip.find("start").text, clip.find("end").text) for clip in video_clips] == [
        ("0", "250"),
        ("250", "325"),
        ("325", "550"),
    ]
    assert [(clip.find("in").text, clip.find("out").text) for clip in video_clips] == [
        ("0", "250"),
        ("300", "375"),
        ("325", "550"),
    ]
