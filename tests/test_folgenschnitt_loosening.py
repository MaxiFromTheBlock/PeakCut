from core.folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_WIDE,
    EditDecision,
)
from core.folgenschnitt_loosening import (
    LOOSENING_DEFAULTS,
    LooseningParams,
    apply_time_logic_loosening,
)


def _decisions():
    return [
        EditDecision(0, 30_000, "/m/CAM_A.mp4", "Matze", "first_speaker"),
        EditDecision(30_000, 50_000, "/m/CAM_B.mp4", "Gast", "speaker_change"),
    ]


def test_loosening_defaults_are_v1():
    assert LOOSENING_DEFAULTS == LooseningParams(
        min_block_to_loosen_ms=120_000,
        first_block_ms=110_000,
        target_block_ms=90_000,
        densify_factor=0.85,
        min_block_ms=50_000,
        totale_interval_ms=240_000,
        totale_block_ms=25_000,
        rotation_order=(SHOT_WIDE, SHOT_CLOSE, SHOT_MEDIUM),
        snap_window_ms=15_000,
    )


def test_noop_returns_decisions_unchanged_and_gapless():
    decisions = _decisions()
    params = LooseningParams(min_block_to_loosen_ms=10_000)

    result = apply_time_logic_loosening(
        decisions, [], pause_ranges=[], params=params
    )

    # No-op: identical content
    assert result == decisions
    # Gapless + same total coverage
    assert result[0].start_ms == 0
    assert result[-1].end_ms == decisions[-1].end_ms
    for prev, cur in zip(result, result[1:]):
        assert prev.end_ms == cur.start_ms
