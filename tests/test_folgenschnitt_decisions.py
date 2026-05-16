import pytest

from core.folgenschnitt_decisions import (
    DECISION_DEFAULTS,
    DecisionParams,
    build_edit_decisions,
    build_speaker_turns,
)
from core.folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_TOTAL,
    SHOT_WIDE,
    ActivityFrame,
    CameraAssignment,
    MicAssignment,
    SpeakerTurn,
)


def _mic_assignments():
    return [
        MicAssignment(0, "/material/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/material/MIC2.wav", "Hartmut Rosa", "mic_2"),
    ]


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


def test_decision_defaults_are_reactive_cutter_profile():
    assert DECISION_DEFAULTS == DecisionParams(
        min_speaker_turn_ms=1_000,
        min_shot_ms=1_000,
        merge_gap_ms=700,
        true_pause_ms=500,
        anticipation_ms=500,
    )


def test_build_speaker_turns_filters_short_interruptions():
    frames = []
    for start in range(0, 800, 100):
        frames.append(_frame(start, start + 200, "mic_2"))
    for start in range(5_000, 12_000, 100):
        frames.append(_frame(start, start + 200, "mic_1"))

    turns = build_speaker_turns(frames, _mic_assignments(), DECISION_DEFAULTS)

    assert len(turns) == 1
    assert turns[0].start_ms == 5_000
    assert turns[0].end_ms == 12_100
    assert turns[0].speaker == "Matze"
    assert turns[0].confidence == pytest.approx(0.9)
    assert turns[0].source == "speaker_activity"


def test_build_speaker_turns_merges_short_gaps_for_same_speaker():
    frames = []
    for start in range(0, 3_000, 100):
        frames.append(_frame(start, start + 200, "mic_1"))
    for start in range(3_600, 7_000, 100):
        frames.append(_frame(start, start + 200, "mic_1"))

    turns = build_speaker_turns(frames, _mic_assignments(), DECISION_DEFAULTS)

    assert len(turns) == 1
    assert turns[0].start_ms == 0
    assert turns[0].end_ms == 7_100


def test_build_edit_decisions_applies_anticipation_in_real_pause():
    turns = [
        SpeakerTurn(0, 10_000, "Matze", 0.9),
        SpeakerTurn(13_000, 21_000, "Hartmut Rosa", 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]

    decisions = build_edit_decisions(
        turns,
        cameras,
        sequence_end_ms=21_000,
        params=DECISION_DEFAULTS,
    )

    assert decisions[0].camera_path == "/material/CAM_MATZE.mp4"
    assert decisions[0].start_ms == 0
    assert decisions[0].end_ms == 12_500
    assert decisions[1].camera_path == "/material/CAM_GUEST.mp4"
    assert decisions[1].start_ms == 12_500
    assert decisions[1].end_ms == 21_000
    assert decisions[1].reason == "anticipation"


def test_build_edit_decisions_without_real_pause_cuts_at_turn_start():
    turns = [
        SpeakerTurn(0, 10_000, "Matze", 0.9),
        SpeakerTurn(10_400, 18_000, "Hartmut Rosa", 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]

    decisions = build_edit_decisions(
        turns,
        cameras,
        sequence_end_ms=18_000,
        params=DECISION_DEFAULTS,
    )

    assert decisions[0].end_ms == 10_400
    assert decisions[1].start_ms == 10_400
    assert decisions[1].reason == "speaker_change"


def test_build_edit_decisions_requires_wide_camera_for_speaker():
    turns = [SpeakerTurn(0, 8_000, "Hartmut Rosa", 0.9)]
    cameras = [CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze")]

    with pytest.raises(ValueError, match="No wide camera"):
        build_edit_decisions(turns, cameras, sequence_end_ms=8_000, params=DECISION_DEFAULTS)


def test_build_edit_decisions_ignores_close_and_total_for_stage_1():
    turns = [SpeakerTurn(0, 8_000, "Hartmut Rosa", 0.9)]
    cameras = [
        CameraAssignment("/material/CAM_CLOSE.mp4", SHOT_CLOSE, "Hartmut Rosa"),
        CameraAssignment("/material/TOTAL.mp4", SHOT_TOTAL),
        CameraAssignment("/material/CAM_WIDE.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]

    decisions = build_edit_decisions(turns, cameras, sequence_end_ms=8_000)

    assert decisions[0].camera_path == "/material/CAM_WIDE.mp4"


def test_build_edit_decisions_rejects_duplicate_wide_camera_for_person():
    turns = [SpeakerTurn(0, 8_000, "Matze", 0.9)]
    cameras = [
        CameraAssignment("/material/CAM_A.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_B.mp4", SHOT_WIDE, "Matze"),
    ]

    with pytest.raises(ValueError, match="Multiple wide cameras"):
        build_edit_decisions(turns, cameras, sequence_end_ms=8_000)


def test_build_edit_decisions_enforces_min_shot_and_gapless_timeline():
    turns = [
        SpeakerTurn(0, 6_000, "Matze", 0.9),
        SpeakerTurn(6_500, 12_000, "Hartmut Rosa", 0.9),
        SpeakerTurn(12_500, 18_000, "Matze", 0.9),
        SpeakerTurn(18_500, 19_600, "Hartmut Rosa", 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]

    decisions = build_edit_decisions(
        turns,
        cameras,
        sequence_end_ms=19_600,
        params=DECISION_DEFAULTS,
    )

    assert decisions[0].start_ms == 0
    assert decisions[-1].end_ms == 19_600
    for previous, current in zip(decisions, decisions[1:]):
        assert previous.end_ms == current.start_ms
    assert all(d.duration_ms >= DECISION_DEFAULTS.min_shot_ms for d in decisions)
    assert decisions[-1].camera_path == "/material/CAM_GUEST.mp4"
    assert decisions[-1].start_ms == 18_500
    assert decisions[-1].duration_ms == 1_100


def test_build_speaker_turns_keeps_one_second_interjection():
    frames = []
    for start in range(0, 900, 100):
        frames.append(_frame(start, start + 200, "mic_2"))

    turns = build_speaker_turns(frames, _mic_assignments(), DECISION_DEFAULTS)

    assert len(turns) == 1
    assert turns[0].start_ms == 0
    assert turns[0].end_ms == 1_000
    assert turns[0].speaker == "Hartmut Rosa"
    assert turns[0].confidence == pytest.approx(0.9)


def test_build_edit_decisions_keeps_one_second_guest_interjection_visible():
    turns = [
        SpeakerTurn(0, 10_000, "Matze", 0.9),
        SpeakerTurn(10_200, 11_200, "Hartmut Rosa", 0.9),
        SpeakerTurn(11_200, 18_000, "Matze", 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_GUEST.mp4", SHOT_WIDE, "Hartmut Rosa"),
    ]

    decisions = build_edit_decisions(
        turns,
        cameras,
        sequence_end_ms=18_000,
        params=DECISION_DEFAULTS,
    )

    guest_decisions = [decision for decision in decisions if decision.speaker == "Hartmut Rosa"]
    assert len(guest_decisions) == 1
    assert guest_decisions[0].start_ms == 10_200
    assert guest_decisions[0].end_ms == 11_200
    assert guest_decisions[0].duration_ms == 1_000
