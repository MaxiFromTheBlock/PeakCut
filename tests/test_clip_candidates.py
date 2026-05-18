"""Roadmap #2 Task 1 — ClipCandidate Core-Contracts (Carl-Plan).

Gate A STOPP: Datenmodell + Statusmaschine einfrieren, danach nicht
mehr dran drehen.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_candidates import (  # noqa: E402
    ClipBoundary, ClipCandidate, PeakDecision,
    PROPOSED, SELECTED, PRODUCED, PUBLISHED, DISCARDED,
    transition, ClipCandidateError,
)


def _cand(status=PROPOSED):
    return ClipCandidate(peak_id=42,
                         boundary=ClipBoundary(1000, 4000), status=status)


def test_boundary_validation():
    ClipBoundary(0, 1)  # ok
    try:
        ClipBoundary(5000, 5000)
        assert False, "end<=start muss abgelehnt werden"
    except ValueError:
        pass
    try:
        ClipBoundary(4000, 1000)
        assert False
    except ValueError:
        pass


def test_unknown_status_rejected():
    try:
        ClipCandidate(peak_id=1, boundary=ClipBoundary(0, 10),
                      status="bogus")
        assert False, "unbekannter Status muss abgelehnt werden"
    except ClipCandidateError:
        pass


def test_roundtrip_all_models():
    b = ClipBoundary(1000, 4000)
    assert ClipBoundary.from_dict(b.to_dict()) == b
    c = ClipCandidate(7, b, status=SELECTED, transcript_excerpt="hi",
                      reason="hook", score=0.8)
    assert ClipCandidate.from_dict(c.to_dict()) == c
    d = PeakDecision(7, PROPOSED, SELECTED, "2026-05-18T10:00:00",
                     source="manual")
    assert PeakDecision.from_dict(d.to_dict()) == d


def test_peak_decision_validates_contract():
    # legaler Roundtrip bleibt grün
    d = PeakDecision(7, PROPOSED, SELECTED, "2026-05-18T10:00:00")
    assert PeakDecision.from_dict(d.to_dict()) == d
    # unbekannter Status (auch via from_dict) -> Fehler
    for bad in ({"peak_id": 1, "from_status": "bogus", "to_status": SELECTED,
                 "decided_at": "t", "source": "manual"},):
        try:
            PeakDecision.from_dict(bad)
            assert False, "unbekannter Status muss abgelehnt werden"
        except ClipCandidateError:
            pass
    # illegaler Übergang im Log -> Fehler
    try:
        PeakDecision(1, PROPOSED, PRODUCED, "t")
        assert False, "proposed->produced muss abgelehnt werden"
    except ClipCandidateError:
        pass


def test_legal_transition_new_instance_and_decision():
    c = _cand(PROPOSED)
    new, dec = transition(c, SELECTED, now="2026-05-18T12:00:00")
    assert new is not c                       # neue frozen Instanz
    assert new.status == SELECTED and c.status == PROPOSED  # original unberührt
    assert dec == PeakDecision(42, PROPOSED, SELECTED,
                               "2026-05-18T12:00:00", source="manual")


def test_noop_same_status_no_decision():
    c = _cand(SELECTED)
    new, dec = transition(c, SELECTED, now="2026-05-18T12:00:00")
    assert new is c and dec is None


def test_illegal_transition_rejected():
    try:
        transition(_cand(PROPOSED), PRODUCED, now="x")  # nicht erlaubt
        assert False
    except ClipCandidateError:
        pass


def test_published_is_terminal_v1():
    for tgt in (PROPOSED, SELECTED, PRODUCED, DISCARDED):
        try:
            transition(_cand(PUBLISHED), tgt, now="x")
            assert False, f"published->{tgt} muss in v1 abgelehnt werden"
        except ClipCandidateError:
            pass


def test_allowed_transition_matrix():
    ok = {
        (PROPOSED, SELECTED), (PROPOSED, DISCARDED),
        (SELECTED, PROPOSED), (SELECTED, PRODUCED), (SELECTED, DISCARDED),
        (PRODUCED, SELECTED), (PRODUCED, PUBLISHED), (PRODUCED, DISCARDED),
        (DISCARDED, PROPOSED), (DISCARDED, SELECTED),
    }
    all_s = (PROPOSED, SELECTED, PRODUCED, PUBLISHED, DISCARDED)
    for a in all_s:
        for b in all_s:
            if a == b:
                continue
            c = _cand(a)
            if (a, b) in ok:
                new, dec = transition(c, b, now="t")
                assert new.status == b and dec is not None
            else:
                try:
                    transition(c, b, now="t")
                    assert False, f"{a}->{b} sollte illegal sein"
                except ClipCandidateError:
                    pass
