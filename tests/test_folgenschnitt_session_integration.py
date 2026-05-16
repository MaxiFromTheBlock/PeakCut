from core.folgenschnitt_models import (
    ActivityFrame,
    EditDecision,
    MicAssignment,
    SpeakerTurn,
)
from core.project import PeakCutProject
from core.session import PeakCutSession


def test_load_analysis_results_loads_folgenschnitt_payload(tmp_export_dir, sample_config):
    project = PeakCutProject()
    project.export_dir = tmp_export_dir
    project.set_files(
        keyboard="/material/keys.wav",
        mics=["/material/MIC1.wav", "/material/MIC2.wav"],
        videos=["/material/CAM_A.mp4"],
    )
    session = PeakCutSession(project, sample_config)

    activity = ActivityFrame(
        start_ms=0,
        end_ms=200,
        levels_db={"mic_1": -20.0, "mic_2": -35.0},
        noise_floor_db={"mic_1": -55.0, "mic_2": -55.0},
        dominance_db=15.0,
        raw_speaker="mic_1",
        smoothed_speaker="mic_1",
        confidence=0.9,
    )
    turn = SpeakerTurn(
        start_ms=0,
        end_ms=6_000,
        speaker="Matze",
        confidence=0.9,
    )
    decision = EditDecision(
        start_ms=0,
        end_ms=6_000,
        camera_path="/material/CAM_A.mp4",
        speaker="Matze",
        reason="first_speaker",
    )
    mic = MicAssignment(
        track_index=0,
        path="/material/MIC1.wav",
        person="Matze",
        speaker_key="mic_1",
    )

    session.load_analysis_results({
        "peaks": [],
        "video_offsets": [],
        "speaker_activity": [activity.to_dict()],
        "speaker_turns": [turn.to_dict()],
        "folgenschnitt_edit_decisions": [decision.to_dict()],
        "speaker_activity_mic_assignments": [mic.to_dict()],
        "speaker_activity_csv": "/tmp/speaker_activity.csv",
    })

    assert session.speaker_activity == [activity]
    assert session.speaker_turns == [turn]
    assert session.folgenschnitt_edit_decisions == [decision]
    assert session.speaker_activity_mic_assignments == [mic]
    assert session.speaker_activity_csv == "/tmp/speaker_activity.csv"
