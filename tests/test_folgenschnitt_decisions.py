import pytest

from core.folgenschnitt_decisions import (
    DECISION_DEFAULTS,
    build_edit_decisions,
    build_speaker_turns,
)
from core.folgenschnitt_models import (
    ActivityFrame,
    CameraAssignment,
    CameraRole,
    SpeakerId,
    SpeakerTurn,
)


def _frame(start_ms, end_ms, speaker):
    return ActivityFrame(
        start_ms=start_ms,
        end_ms=end_ms,
        levels_db={"matze": -20.0, "guest": -35.0},
        noise_floor_db={"matze": -55.0, "guest": -55.0},
        dominance_db=12.0,
        raw_speaker=speaker,
        smoothed_speaker=speaker,
        confidence=0.9,
    )


def test_build_speaker_turns_filters_short_interruptions():
    frames = []
    for start in range(0, 4_800, 100):
        frames.append(_frame(start, start + 200, SpeakerId.GUEST))
    for start in range(5_000, 12_000, 100):
        frames.append(_frame(start, start + 200, SpeakerId.MATZE))

    turns = build_speaker_turns(frames, DECISION_DEFAULTS)

    assert turns == [
        SpeakerTurn(
            start_ms=5_000,
            end_ms=12_100,
            speaker=SpeakerId.MATZE,
            confidence=0.9,
            source="speaker_activity",
        )
    ]


def test_build_speaker_turns_merges_short_gaps_for_same_speaker():
    frames = []
    for start in range(0, 3_000, 100):
        frames.append(_frame(start, start + 200, SpeakerId.MATZE))
    for start in range(3_600, 7_000, 100):
        frames.append(_frame(start, start + 200, SpeakerId.MATZE))

    turns = build_speaker_turns(frames, DECISION_DEFAULTS)

    assert len(turns) == 1
    assert turns[0].start_ms == 0
    assert turns[0].end_ms == 7_100


def test_build_edit_decisions_applies_anticipation_in_real_pause():
    turns = [
        SpeakerTurn(0, 10_000, SpeakerId.MATZE, 0.9),
        SpeakerTurn(13_000, 21_000, SpeakerId.GUEST, 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", CameraRole.MATZE_WIDE),
        CameraAssignment("/material/CAM_GUEST.mp4", CameraRole.GUEST_WIDE),
    ]

    decisions = build_edit_decisions(
        turns,
        cameras,
        sequence_end_ms=21_000,
        params=DECISION_DEFAULTS,
    )

    assert decisions[0].camera_path == "/material/CAM_MATZE.mp4"
    assert decisions[0].start_ms == 0
    assert decisions[0].end_ms == 11_500
    assert decisions[1].camera_path == "/material/CAM_GUEST.mp4"
    assert decisions[1].start_ms == 11_500
    assert decisions[1].end_ms == 21_000
    assert decisions[1].reason == "anticipation"


def test_build_edit_decisions_without_real_pause_cuts_at_turn_start():
    turns = [
        SpeakerTurn(0, 10_000, SpeakerId.MATZE, 0.9),
        SpeakerTurn(10_400, 18_000, SpeakerId.GUEST, 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", CameraRole.MATZE_WIDE),
        CameraAssignment("/material/CAM_GUEST.mp4", CameraRole.GUEST_WIDE),
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
    turns = [SpeakerTurn(0, 8_000, SpeakerId.GUEST, 0.9)]
    cameras = [CameraAssignment("/material/CAM_MATZE.mp4", CameraRole.MATZE_WIDE)]

    with pytest.raises(ValueError, match="No wide camera"):
        build_edit_decisions(turns, cameras, sequence_end_ms=8_000, params=DECISION_DEFAULTS)


def test_build_edit_decisions_enforces_min_shot_and_gapless_timeline():
    turns = [
        SpeakerTurn(0, 6_000, SpeakerId.MATZE, 0.9),
        SpeakerTurn(6_500, 12_000, SpeakerId.GUEST, 0.9),
        SpeakerTurn(12_500, 18_000, SpeakerId.MATZE, 0.9),
        SpeakerTurn(18_500, 19_600, SpeakerId.GUEST, 0.9),
    ]
    cameras = [
        CameraAssignment("/material/CAM_MATZE.mp4", CameraRole.MATZE_WIDE),
        CameraAssignment("/material/CAM_GUEST.mp4", CameraRole.GUEST_WIDE),
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
    assert decisions[-1].camera_path == "/material/CAM_MATZE.mp4"
