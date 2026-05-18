"""Roadmap #2 Task 2 — Bootstrap + Session-Lifecycle (Carl-Plan).

peak_id = Peak.index (akten-stabil, NICHT Listenposition); ignorierter
Peak -> Candidate discarded; ignore_peak() schreibt genau eine Decision
und ist idempotent; Bootstrap erzeugt keine Decision.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.clip_candidates import PROPOSED, DISCARDED  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _session(peaks):
    s = PeakCutSession(PeakCutProject(), dict(_CFG))
    s.load_analysis_results({"peaks": peaks, "video_offsets": []})
    return s


def _peak(index, pos, ignored=False):
    return {"index": index, "position_ms": pos, "context_ms": 15000,
            "ignored": ignored}


def test_bootstrap_one_candidate_per_peak_correct_status():
    s = _session([_peak(0, 60000), _peak(1, 120000, ignored=True)])
    assert len(s.clip_candidates) == 2
    assert s.clip_candidates[0].status == PROPOSED
    assert s.clip_candidates[1].status == DISCARDED  # ignoriert
    assert s.peak_decisions == []                      # kein Decision


def test_peak_id_is_peak_index_not_list_position():
    s = _session([_peak(10, 60000), _peak(42, 120000)])
    assert [c.peak_id for c in s.clip_candidates] == [10, 42]


def test_ignore_peak_writes_exactly_one_decision_idempotent():
    s = _session([_peak(10, 60000), _peak(42, 120000)])
    s.set_current_peak(1)            # Peak mit index 42 (Position 1)
    s.ignore_peak()
    assert s.peaks[1].ignored is True
    cand = next(c for c in s.clip_candidates if c.peak_id == 42)
    assert cand.status == DISCARDED
    assert len(s.peak_decisions) == 1
    d = s.peak_decisions[0]
    assert d.peak_id == 42 and d.to_status == DISCARDED
    assert d.source == "ignore_peak"
    # idempotent: nochmal ignorieren -> keine zweite Decision
    s.ignore_peak()
    assert len(s.peak_decisions) == 1


def test_ignore_couples_via_peak_index_not_position():
    # Position 0 hat Peak-index 10 -> Decision muss peak_id 10 tragen,
    # nicht 0 (current_peak-Position).
    s = _session([_peak(10, 60000), _peak(42, 120000)])
    s.set_current_peak(0)
    s.ignore_peak()
    assert s.peak_decisions[0].peak_id == 10
    assert next(c for c in s.clip_candidates
                if c.peak_id == 10).status == DISCARDED
    assert next(c for c in s.clip_candidates
                if c.peak_id == 42).status == PROPOSED
