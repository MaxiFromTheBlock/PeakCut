"""#76 Task 2 — Playback Window Resolver (Carl-Plan 2026-06-15).

Qt-frei, deterministisch. Liefert pro Modus das Mix-Zeitfenster (start/end)
oder einen Grund, warum nicht abspielbar (Smart ohne gültigen Candidate).
Refinement ggü. Carl: Modus wird als Parameter übergeben (nicht aus
session.mode gelesen), damit Tasks 1-3 rein additiv bleiben.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.playback_windows import PlaybackWindow, build_playback_window  # noqa: E402
from core.peak import Peak  # noqa: E402
from core.clip_candidates import ClipCandidate, ClipBoundary, DISCARDED  # noqa: E402


def _peak(index=0, pos=60000, in_ms=50000, out_ms=80000, ignored=False):
    p = Peak(index=index, position_ms=pos)
    p.set_in_point(in_ms)
    p.set_out_point(out_ms)
    p.ignored = ignored
    return p


def _session(peaks, candidates=None, current=0):
    return types.SimpleNamespace(
        peaks=peaks, current_peak=current,
        clip_candidates=candidates or [],
        config={"preview_duration_ms": 1000})


def test_key_window():
    s = _session([_peak()])
    w = build_playback_window(s, "key")
    assert w.mode == "key" and w.start_ms == 60000 and w.end_ms == 61000
    assert not w.disabled


def test_speak_window_from_in_out():
    s = _session([_peak(in_ms=50000, out_ms=80000)])
    w = build_playback_window(s, "speak")
    assert w.start_ms == 50000 and w.end_ms == 80000 and not w.disabled


def test_smart_window_from_candidate():
    cand = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000), score=0.8)
    s = _session([_peak()], [cand])
    w = build_playback_window(s, "smart")
    assert w.start_ms == 40000 and w.end_ms == 90000 and not w.disabled


def test_smart_disabled_when_no_candidate():
    s = _session([_peak()], [])
    w = build_playback_window(s, "smart")
    assert w.mode == "smart" and w.disabled and w.disabled_reason


def test_smart_disabled_when_ignored():
    cand = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000), score=0.8)
    s = _session([_peak(ignored=True)], [cand])
    assert build_playback_window(s, "smart").disabled


def test_smart_disabled_when_discarded():
    cand = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000),
                         status=DISCARDED, score=0.8)
    s = _session([_peak()], [cand])
    assert build_playback_window(s, "smart").disabled


def test_smart_disabled_when_score_none_or_zero():
    c_none = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000), score=None)
    assert build_playback_window(_session([_peak()], [c_none]), "smart").disabled
    c_zero = ClipCandidate(peak_id=0, boundary=ClipBoundary(40000, 90000), score=0.0)
    assert build_playback_window(_session([_peak()], [c_zero]), "smart").disabled


def test_smart_mode_stays_selectable_even_when_disabled():
    w = build_playback_window(_session([_peak()], []), "smart")
    assert w.mode == "smart"   # Modus bleibt wählbar, nur Fenster disabled


def test_no_valid_peak_disabled():
    assert build_playback_window(_session([]), "key").disabled
    assert build_playback_window(_session([_peak()], current=5), "key").disabled


def test_mode_is_normalized():
    w = build_playback_window(_session([_peak()]), "keyboard")  # legacy -> key
    assert w.mode == "key" and w.start_ms == 60000


def test_explicit_peak_index():
    peaks = [_peak(index=0, pos=10000), _peak(index=1, pos=99000)]
    w = build_playback_window(_session(peaks), "key", peak_index=1)
    assert w.start_ms == 99000


def test_window_is_immutable():
    w = build_playback_window(_session([_peak()]), "key")
    try:
        w.start_ms = 0
        assert False, "PlaybackWindow sollte frozen sein"
    except Exception:
        pass
