"""Slice "Marker + Vergleichbarkeit" — Task 1 (Carl-Plan).

Gemeinsame Nummern-/Span-/Marker-Helfer für die kompakten Clip-an-Clip-
XMLs (Keyboardstellen raw + Keyboardstellen smart). EINE Wahrheit für die
Stellennummer (peak.index -> Stelle 1..N über aktive Peaks) und die
kumulativen Record-Positionen, damit beide XMLs dieselben Marker-Nummern
tragen.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.xml_sequence_helpers import (  # noqa: E402
    build_peak_number_map, build_keyboard_spans, build_smart_spans,
    active_smart_candidates, marker_xml, sequence_markers_xml)
from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, PROPOSED, DISCARDED,
    ORIGIN_MARKER, marker_candidate_id)

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _peak(index, position_ms, ignored=False, context_ms=15000):
    p = Peak(index=index, position_ms=position_ms, context_ms=context_ms)
    p.ignored = ignored
    return p


def _mc(peak_id, position_ms, boundary, **kw):
    """Testhelfer: markergebundener v6-Kandidat (candidate_id/origin/anchor_ms
    aus peak_id + der echten Peak-Position — der Anker ist der Tritt)."""
    return ClipCandidate(candidate_id=marker_candidate_id(peak_id),
                         origin=ORIGIN_MARKER, anchor_ms=position_ms,
                         peak_id=peak_id, boundary=boundary, **kw)


def _session(peaks, cands=None):
    s = PeakCutSession(PeakCutProject(), dict(_CFG))
    s.peaks = peaks
    if cands is not None:
        s.clip_candidates = cands
    return s


# --- Nummernkarte / Keyboard-Spans ---------------------------------------

def test_peak_number_map_skips_ignored_like_keyboardstellen():
    # index 1 ignoriert -> nicht in der Karte; Rest 1..N in Reihenfolge.
    s = _session([_peak(0, 60000), _peak(1, 120000, ignored=True),
                  _peak(2, 180000), _peak(3, 240000)])
    assert build_peak_number_map(s) == {0: 1, 2: 2, 3: 3}


def test_keyboard_spans_record_positions_are_cumulative():
    s = _session([_peak(0, 60000), _peak(1, 120000)])
    spans = build_keyboard_spans(s)
    assert [sp.number for sp in spans] == [1, 2]
    assert spans[0].rec_start_f == 0
    for sp in spans:
        assert sp.rec_end_f - sp.rec_start_f == sp.source_out_f - sp.source_in_f
    assert spans[1].rec_start_f == spans[0].rec_end_f


# --- Smart-Spans: Nummer folgt Keyboard, nicht peak_id -------------------

def test_smart_span_number_follows_keyboard_not_peak_id():
    # Peak index 0 ignoriert -> Peak index 1 ist "Stelle 1".
    s = _session(
        [_peak(0, 60000, ignored=True), _peak(1, 120000)],
        cands=[_mc(1, 120000, ClipBoundary(110000, 130000),
                   status=PROPOSED, score=0.8)])
    spans = build_smart_spans(s)
    assert len(spans) == 1
    assert spans[0].number == 1          # nicht 2 (= candidate.peak_id)


def test_smart_spans_sorted_by_keyboard_number_not_list_order():
    s = _session(
        [_peak(0, 60000), _peak(1, 120000), _peak(2, 180000)],
        cands=[  # absichtlich verkehrte Reihenfolge
            _mc(2, 180000, ClipBoundary(170000, 190000),
               status=PROPOSED, score=0.7),
            _mc(0, 60000, ClipBoundary(50000, 70000),
               status=PROPOSED, score=0.9)])
    spans = build_smart_spans(s)
    assert [sp.number for sp in spans] == [1, 3]
    assert spans[0].rec_start_f == 0
    assert spans[1].rec_start_f == spans[0].rec_end_f


def test_smart_span_skips_candidate_without_active_peak():
    # Peak index 1 ignoriert -> Kandidat peak_id=1 hat keinen aktiven Peak.
    s = _session(
        [_peak(0, 60000), _peak(1, 120000, ignored=True)],
        cands=[
            _mc(0, 60000, ClipBoundary(50000, 70000),
               status=PROPOSED, score=0.9),
            _mc(1, 120000, ClipBoundary(110000, 130000),
               status=PROPOSED, score=0.8)])
    assert [sp.number for sp in build_smart_spans(s)] == [1]


def test_smart_spans_exclude_discarded_and_scoreless():
    s = _session(
        [_peak(0, 60000), _peak(1, 120000), _peak(2, 180000)],
        cands=[
            _mc(0, 60000, ClipBoundary(50000, 70000),
               status=DISCARDED, score=0.9),       # discarded raus
            _mc(1, 120000, ClipBoundary(110000, 130000),
               status=PROPOSED, score=None),       # bootstrap raus
            _mc(2, 180000, ClipBoundary(170000, 190000),
               status=PROPOSED, score=0.6)])       # bleibt
    assert [sp.number for sp in build_smart_spans(s)] == [3]


def test_active_smart_candidates_returns_number_and_candidate_sorted():
    # Peak 0 ignoriert -> Kandidat peak_id=0 fällt raus; Rest nach Stelle.
    s = _session(
        [_peak(0, 60000, ignored=True), _peak(1, 120000), _peak(2, 180000)],
        cands=[
            _mc(2, 180000, ClipBoundary(170000, 190000),
               status=PROPOSED, score=0.7),
            _mc(1, 120000, ClipBoundary(110000, 130000),
               status=PROPOSED, score=0.8),
            _mc(0, 60000, ClipBoundary(50000, 70000),
               status=PROPOSED, score=0.9)])
    result = active_smart_candidates(s)
    assert [num for num, _ in result] == [1, 2]        # nach Stelle sortiert
    assert [c.peak_id for _, c in result] == [1, 2]     # peak_id=0 ist raus


# --- Marker-XML ----------------------------------------------------------

def test_marker_xml_spans_clip_in_to_out():
    # Bereich-Marker (Max-Wunsch): so lang wie die Stelle -> Label lesbar.
    xml = marker_xml(4, 1000, 1750)
    assert "<marker>" in xml and "</marker>" in xml
    assert "<name>Stelle 4</name>" in xml
    assert "<in>1000</in>" in xml
    assert "<out>1750</out>" in xml       # out != in: spannt die ganze Stelle


def test_sequence_markers_span_whole_stelle():
    s = _session([_peak(0, 60000), _peak(1, 120000)])
    spans = build_keyboard_spans(s)
    xml = sequence_markers_xml(spans)
    assert xml.count("<marker>") == 2
    assert "<name>Stelle 1</name>" in xml and "<name>Stelle 2</name>" in xml
    # Marker spannen rec_start..rec_end (so lang wie die Stelle)
    assert f"<in>{spans[0].rec_start_f}</in>" in xml
    assert f"<out>{spans[0].rec_end_f}</out>" in xml
    assert f"<in>{spans[1].rec_start_f}</in>" in xml
    assert f"<out>{spans[1].rec_end_f}</out>" in xml
