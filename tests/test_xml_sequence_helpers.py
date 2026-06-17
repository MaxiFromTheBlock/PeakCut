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
    marker_xml, sequence_markers_xml)
from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, PROPOSED, DISCARDED)

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _peak(index, position_ms, ignored=False, context_ms=15000):
    p = Peak(index=index, position_ms=position_ms, context_ms=context_ms)
    p.ignored = ignored
    return p


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
        cands=[ClipCandidate(peak_id=1, boundary=ClipBoundary(110000, 130000),
                             status=PROPOSED, score=0.8)])
    spans = build_smart_spans(s)
    assert len(spans) == 1
    assert spans[0].number == 1          # nicht 2 (= candidate.peak_id)


def test_smart_spans_sorted_by_keyboard_number_not_list_order():
    s = _session(
        [_peak(0, 60000), _peak(1, 120000), _peak(2, 180000)],
        cands=[  # absichtlich verkehrte Reihenfolge
            ClipCandidate(peak_id=2, boundary=ClipBoundary(170000, 190000),
                          status=PROPOSED, score=0.7),
            ClipCandidate(peak_id=0, boundary=ClipBoundary(50000, 70000),
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
            ClipCandidate(peak_id=0, boundary=ClipBoundary(50000, 70000),
                          status=PROPOSED, score=0.9),
            ClipCandidate(peak_id=1, boundary=ClipBoundary(110000, 130000),
                          status=PROPOSED, score=0.8)])
    assert [sp.number for sp in build_smart_spans(s)] == [1]


def test_smart_spans_exclude_discarded_and_scoreless():
    s = _session(
        [_peak(0, 60000), _peak(1, 120000), _peak(2, 180000)],
        cands=[
            ClipCandidate(peak_id=0, boundary=ClipBoundary(50000, 70000),
                          status=DISCARDED, score=0.9),       # discarded raus
            ClipCandidate(peak_id=1, boundary=ClipBoundary(110000, 130000),
                          status=PROPOSED, score=None),       # bootstrap raus
            ClipCandidate(peak_id=2, boundary=ClipBoundary(170000, 190000),
                          status=PROPOSED, score=0.6)])       # bleibt
    assert [sp.number for sp in build_smart_spans(s)] == [3]


# --- Marker-XML ----------------------------------------------------------

def test_marker_xml_is_point_marker_named_stelle():
    xml = marker_xml(4, 1234)
    assert "<marker>" in xml and "</marker>" in xml
    assert "<name>Stelle 4</name>" in xml
    assert "<in>1234</in>" in xml
    assert "<out>1234</out>" in xml      # Punkt-Marker (in == out)


def test_sequence_markers_at_record_starts():
    s = _session([_peak(0, 60000), _peak(1, 120000)])
    spans = build_keyboard_spans(s)
    xml = sequence_markers_xml(spans)
    assert xml.count("<marker>") == 2
    assert "<name>Stelle 1</name>" in xml and "<name>Stelle 2</name>" in xml
    assert f"<in>{spans[0].rec_start_f}</in>" in xml
    assert f"<in>{spans[1].rec_start_f}</in>" in xml
