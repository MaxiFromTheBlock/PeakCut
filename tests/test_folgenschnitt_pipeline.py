import os
from unittest.mock import patch

from core.folgenschnitt_decisions import build_edit_decisions
from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_models import (
    SHOT_WIDE,
    ActivityFrame,
    CameraAssignment,
    MicAssignment,
    SpeakerTurn,
)
from core.folgenschnitt_pipeline import prepare_folgenschnitt_for_export
from core.project import PeakCutProject
from core.session import PeakCutSession


def _mic_assignments():
    return [
        MicAssignment(0, "/material/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/material/MIC2.wav", "Hartmut Rosa", "mic_2"),
    ]


def _camera_assignments():
    return [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]


def _activity_frames():
    frames = []
    for start in range(0, 5_000, 100):
        frames.append(_frame(start, start + 200, "mic_1"))
    for start in range(6_000, 12_000, 100):
        frames.append(_frame(start, start + 200, "mic_2"))
    return frames


def _frame(start_ms, end_ms, speaker_key):
    return ActivityFrame(
        start_ms=start_ms,
        end_ms=end_ms,
        levels_db={"mic_1": -20.0, "mic_2": -35.0},
        noise_floor_db={"mic_1": -55.0, "mic_2": -55.0},
        dominance_db=12.0,
        raw_speaker=speaker_key,
        smoothed_speaker=speaker_key,
        confidence=0.9,
    )


def _session(sample_config):
    project = PeakCutProject()
    project.set_files(
        keyboard="/material/keys.wav",
        mics=["/material/MIC1.wav", "/material/MIC2.wav"],
        videos=["/material/CAM_MATZE.mp4", "/material/CAM_GUEST.mp4"],
    )
    project.guest_name = "Hartmut Rosa"
    session = PeakCutSession(project, sample_config)
    session.speaker_activity = _activity_frames()
    session.speaker_activity_mic_assignments = _mic_assignments()
    session.folgenschnitt_mic_assignments = _mic_assignments()
    session.folgenschnitt_camera_assignments = _camera_assignments()
    return session


def test_prepare_folgenschnitt_for_export_builds_decisions_from_assignments(sample_config):
    session = _session(sample_config)

    reason = prepare_folgenschnitt_for_export(session)

    assert reason is None
    assert session.speaker_turns
    assert session.folgenschnitt_edit_decisions
    assert session.folgenschnitt_skip_reason is None


def test_prepare_folgenschnitt_for_export_skips_incomplete_assignment(sample_config):
    session = _session(sample_config)
    session.folgenschnitt_camera_assignments = []

    reason = prepare_folgenschnitt_for_export(session)

    assert reason == "Zuordnung unvollstaendig"
    assert session.folgenschnitt_edit_decisions == []
    assert session.speaker_turns == []


def test_applied_empty_assignment_does_not_fall_back_to_analysis_people(sample_config):
    # Deliberately empty mic assignment + flag set: must NOT silently reuse
    # the analysis-default mics, even though valid cameras + activity exist.
    session = _session(sample_config)
    session.folgenschnitt_assignment_applied = True
    session.folgenschnitt_mic_assignments = []
    # cameras stay valid (2 wide); only mics are deliberately blank

    reason = prepare_folgenschnitt_for_export(session)

    assert reason == "Zuordnung unvollstaendig"
    assert session.folgenschnitt_edit_decisions == []
    assert session.folgenschnitt_skip_reason == "Zuordnung unvollstaendig"


def test_prepare_folgenschnitt_for_export_skips_when_speaker_without_wide_camera(sample_config):
    session = _session(sample_config)
    session.folgenschnitt_camera_assignments = [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_X.mp4", SHOT_WIDE, "Jemand Anders"),
    ]

    reason = prepare_folgenschnitt_for_export(session)

    assert reason == "Zuordnung unvollstaendig"
    assert session.folgenschnitt_edit_decisions == []


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
        SpeakerTurn(0, 10_000, "Matze", 0.9),
        SpeakerTurn(13_000, 22_000, "Hartmut Rosa", 0.9),
    ]
    session.folgenschnitt_edit_decisions = build_edit_decisions(
        session.speaker_turns,
        _camera_assignments(),
        sequence_end_ms=22_000,
    )

    with patch("core.folgenschnitt_exporter._probe_video_info", return_value=(1920, 1080)), \
         patch("core.folgenschnitt_exporter._probe_audio_info", return_value=(48000, 16, 1)):
        xml_path = FolgenschnittXMLExporter().export(session)

    assert os.path.exists(xml_path)
    assert os.path.basename(xml_path) == "Folgenschnitt - Hartmut Rosa.xml"


def test_has_minimum_generalized_close_only_is_valid():
    from core.folgenschnitt_models import SHOT_CLOSE, MicAssignment, CameraAssignment
    from core.folgenschnitt_pipeline import has_minimum_folgenschnitt_assignment
    mics = [MicAssignment(0, "/m/MIC1.wav", "Anna", "mic_1"),
            MicAssignment(1, "/m/MIC2.wav", "Tom", "mic_2")]
    cams = [CameraAssignment("/m/A_CLOSE.mp4", SHOT_CLOSE, "Anna"),
            CameraAssignment("/m/T_CLOSE.mp4", SHOT_CLOSE, "Tom")]
    assert has_minimum_folgenschnitt_assignment(mics, cams) == (True, None)


def test_has_minimum_generalized_totale_only_two_mics_is_valid():
    from core.folgenschnitt_models import SHOT_TOTAL, MicAssignment, CameraAssignment
    from core.folgenschnitt_pipeline import has_minimum_folgenschnitt_assignment
    mics = [MicAssignment(0, "/m/MIC1.wav", "Anna", "mic_1"),
            MicAssignment(1, "/m/MIC2.wav", "Tom", "mic_2")]
    cams = [CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None)]
    assert has_minimum_folgenschnitt_assignment(mics, cams) == (True, None)


def test_has_minimum_skips_when_a_person_is_unresolvable():
    from core.folgenschnitt_models import SHOT_WIDE, MicAssignment, CameraAssignment
    from core.folgenschnitt_pipeline import has_minimum_folgenschnitt_assignment, SKIP_REASON
    mics = [MicAssignment(0, "/m/MIC1.wav", "Matze", "mic_1"),
            MicAssignment(1, "/m/MIC2.wav", "Gast", "mic_2")]
    cams = [CameraAssignment("/m/M_WIDE.mp4", SHOT_WIDE, "Matze")]  # Gast unresolvable, no totale
    assert has_minimum_folgenschnitt_assignment(mics, cams) == (False, SKIP_REASON)


def test_has_minimum_skips_with_no_cameras():
    from core.folgenschnitt_models import MicAssignment
    from core.folgenschnitt_pipeline import has_minimum_folgenschnitt_assignment, SKIP_REASON
    mics = [MicAssignment(0, "/m/MIC1.wav", "Matze", "mic_1"),
            MicAssignment(1, "/m/MIC2.wav", "Gast", "mic_2")]
    assert has_minimum_folgenschnitt_assignment(mics, []) == (False, SKIP_REASON)
