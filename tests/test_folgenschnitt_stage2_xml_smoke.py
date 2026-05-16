"""Stufe-2 XML smoke: a mixed wide/close/totale decision list (as the
loosening layer produces) must export as a valid, gapless FCP7-XML.
The exporter itself is unchanged — this only guards the integration."""

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


def test_stage2_mixed_decisions_export_gapless_and_consistent(tmp_export_dir):
    session = MagicMock()
    session.config = {"fps": 25}
    session.video_offsets = [
        ("CAM_W.mp4", "00:00:00:00"),
        ("CAM_C.mp4", "00:00:00:00"),
        ("TOTALE.mov", "00:00:00:00"),
    ]
    session.folgenschnitt_edit_decisions = [
        EditDecision(0, 110_000, "/m/CAM_W.mp4", "Gast", "first_speaker"),
        EditDecision(110_000, 135_000, "/m/TOTALE.mov", "Gast", "loosen_total"),
        EditDecision(135_000, 225_000, "/m/CAM_C.mp4", "Gast", "loosen_rotation"),
        EditDecision(225_000, 360_000, "/m/CAM_W.mp4", "Gast", "loosen_rotation"),
    ]
    project = MagicMock()
    project.export_dir = tmp_export_dir
    project.guest_name = "Hartmut Rosa"
    project.videos = ["/m/CAM_W.mp4", "/m/CAM_C.mp4", "/m/TOTALE.mov"]
    project.mic_tracks = ["/m/MIC1.wav", "/m/MIC2.wav"]
    session.project = project

    with patch("core.folgenschnitt_exporter._probe_video_info",
               return_value=(1920, 1080)), \
         patch("core.folgenschnitt_exporter._probe_audio_info",
               return_value=(48000, 16, 1)):
        xml_path = FolgenschnittXMLExporter().export(session)

    clips = _clipitems(ET.parse(xml_path).getroot(), "video")

    assert [c.find("name").text for c in clips] == [
        "CAM_W", "TOTALE", "CAM_C", "CAM_W"
    ]
    starts = [int(c.find("start").text) for c in clips]
    ends = [int(c.find("end").text) for c in clips]
    assert starts[0] == 0
    for i in range(len(clips) - 1):
        assert ends[i] == starts[i + 1]                       # gapless
    for c in clips:                                            # duration consistent
        s, e = int(c.find("start").text), int(c.find("end").text)
        i_, o = int(c.find("in").text), int(c.find("out").text)
        assert o - i_ == e - s
