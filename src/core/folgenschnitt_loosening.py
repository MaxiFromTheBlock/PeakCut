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
    min_block_to_loosen_ms: int = 90_000
    first_block_ms: int = 70_000
    target_block_ms: int = 55_000
    densify_factor: float = 0.85
    min_block_ms: int = 35_000
    totale_interval_ms: int = 240_000
    totale_block_ms: int = 20_000
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


def build_pause_ranges(activity_frames):
    """Contiguous frames with no dominant speaker (smoothed_speaker is
    None) = a speech pause. Overlapping/adjacent None-frames are merged."""
    ranges = []
    cur_start = None
    cur_end = None
    for f in activity_frames:
        if f.smoothed_speaker is None:
            if cur_start is None:
                cur_start, cur_end = f.start_ms, f.end_ms
            else:
                cur_end = max(cur_end, f.end_ms)
        elif cur_start is not None:
            ranges.append(PauseRange(cur_start, cur_end))
            cur_start = None
    if cur_start is not None:
        ranges.append(PauseRange(cur_start, cur_end))
    return ranges


def _snap_into_window(desired_ms, valid_lo, valid_hi, pause_ranges, snap_window_ms):
    """Return the best pause midpoint near desired_ms that keeps the hard
    min_block floors (valid window), else the desired point clamped into
    the valid window. None means: no floor-safe position -> omit the cut.
    The floor always wins over a 'nice' pause.
    """
    if valid_lo > valid_hi:
        return None
    candidates = []
    for pr in pause_ranges:
        mid = (pr.start_ms + pr.end_ms) // 2
        if (
            desired_ms - snap_window_ms <= mid <= desired_ms + snap_window_ms
            and valid_lo <= mid <= valid_hi
        ):
            candidates.append(mid)
    if candidates:
        return min(candidates, key=lambda m: abs(m - desired_ms))
    return max(valid_lo, min(desired_ms, valid_hi))


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


def _loosen_decision(decision, camera_assignments, pause_ranges, params):
    """Subdivide one long single-speaker block by rotating through that
    speaker's single-person cameras. Cut points snap to the nearest
    speech pause within the snap window, but the hard min_block floor
    always wins (sequentially validated). Returns [decision] unchanged
    when there is nothing to rotate or the block is too short."""
    ordered = _person_single_person_cameras(
        decision.speaker, camera_assignments, params.rotation_order
    )
    if len(ordered) < 2:
        return [decision]

    raw = split_block_segments(decision.start_ms, decision.end_ms, params)
    if len(raw) < 2:
        return [decision]

    raw_cuts = [raw[i][1] for i in range(len(raw) - 1)]
    left = decision.start_ms
    right = decision.end_ms  # block end (Carl-allowed right_bound)
    final_cuts = []
    for desired in raw_cuts:
        snapped = _snap_into_window(
            desired,
            left + params.min_block_ms,
            right - params.min_block_ms,
            pause_ranges,
            params.snap_window_ms,
        )
        if snapped is None:
            continue  # no floor-safe spot -> drop this cut (segments merge)
        final_cuts.append(snapped)
        left = snapped

    bounds = [decision.start_ms] + final_cuts + [decision.end_ms]
    try:
        start_i = ordered.index(decision.camera_path)
    except ValueError:
        start_i = 0

    out = []
    for i in range(len(bounds) - 1):
        out.append(EditDecision(
            bounds[i],
            bounds[i + 1],
            ordered[(start_i + i) % len(ordered)],
            decision.speaker,
            decision.reason if i == 0 else "loosen_rotation",
        ))
    return out


def _totale_path(camera_assignments):
    cam = next(
        (c for c in camera_assignments if c.shot_type == SHOT_TOTAL), None
    )
    return cam.path if cam is not None else None


def _insert_totale(segments, block_start, block_end, totale_path,
                   pause_ranges, params):
    """Overlay periodic Establishing-Totale at block_start + n*interval.
    The totale start snaps to the nearest pause; the block stays exactly
    totale_block_ms. Splits the containing segment into pre / totale /
    post, keeping min_block_ms on both sides (floor wins). Skips the point
    if no floor-safe start exists or the segment is already the totale.
    Gapless / coverage preserved."""
    t = block_start + params.totale_interval_ms
    while t < block_end:
        idx = next(
            (
                i
                for i, d in enumerate(segments)
                if d.start_ms <= t < d.end_ms
            ),
            None,
        )
        if idx is None:
            t += params.totale_interval_ms
            continue
        seg = segments[idx]
        if seg.camera_path == totale_path:
            t += params.totale_interval_ms
            continue
        start = _snap_into_window(
            t,
            seg.start_ms + params.min_block_ms,
            seg.end_ms - params.totale_block_ms - params.min_block_ms,
            pause_ranges,
            params.snap_window_ms,
        )
        if start is not None:
            tot_end = start + params.totale_block_ms
            segments = (
                segments[:idx]
                + [
                    EditDecision(seg.start_ms, start, seg.camera_path,
                                 seg.speaker, seg.reason),
                    EditDecision(start, tot_end, totale_path,
                                 seg.speaker, "loosen_total"),
                    EditDecision(tot_end, seg.end_ms, seg.camera_path,
                                 seg.speaker, seg.reason),
                ]
                + segments[idx + 1:]
            )
        t += params.totale_interval_ms
    return segments


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
        totale_path = _totale_path(camera_assignments)
        out: list[EditDecision] = []
        for decision in decisions:
            segs = _loosen_decision(
                decision, camera_assignments, pause_ranges, params
            )
            block_duration = decision.end_ms - decision.start_ms
            if (
                totale_path is not None
                and block_duration >= params.min_block_to_loosen_ms
            ):
                segs = _insert_totale(
                    segs, decision.start_ms, decision.end_ms,
                    totale_path, pause_ranges, params,
                )
            out.extend(segs)
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
