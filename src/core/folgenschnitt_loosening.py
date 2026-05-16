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
    SHOT_WIDE,
    CameraAssignment,
    EditDecision,
)


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
        return list(decisions)


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
