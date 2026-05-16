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


def test_base_camera_prefers_wide_then_close_then_medium():
    from core.folgenschnitt_models import (
        SHOT_CLOSE, SHOT_MEDIUM, MicAssignment, CameraAssignment,
    )
    from core.folgenschnitt_loosening import build_stage1_base_camera_assignments

    mics = [
        MicAssignment(0, "/m/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/m/MIC2.wav", "Gast", "mic_2"),
    ]
    cams = [
        CameraAssignment("/m/MATZE_WIDE.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/m/MATZE_CLOSE.mp4", SHOT_CLOSE, "Matze"),
        CameraAssignment("/m/GAST_CLOSE.mp4", SHOT_CLOSE, "Gast"),
    ]

    base = build_stage1_base_camera_assignments(mics, cams)
    by_person = {c.person: c for c in base}

    assert by_person["Matze"].path == "/m/MATZE_WIDE.mp4"   # wide wins
    assert by_person["Gast"].path == "/m/GAST_CLOSE.mp4"     # close (no wide)
    assert all(c.shot_type == SHOT_WIDE for c in base)        # synthetic wide
    assert {c.person for c in base} == {"Matze", "Gast"}


def test_base_camera_totale_fallback_and_unresolvable_excluded():
    from core.folgenschnitt_models import (
        SHOT_TOTAL, MicAssignment, CameraAssignment,
    )
    from core.folgenschnitt_loosening import build_stage1_base_camera_assignments

    mics = [
        MicAssignment(0, "/m/MIC1.wav", "Anna", "mic_1"),
        MicAssignment(1, "/m/MIC2.wav", "Tom", "mic_2"),
    ]
    cams = [CameraAssignment("/m/TOTALE.mov", SHOT_TOTAL, None)]

    base = build_stage1_base_camera_assignments(mics, cams)

    # both persons fall back to the totale as their base (synthetic wide)
    assert {c.person for c in base} == {"Anna", "Tom"}
    assert all(c.path == "/m/TOTALE.mov" and c.shot_type == SHOT_WIDE for c in base)

    # no camera at all -> nobody resolvable
    assert build_stage1_base_camera_assignments(mics, []) == []


def test_split_block_short_block_not_split():
    from core.folgenschnitt_loosening import split_block_segments
    p = LooseningParams(min_block_to_loosen_ms=100)
    assert split_block_segments(0, 80, p) == [(0, 80)]


def test_split_block_segments_exact():
    from core.folgenschnitt_loosening import split_block_segments
    p = LooseningParams(
        min_block_to_loosen_ms=100,
        first_block_ms=50,
        target_block_ms=40,
        densify_factor=0.5,
        min_block_ms=20,
    )
    segs = split_block_segments(0, 160, p)
    assert segs == [(0, 50), (50, 90), (90, 110), (110, 130), (130, 160)]


def test_split_block_invariants():
    from core.folgenschnitt_loosening import split_block_segments
    p = LooseningParams(
        min_block_to_loosen_ms=100,
        first_block_ms=40,
        target_block_ms=30,
        densify_factor=0.5,
        min_block_ms=10,
    )
    segs = split_block_segments(1000, 1000 + 500, p)
    assert segs[0][0] == 1000 and segs[-1][1] == 1500          # exact coverage
    for a, b in zip(segs, segs[1:]):
        assert a[1] == b[0]                                     # gapless
    assert all(e - s >= p.min_block_ms for s, e in segs)        # hard floor
    assert segs[0][1] - segs[0][0] == 40                        # first_block
