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


def _rot_params():
    return LooseningParams(
        min_block_to_loosen_ms=100, first_block_ms=50,
        target_block_ms=40, densify_factor=0.5, min_block_ms=20,
    )


def test_rotation_wide_close_alternates_big_blocks():
    from core.folgenschnitt_models import SHOT_CLOSE, CameraAssignment, EditDecision
    decisions = [EditDecision(0, 160, "/m/G_WIDE.mp4", "Gast", "first_speaker")]
    cams = [
        CameraAssignment("/m/G_WIDE.mp4", SHOT_WIDE, "Gast"),
        CameraAssignment("/m/G_CLOSE.mp4", SHOT_CLOSE, "Gast"),
    ]
    out = apply_time_logic_loosening(decisions, cams, [], _rot_params())
    assert [d.camera_path for d in out] == [
        "/m/G_WIDE.mp4", "/m/G_CLOSE.mp4", "/m/G_WIDE.mp4",
        "/m/G_CLOSE.mp4", "/m/G_WIDE.mp4",
    ]
    assert [(d.start_ms, d.end_ms) for d in out] == [
        (0, 50), (50, 90), (90, 110), (110, 130), (130, 160)
    ]
    assert out[0].reason == "first_speaker"
    assert all(d.reason == "loosen_rotation" for d in out[1:])
    assert all(d.speaker == "Gast" for d in out)


def test_rotation_wide_close_medium_round_robin():
    from core.folgenschnitt_models import (
        SHOT_CLOSE, SHOT_MEDIUM, CameraAssignment, EditDecision,
    )
    decisions = [EditDecision(0, 160, "/m/W.mp4", "Gast", "first_speaker")]
    cams = [
        CameraAssignment("/m/W.mp4", SHOT_WIDE, "Gast"),
        CameraAssignment("/m/C.mp4", SHOT_CLOSE, "Gast"),
        CameraAssignment("/m/H.mp4", SHOT_MEDIUM, "Gast"),
    ]
    out = apply_time_logic_loosening(decisions, cams, [], _rot_params())
    assert [d.camera_path for d in out] == [
        "/m/W.mp4", "/m/C.mp4", "/m/H.mp4", "/m/W.mp4", "/m/C.mp4"
    ]


def test_rotation_single_camera_unchanged():
    from core.folgenschnitt_models import CameraAssignment, EditDecision
    decisions = [EditDecision(0, 160, "/m/W.mp4", "Gast", "first_speaker")]
    cams = [CameraAssignment("/m/W.mp4", SHOT_WIDE, "Gast")]
    out = apply_time_logic_loosening(decisions, cams, [], _rot_params())
    assert out == decisions


def _tot_params():
    return LooseningParams(
        min_block_to_loosen_ms=100, first_block_ms=200, target_block_ms=200,
        densify_factor=1.0, min_block_ms=20,
        totale_interval_ms=100, totale_block_ms=30,
    )


def test_totale_periodic_establishing_blocks():
    from core.folgenschnitt_models import (
        SHOT_CLOSE, SHOT_TOTAL, CameraAssignment, EditDecision,
    )
    decisions = [EditDecision(0, 400, "/m/W.mp4", "Gast", "first_speaker")]
    cams = [
        CameraAssignment("/m/W.mp4", SHOT_WIDE, "Gast"),
        CameraAssignment("/m/C.mp4", SHOT_CLOSE, "Gast"),
        CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None),
    ]
    out = apply_time_logic_loosening(decisions, cams, [], _tot_params())

    tot = [d for d in out if d.camera_path == "/m/TOT.mov"]
    # No pauses -> totale start clamped into the floor-safe window
    # (Carl-final: clamp, not skip). t=100->100, t=200->220, t=300->300.
    assert [(d.start_ms, d.end_ms) for d in tot] == [
        (100, 130), (220, 250), (300, 330)
    ]
    assert all(d.reason == "loosen_total" for d in tot)
    assert all(d.speaker == "Gast" for d in tot)
    assert all(d.end_ms - d.start_ms == 30 for d in tot)        # fixed length
    # gapless + exact coverage; non-totale segments keep the hard floor
    assert out[0].start_ms == 0 and out[-1].end_ms == 400
    for a, b in zip(out, out[1:]):
        assert a.end_ms == b.start_ms
    assert all(
        d.end_ms - d.start_ms >= 20 or d.camera_path == "/m/TOT.mov"
        for d in out
    )


def test_totale_skipped_for_short_block():
    from core.folgenschnitt_models import SHOT_TOTAL, CameraAssignment, EditDecision
    decisions = [EditDecision(0, 80, "/m/W.mp4", "Gast", "first_speaker")]
    cams = [
        CameraAssignment("/m/W.mp4", SHOT_WIDE, "Gast"),
        CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None),
    ]
    out = apply_time_logic_loosening(decisions, cams, [], _tot_params())
    assert out == decisions  # short block -> no loosening, no totale


def test_pure_totale_stays_single_clip():
    from core.folgenschnitt_models import SHOT_TOTAL, CameraAssignment, EditDecision
    # only-totale: Stage 1 already produced one totale clip; no churn.
    decisions = [EditDecision(0, 600, "/m/TOT.mov", "Gast", "first_speaker")]
    cams = [CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None)]
    out = apply_time_logic_loosening(decisions, cams, [], _tot_params())
    assert out == decisions


