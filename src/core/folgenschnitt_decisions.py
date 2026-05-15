from dataclasses import dataclass

from .folgenschnitt_models import (
    ActivityFrame,
    CameraAssignment,
    CameraRole,
    EditDecision,
    SpeakerId,
    SpeakerTurn,
)


@dataclass(frozen=True)
class DecisionParams:
    min_speaker_turn_ms: int = 5_000
    min_shot_ms: int = 2_000
    merge_gap_ms: int = 700
    true_pause_ms: int = 700
    anticipation_ms: int = 1_500


DECISION_DEFAULTS = DecisionParams()


def build_speaker_turns(
    activity_frames: list[ActivityFrame],
    params: DecisionParams = DECISION_DEFAULTS,
) -> list[SpeakerTurn]:
    turns: list[SpeakerTurn] = []
    current_speaker = SpeakerId.UNKNOWN
    current_start = None
    current_end = None
    confidences: list[float] = []

    for frame in activity_frames:
        speaker = frame.smoothed_speaker
        if speaker is SpeakerId.UNKNOWN:
            continue

        if current_start is None:
            current_speaker = speaker
            current_start = frame.start_ms
            current_end = frame.end_ms
            confidences = [frame.confidence]
            continue

        same_speaker = speaker is current_speaker
        short_gap = frame.start_ms - current_end <= params.merge_gap_ms
        if same_speaker and short_gap:
            current_end = max(current_end, frame.end_ms)
            confidences.append(frame.confidence)
            continue

        _append_turn_if_long_enough(
            turns,
            current_start,
            current_end,
            current_speaker,
            confidences,
            params,
        )
        current_speaker = speaker
        current_start = frame.start_ms
        current_end = frame.end_ms
        confidences = [frame.confidence]

    if current_start is not None:
        _append_turn_if_long_enough(
            turns,
            current_start,
            current_end,
            current_speaker,
            confidences,
            params,
        )

    return turns


def build_edit_decisions(
    speaker_turns: list[SpeakerTurn],
    camera_assignments: list[CameraAssignment],
    sequence_end_ms: int | None = None,
    params: DecisionParams = DECISION_DEFAULTS,
) -> list[EditDecision]:
    if not speaker_turns:
        return []

    wide_cameras = _speaker_wide_camera_map(camera_assignments)
    sequence_end = sequence_end_ms if sequence_end_ms is not None else speaker_turns[-1].end_ms

    decisions: list[EditDecision] = []
    previous_turn = None

    for idx, turn in enumerate(speaker_turns):
        camera_path = _camera_for_speaker(turn.speaker, wide_cameras)

        if idx == 0:
            decisions.append(EditDecision(
                start_ms=0,
                end_ms=sequence_end,
                camera_path=camera_path,
                speaker=turn.speaker,
                reason="first_speaker",
            ))
            previous_turn = turn
            continue

        if decisions[-1].speaker is turn.speaker:
            previous_turn = turn
            continue

        gap_ms = turn.start_ms - previous_turn.end_ms
        if gap_ms > params.true_pause_ms:
            cut_ms = max(previous_turn.end_ms, turn.start_ms - params.anticipation_ms)
            reason = "anticipation"
        else:
            cut_ms = turn.start_ms
            reason = "speaker_change"

        if cut_ms - decisions[-1].start_ms < params.min_shot_ms:
            cut_ms = decisions[-1].start_ms + params.min_shot_ms

        if cut_ms >= sequence_end:
            break

        decisions[-1] = EditDecision(
            start_ms=decisions[-1].start_ms,
            end_ms=cut_ms,
            camera_path=decisions[-1].camera_path,
            speaker=decisions[-1].speaker,
            reason=decisions[-1].reason,
        )
        decisions.append(EditDecision(
            start_ms=cut_ms,
            end_ms=sequence_end,
            camera_path=camera_path,
            speaker=turn.speaker,
            reason=reason,
        ))
        previous_turn = turn

    return _enforce_min_shot(decisions, params)


def _append_turn_if_long_enough(
    turns: list[SpeakerTurn],
    start_ms: int,
    end_ms: int,
    speaker: SpeakerId,
    confidences: list[float],
    params: DecisionParams,
) -> None:
    if end_ms - start_ms < params.min_speaker_turn_ms:
        return
    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    turns.append(SpeakerTurn(
        start_ms=start_ms,
        end_ms=end_ms,
        speaker=speaker,
        confidence=confidence,
        source="speaker_activity",
    ))


def _speaker_wide_camera_map(camera_assignments: list[CameraAssignment]) -> dict[SpeakerId, str]:
    mapping = {}
    for assignment in camera_assignments:
        if assignment.role is CameraRole.MATZE_WIDE:
            mapping[SpeakerId.MATZE] = assignment.path
        elif assignment.role is CameraRole.GUEST_WIDE:
            mapping[SpeakerId.GUEST] = assignment.path
    return mapping


def _camera_for_speaker(speaker: SpeakerId, wide_cameras: dict[SpeakerId, str]) -> str:
    try:
        return wide_cameras[speaker]
    except KeyError as exc:
        raise ValueError(f"No wide camera for speaker: {speaker.value}") from exc


def _enforce_min_shot(
    decisions: list[EditDecision],
    params: DecisionParams,
) -> list[EditDecision]:
    if len(decisions) <= 1:
        return decisions

    consolidated: list[EditDecision] = []
    for decision in decisions:
        if consolidated and decision.duration_ms < params.min_shot_ms:
            previous = consolidated[-1]
            consolidated[-1] = EditDecision(
                start_ms=previous.start_ms,
                end_ms=decision.end_ms,
                camera_path=previous.camera_path,
                speaker=previous.speaker,
                reason=previous.reason,
            )
        else:
            consolidated.append(decision)

    if len(consolidated) > 1 and consolidated[0].duration_ms < params.min_shot_ms:
        first = consolidated[0]
        second = consolidated[1]
        consolidated[0] = EditDecision(
            start_ms=first.start_ms,
            end_ms=second.end_ms,
            camera_path=second.camera_path,
            speaker=second.speaker,
            reason=second.reason,
        )
        del consolidated[1]

    return _merge_same_camera_neighbors(consolidated)


def _merge_same_camera_neighbors(decisions: list[EditDecision]) -> list[EditDecision]:
    merged: list[EditDecision] = []
    for decision in decisions:
        if merged and merged[-1].camera_path == decision.camera_path:
            previous = merged[-1]
            merged[-1] = EditDecision(
                start_ms=previous.start_ms,
                end_ms=decision.end_ms,
                camera_path=previous.camera_path,
                speaker=previous.speaker,
                reason=previous.reason,
            )
        else:
            merged.append(decision)
    return merged
