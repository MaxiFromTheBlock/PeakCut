import json

import pytest

from core.folgenschnitt_models import (
    ActivityFrame,
    CameraAssignment,
    CameraRole,
    EditDecision,
    MicAssignment,
    SpeakerId,
    SpeakerTurn,
)


def test_activity_frame_json_roundtrip():
    frame = ActivityFrame(
        start_ms=100,
        end_ms=300,
        levels_db={"matze": -18.5, "guest": -31.2},
        noise_floor_db={"matze": -52.0, "guest": -54.0},
        dominance_db=12.7,
        raw_speaker=SpeakerId.MATZE,
        smoothed_speaker=SpeakerId.MATZE,
        confidence=0.92,
    )

    payload = json.loads(json.dumps(frame.to_dict()))
    restored = ActivityFrame.from_dict(payload)

    assert restored == frame
    assert restored.start_ms == 100
    assert restored.end_ms == 300
    assert restored.raw_speaker is SpeakerId.MATZE
    assert restored.smoothed_speaker is SpeakerId.MATZE


def test_speaker_turn_json_roundtrip():
    turn = SpeakerTurn(
        start_ms=1_000,
        end_ms=8_500,
        speaker=SpeakerId.GUEST,
        confidence=0.81,
        source="smoothed_activity",
    )

    payload = json.loads(json.dumps(turn.to_dict()))
    restored = SpeakerTurn.from_dict(payload)

    assert restored == turn
    assert restored.duration_ms == 7_500


def test_edit_decision_json_roundtrip():
    decision = EditDecision(
        start_ms=0,
        end_ms=12_000,
        camera_path="/material/CAM_A.mp4",
        speaker=SpeakerId.MATZE,
        reason="first_speaker",
    )

    payload = json.loads(json.dumps(decision.to_dict()))
    restored = EditDecision.from_dict(payload)

    assert restored == decision
    assert restored.duration_ms == 12_000


def test_role_assignments_json_roundtrip():
    mic = MicAssignment(
        track_index=0,
        path="/material/MIC1.wav",
        speaker=SpeakerId.MATZE,
    )
    camera = CameraAssignment(
        path="/material/CAM_A.mp4",
        role=CameraRole.MATZE_WIDE,
    )

    assert MicAssignment.from_dict(mic.to_dict()) == mic
    assert CameraAssignment.from_dict(camera.to_dict()) == camera


@pytest.mark.parametrize(
    "klass,payload",
    [
        (ActivityFrame, {"start_ms": 300, "end_ms": 100}),
        (SpeakerTurn, {"start_ms": 9_000, "end_ms": 8_000, "speaker": "matze"}),
        (EditDecision, {"start_ms": 5_000, "end_ms": 5_000, "camera_path": "/x.mov", "speaker": "guest"}),
    ],
)
def test_time_ranges_must_be_positive(klass, payload):
    with pytest.raises(ValueError):
        klass.from_dict(payload)