def test_build_pause_ranges_merges_none_frames():
    from core.folgenschnitt_models import ActivityFrame
    from core.folgenschnitt_loosening import build_pause_ranges, PauseRange
    frames = [
        ActivityFrame(0, 200, {}, {}, 0.0, None, None, 0.0),
        ActivityFrame(100, 300, {}, {}, 0.0, None, None, 0.0),
        ActivityFrame(200, 400, {}, {}, 5.0, "mic_1", "mic_1", 0.9),
        ActivityFrame(300, 500, {}, {}, 0.0, None, None, 0.0),
    ]
    assert build_pause_ranges(frames) == [PauseRange(0, 300), PauseRange(300, 500)]


def _snap_params(**kw):
    base = dict(min_block_to_loosen_ms=100, first_block_ms=30,
                target_block_ms=30, densify_factor=1.0, min_block_ms=20,
                snap_window_ms=30)
    base.update(kw)
    return LooseningParams(**base)


def _wide_close(person="Gast"):
    from core.folgenschnitt_models import SHOT_CLOSE, CameraAssignment
    return [
        CameraAssignment("/m/W.mp4", SHOT_WIDE, person),
        CameraAssignment("/m/C.mp4", SHOT_CLOSE, person),
    ]


def test_rotation_cut_snaps_to_nearest_pause():
    from core.folgenschnitt_models import EditDecision
    from core.folgenschnitt_loosening import PauseRange
    d = [EditDecision(0, 200, "/m/W.mp4", "Gast", "first_speaker")]
    out = apply_time_logic_loosening(
        d, _wide_close(), [PauseRange(56, 60)], _snap_params()
    )
    # first internal cut (raw 30) snaps right to pause midpoint 58
    assert out[0].end_ms == 58


def test_rotation_cut_does_not_snap_below_min_block():
    from core.folgenschnitt_models import EditDecision
    from core.folgenschnitt_loosening import PauseRange
    d = [EditDecision(0, 200, "/m/W.mp4", "Gast", "first_speaker")]
    # pause midpoint 5 is inside snap window of raw cut 30 (±30 -> [0,60])
    # but below valid_lo (0+min_block=20) -> floor wins, no snap
    out = apply_time_logic_loosening(
        d, _wide_close(), [PauseRange(3, 7)], _snap_params()
    )
    assert out[0].end_ms == 30  # stayed at clamped desired


def test_rotation_cut_falls_back_without_pause_in_window():
    from core.folgenschnitt_models import EditDecision
    from core.folgenschnitt_loosening import PauseRange
    d = [EditDecision(0, 200, "/m/W.mp4", "Gast", "first_speaker")]
    out = apply_time_logic_loosening(
        d, _wide_close(), [PauseRange(900, 950)], _snap_params()
    )
    assert out[0].end_ms == 30  # no pause near -> desired kept


def test_rotation_fallback_clamped_after_previous_right_snap():
    from core.folgenschnitt_models import EditDecision
    from core.folgenschnitt_loosening import PauseRange
    d = [EditDecision(0, 200, "/m/W.mp4", "Gast", "first_speaker")]
    out = apply_time_logic_loosening(
        d, _wide_close(), [PauseRange(56, 60)], _snap_params()
    )
    cuts = [s.end_ms for s in out[:-1]]
    assert cuts[0] == 58                       # snapped right
    assert cuts[1] == 78                       # == left(58) + min_block(20)
    bounds = [0] + cuts + [200]
    assert all(b - a >= 20 for a, b in zip(bounds, bounds[1:]))  # invariant


def test_totale_start_snaps_to_pause_keeps_min_blocks():
    from core.folgenschnitt_models import SHOT_TOTAL, CameraAssignment, EditDecision
    from core.folgenschnitt_loosening import PauseRange
    d = [EditDecision(0, 400, "/m/W.mp4", "Gast", "first_speaker")]
    cams = _wide_close() + [CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None)]
    p = _snap_params(min_block_to_loosen_ms=100, first_block_ms=400,
                      target_block_ms=400, min_block_ms=20,
                      totale_interval_ms=100, totale_block_ms=30, snap_window_ms=25)
    out = apply_time_logic_loosening(d, cams, [PauseRange(108, 116)], p)
    tot = [s for s in out if s.camera_path == "/m/TOT.mov"]
    assert tot and tot[0].start_ms == 112              # snapped to pause mid
    assert tot[0].end_ms == 112 + 30
    assert all(s.end_ms - s.start_ms >= 20 or s.camera_path == "/m/TOT.mov"
               for s in out)
    for a, b in zip(out, out[1:]):
        assert a.end_ms == b.start_ms                   # gapless


def test_totale_omitted_when_no_room():
    from core.folgenschnitt_models import SHOT_TOTAL, CameraAssignment, EditDecision
    d = [EditDecision(0, 130, "/m/W.mp4", "Gast", "first_speaker")]
    cams = _wide_close() + [CameraAssignment("/m/TOT.mov", SHOT_TOTAL, None)]
    p = _snap_params(min_block_to_loosen_ms=100, first_block_ms=130,
                      target_block_ms=130, min_block_ms=55,
                      totale_interval_ms=60, totale_block_ms=30, snap_window_ms=10)
    out = apply_time_logic_loosening(d, cams, [], p)
    assert all(s.camera_path != "/m/TOT.mov" for s in out)  # no room -> omitted
