"""Folgenschnitt Stufe 2 / Track 1 — deterministic loosening layer.

Sits ON TOP of Stage 1 (`build_edit_decisions`, untouched). Long
single-speaker blocks get subdivided by rotating among that speaker's
cameras in large balanced blocks; a personless Totale serves as periodic
establishing shot + fallback. Cut points snap to the nearest real speech
pause (deterministic, no AI). The camera-decision strategy is pluggable so
a future AI director (Track 2) can be slotted in without rebuilding.

This module is session-agnostic: it only takes decisions, camera
assignments and pause ranges — all explicit, fully unit-testable.
"""

from dataclasses import dataclass
from typing import Protocol

from .folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_TOTAL,
    SHOT_WIDE,
    CameraAssignment,
    EditDecision,
)

_BASE_CAMERA_PRIORITY = (SHOT_WIDE, SHOT_CLOSE, SHOT_MEDIUM)


def build_stage1_base_camera_assignments(mic_assignments, camera_assignments):
    """Generality adapter: pick one base camera per speaking person
    (weit > nah_close > halbnah > totale-fallback) and expose it to the
    UNCHANGED Stage-1 decision function as a synthetic SHOT_WIDE
    assignment. Persons with no resolvable camera are omitted — the
    pipeline guardrail then skips Folgenschnitt cleanly.
    """
    totale = next(
        (c for c in camera_assignments if c.shot_type == SHOT_TOTAL), None
    )
    persons: list[str] = []
    seen: set[str] = set()
    for m in mic_assignments:
        if m.person and m.person not in seen:
            seen.add(m.person)
            persons.append(m.person)

    result: list[CameraAssignment] = []
    for person in persons:
        base_path = None
        for shot in _BASE_CAMERA_PRIORITY:
            cam = next(
                (
                    c
                    for c in camera_assignments
                    if c.person == person and c.shot_type == shot
                ),
                None,
            )
            if cam is not None:
                base_path = cam.path
                break
        if base_path is None and totale is not None:
            base_path = totale.path
        if base_path is not None:
            result.append(CameraAssignment(base_path, SHOT_WIDE, person))
    return result


@dataclass(frozen=True)
class LooseningParams:
    min_block_to_loosen_ms: int = 120_000
    first_block_ms: int = 110_000
    target_block_ms: int = 90_000
    densify_factor: float = 0.85
    min_block_ms: int = 50_000
    totale_interval_ms: int = 240_000
    totale_block_ms: int = 25_000
    rotation_order: tuple[str, ...] = (SHOT_WIDE, SHOT_CLOSE, SHOT_MEDIUM)
    snap_window_ms: int = 15_000


LOOSENING_DEFAULTS = LooseningParams()


@dataclass(frozen=True)
class PauseRange:
    start_ms: int
    end_ms: int


def split_block_segments(start_ms, end_ms, params):
    """Split one long single-speaker block into balanced segments:
    a long calm first segment (first_block_ms), then target_block_ms
    progressively densified (target * densify_factor**k), hard floor at
    min_block_ms, and a small final remainder is absorbed into the last
    segment (no sub-min tail). Gapless, covers [start, end] exactly.
    Blocks below min_block_to_loosen_ms are returned unsplit.
    """
    duration = end_ms - start_ms
    if duration < params.min_block_to_loosen_ms:
        return [(start_ms, end_ms)]

    segments = []
    pos = start_ms
    first_len = min(params.first_block_ms, end_ms - pos)
    segments.append((pos, pos + first_len))
    pos += first_len

    k = 0
    while pos < end_ms:
        seg_len = max(
            params.min_block_ms,
            round(params.target_block_ms * (params.densify_factor ** k)),
        )
        seg_end = pos + seg_len
        if seg_end >= end_ms or (end_ms - seg_end) < params.min_block_ms:
            segments.append((pos, end_ms))  # absorb small remainder
            break
        segments.append((pos, seg_end))
        pos = seg_end
        k += 1

    return segments


def _person_single_person_cameras(person, camera_assignments, rotation_order):
    """That person's single-person cameras, ordered by rotation_order."""
    ordered = []
    for shot in rotation_order:
        cam = next(
            (
                c
                for c in camera_assignments
                if c.person == person and c.shot_type == shot
            ),
            None,
        )
        if cam is not None:
            ordered.append(cam.path)
    return ordered


def _loosen_decision(decision, camera_assignments, params):
    """Subdivide one long single-speaker block by rotating through that
    speaker's single-person cameras. Returns [decision] unchanged when
    there is nothing to rotate or the block is too short."""
    ordered = _person_single_person_cameras(
        decision.speaker, camera_assignments, params.rotation_order
    )
    if len(ordered) < 2:
        return [decision]

    segments = split_block_segments(decision.start_ms, decision.end_ms, params)
    if len(segments) < 2:
        return [decision]

    try:
        start_i = ordered.index(decision.camera_path)
    except ValueError:
        start_i = 0

    out = []
    for i, (s, e) in enumerate(segments):
        out.append(EditDecision(
            s,
            e,
            ordered[(start_i + i) % len(ordered)],
            decision.speaker,
            decision.reason if i == 0 else "loosen_rotation",
        ))
    return out


class FolgenschnittLooseningStrategy(Protocol):
    """Pluggable camera-decision strategy. Track 1 = time logic;
    Track 2 (AI director) will implement the same interface later."""

    def apply(
        self,
        decisions: list[EditDecision],
        camera_assignments: list[CameraAssignment],
        pause_ranges: list[PauseRange],
        params: LooseningParams,
    ) -> list[EditDecision]:
        ...


class TimeLogicLooseningStrategy:
    """Deterministic time-logic loosening. No-op skeleton for now —
    real subdivision/rotation/totale/snapping added in later tasks."""

    def apply(
        self,
        decisions: list[EditDecision],
        camera_assignments: list[CameraAssignment],
        pause_ranges: list[PauseRange],
        params: LooseningParams,
    ) -> list[EditDecision]:
        out: list[EditDecision] = []
        for decision in decisions:
            out.extend(_loosen_decision(decision, camera_assignments, params))
        return out


def apply_time_logic_loosening(
    decisions: list[EditDecision],
    camera_assignments: list[CameraAssignment],
    pause_ranges: list[PauseRange] | None = None,
    params: LooseningParams = LOOSENING_DEFAULTS,
) -> list[EditDecision]:
    """Pipeline entry point. Thin wrapper over the time-logic strategy so
    a different strategy (Track 2) can be swapped here later."""
    return TimeLogicLooseningStrategy().apply(
        decisions,
        camera_assignments,
        list(pause_ranges or []),
        params,
    )
