"""Stufe-2 safety net: cases where the loosening layer MUST be identity.
These must stay green through every later Stage-2 task (adapter, split,
rotation, totale, snapping) — they protect the cutter-validated Stage-1
behaviour where there is nothing to loosen.
"""

from core.folgenschnitt_models import SHOT_WIDE, CameraAssignment, EditDecision
from core.folgenschnitt_loosening import (
    LooseningParams,
    apply_time_logic_loosening,
)


def test_only_wide_cameras_long_block_stays_identical():
    # Long single-speaker block, but the speaker has ONLY a wide camera ->
    # nothing to rotate to -> must come back exactly as Stage 1 produced it.
    decisions = [
        EditDecision(0, 600_000, "/m/CAM_MATZE.mp4", "Matze", "first_speaker"),
        EditDecision(600_000, 900_000, "/m/CAM_GUEST.mp4", "Gast", "speaker_change"),
    ]
    cameras = [
        CameraAssignment("/m/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/m/CAM_GUEST.mp4", SHOT_WIDE, "Gast"),
    ]
    params = LooseningParams(min_block_to_loosen_ms=120_000)

    result = apply_time_logic_loosening(decisions, cameras, [], params)

    assert result == decisions


def test_short_blocks_below_threshold_stay_identical():
    # Every block shorter than min_block_to_loosen_ms -> Stage 1 untouched.
    decisions = [
        EditDecision(0, 40_000, "/m/CAM_MATZE.mp4", "Matze", "first_speaker"),
        EditDecision(40_000, 70_000, "/m/CAM_GUEST.mp4", "Gast", "speaker_change"),
        EditDecision(70_000, 95_000, "/m/CAM_MATZE.mp4", "Matze", "speaker_change"),
    ]
    cameras = [
        CameraAssignment("/m/CAM_MATZE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/m/CAM_GUEST.mp4", SHOT_WIDE, "Gast"),
    ]
    params = LooseningParams(min_block_to_loosen_ms=120_000)

    result = apply_time_logic_loosening(decisions, cameras, [], params)

    assert result == decisions
