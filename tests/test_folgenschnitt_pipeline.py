import os
from unittest.mock import patch

from core.folgenschnitt_decisions import build_edit_decisions
from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import CameraAssignment, CameraRole, SpeakerId, SpeakerTurn
from core.project import PeakCutProject
from core.session import PeakCutSession


def test_folgenschnitt_pipeline_from_turns_to_xml(tmp_export_dir, sample_config):
    project = PeakCutProject()
    project.export_dir = tmp_export_dir
    project.set_files(
        keyboard="/material/keys.wav",
        mics=["/material/MIC1.wav", "/material/MIC2.wav"],
        videos=["/material/CAM_MATZE.mp4", "/material/CAM_GUEST.mp4"],
    )
    project.guest_name = "Hartmut Rosa"
    session = PeakCutSession(project, sample_config)
    session.video_offsets = [
        ("CAM_MATZE.mp4", "00:00:00:00"),
        ("CAM_GUEST.mp4", "00:00:02:00"),
    ]
    session.speaker_turns = [
        SpeakerTurn(0, 10_000, SpeakerId.MATZE, 0.9),
        SpeakerTurn(13_000, 22_000, SpeakerId.GUEST, 0.9),
    ]

    camera_assignments = [
        CameraAssignment("/material/CAM_MATZE.mp4", CameraRole.MATZE_WIDE),
        CameraAssignment("/material/CAM_GUEST.mp4", CameraRole.GUEST_WIDE),
    ]
    session.folgenschnitt_edit_decisions = build_edit_decisions(
        session.speaker_turns,
        camera_assignments,
        sequence_end_ms=22_000,
    )

    with patch("core.folgenschnitt_exporter._probe_video_info", return_value=(1920, 1080)), \
         patch("core.folgenschnitt_exporter._probe_audio_info", return_value=(48000, 16, 1)):
        xml_path = FolgenschnittXMLExporter().export(session)

    assert os.path.exists(xml_path)
    assert os.path.basename(xml_path) == "Folgenschnitt - Hartmut Rosa.xml"
