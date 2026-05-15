from core.folgenschnitt_models import ActivityFrame, EditDecision, SpeakerId, SpeakerTurn
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
        levels_db={"matze": -20.0, "guest": -35.0},
        noise_floor_db={"matze": -55.0, "guest": -55.0},
        dominance_db=15.0,
        raw_speaker=SpeakerId.MATZE,
        smoothed_speaker=SpeakerId.MATZE,
        confidence=0.9,
    )
    turn = SpeakerTurn(
        start_ms=0,
        end_ms=6_000,
        speaker=SpeakerId.MATZE,
        confidence=0.9,
    )
    decision = EditDecision(
        start_ms=0,
        end_ms=6_000,
        camera_path="/material/CAM_A.mp4",
        speaker=SpeakerId.MATZE,
        reason="first_speaker",
    )

    session.load_analysis_results({
        "peaks": [],
        "video_offsets": [],
        "speaker_activity": [activity.to_dict()],
        "speaker_turns": [turn.to_dict()],
        "folgenschnitt_edit_decisions": [decision.to_dict()],
        "speaker_activity_csv": "/tmp/speaker_activity.csv",
    })

    assert session.speaker_activity == [activity]
    assert session.speaker_turns == [turn]
    assert session.folgenschnitt_edit_decisions == [decision]
    assert session.speaker_activity_csv == "/tmp/speaker_activity.csv"
