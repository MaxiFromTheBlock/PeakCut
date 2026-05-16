import json

import pytest

from core.folgenschnitt_models import (
    SHOT_TOTAL,
    SHOT_WIDE,
    ActivityFrame,
    CameraAssignment,
    EditDecision,
    MicAssignment,
    SpeakerTurn,
)


def test_activity_frame_json_roundtrip_with_unknown_none():
    frame = ActivityFrame(
        start_ms=100,
        end_ms=300,
        levels_db={"mic_1": -18.5, "mic_2": -31.2},
        noise_floor_db={"mic_1": -52.0, "mic_2": -54.0},
        dominance_db=12.7,
        raw_speaker=None,
        smoothed_speaker=None,
        confidence=0.0,
    )

    payload = json.loads(json.dumps(frame.to_dict()))
    restored = ActivityFrame.from_dict(payload)

    assert restored == frame
    assert restored.raw_speaker is None
    assert restored.smoothed_speaker is None


def test_activity_frame_json_roundtrip_with_speaker_key():
    frame = ActivityFrame(
        start_ms=100,
        end_ms=300,
        levels_db={"mic_1": -18.5, "mic_2": -31.2},
        noise_floor_db={"mic_1": -52.0, "mic_2": -54.0},
        dominance_db=12.7,
        raw_speaker="mic_1",
        smoothed_speaker="mic_1",
        confidence=0.92,
    )

    payload = json.loads(json.dumps(frame.to_dict()))
    restored = ActivityFrame.from_dict(payload)

    assert restored == frame
    assert restored.raw_speaker == "mic_1"


def test_speaker_turn_json_roundtrip_with_person_string():
    turn = SpeakerTurn(
        start_ms=1_000,
        end_ms=8_500,
        speaker="Hartmut Rosa",
        confidence=0.81,
        source="smoothed_activity",
    )

    payload = json.loads(json.dumps(turn.to_dict()))
    restored = SpeakerTurn.from_dict(payload)

    assert restored == turn
    assert restored.speaker == "Hartmut Rosa"
    assert restored.duration_ms == 7_500


def test_edit_decision_json_roundtrip_with_person_string():
    decision = EditDecision(
        start_ms=0,
        end_ms=12_000,
        camera_path="/material/CAM_A.mp4",
        speaker="Matze",
        reason="first_speaker",
    )

    payload = json.loads(json.dumps(decision.to_dict()))
    restored = EditDecision.from_dict(payload)

    assert restored == decision
    assert restored.speaker == "Matze"
    assert restored.duration_ms == 12_000


def test_role_assignments_json_roundtrip_generic():
    mic = MicAssignment(
        track_index=0,
        path="/material/MIC1.wav",
        person="Matze",
        speaker_key="mic_1",
    )
    camera = CameraAssignment(
        path="/material/CAM_A.mp4",
        shot_type=SHOT_WIDE,
        person="Matze",
    )

    assert MicAssignment.from_dict(mic.to_dict()) == mic
    assert CameraAssignment.from_dict(camera.to_dict()) == camera


def test_mic_assignment_defaults_speaker_key_from_track_index():
    mic = MicAssignment(track_index=1, path="/material/MIC2.wav", person="Hartmut Rosa")

    assert mic.speaker_key == "mic_2"


def test_personless_camera_normalizes_person_to_none():
    camera = CameraAssignment(path="/material/TOTAL.mp4", shot_type=SHOT_TOTAL, person="Matze")

    assert camera.person is None


def test_wide_camera_requires_person():
    with pytest.raises(ValueError, match="person"):
        CameraAssignment(path="/material/CAM_A.mp4", shot_type=SHOT_WIDE, person=None)


@pytest.mark.parametrize(
    "klass,payload",
    [
        (ActivityFrame, {"start_ms": 300, "end_ms": 100}),
        (SpeakerTurn, {"start_ms": 9_000, "end_ms": 8_000, "speaker": "Matze"}),
        (EditDecision, {"start_ms": 5_000, "end_ms": 5_000, "camera_path": "/x.mov", "speaker": "Gast"}),
    ],
)
def test_time_ranges_must_be_positive(klass, payload):
    with pytest.raises(ValueError):
        klass.from_dict(payload)
