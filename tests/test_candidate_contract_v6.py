"""Task 1 — v6-Vertrag: Identitaet, Herkunft, Anker, Migration, Roundtrip."""
import json

import pytest

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, CandidateDecision, ClipCandidateError,
    ORIGIN_MARKER, ORIGIN_AUTO, PROPOSED, SELECTED, marker_candidate_id)


def test_marker_candidate_id_format():
    assert marker_candidate_id(0) == "marker:0"
    assert marker_candidate_id(17) == "marker:17"


def test_kandidat_traegt_identitaet_herkunft_anker():
    c = ClipCandidate(candidate_id="marker:0", origin=ORIGIN_MARKER,
                      anchor_ms=60_000, peak_id=0,
                      boundary=ClipBoundary(45_000, 75_000))
    assert c.candidate_id == "marker:0"
    assert c.origin == ORIGIN_MARKER
    assert c.anchor_ms == 60_000
    assert c.peak_id == 0


def test_unbekannte_herkunft_wird_abgelehnt():
    with pytest.raises(ClipCandidateError):
        ClipCandidate(candidate_id="x", origin="pedal", anchor_ms=1,
                      peak_id=None, boundary=ClipBoundary(0, 10))


def test_v6_roundtrip_ist_exakt():
    c = ClipCandidate(candidate_id="auto:7f3", origin=ORIGIN_AUTO,
                      anchor_ms=90_000, peak_id=None,
                      boundary=ClipBoundary(80_000, 100_000),
                      status=SELECTED, reason="starker Einstieg", score=0.81)
    assert ClipCandidate.from_dict(json.loads(json.dumps(c.to_dict()))) == c


def test_v6_ohne_pflichtfelder_wird_abgelehnt():
    """Strikt (Carl): grosszuegige Defaults wuerden kaputte v6-Akten tarnen."""
    with pytest.raises((ClipCandidateError, KeyError)):
        ClipCandidate.from_dict({"boundary": {"start_ms": 0, "end_ms": 10},
                                 "status": PROPOSED})


def test_decision_haengt_an_candidate_id():
    d = CandidateDecision(candidate_id="auto:7f3", from_status=PROPOSED,
                          to_status=SELECTED, decided_at="2026-08-19T10:00:00")
    assert d.to_dict()["candidate_id"] == "auto:7f3"
    assert "peak_id" not in d.to_dict()


def test_alte_decision_mit_peak_id_wird_gelesen():
    """v1-v5-Decisions sind eine reine String-Abbildung — kein Peak noetig."""
    d = CandidateDecision.from_dict({
        "peak_id": 3, "from_status": PROPOSED, "to_status": SELECTED,
        "decided_at": "2026-06-01T10:00:00", "source": "manual"})
    assert d.candidate_id == "marker:3"


def test_v5_akte_migriert_anchor_aus_dem_peak(tmp_path):
    """Der Anker MUSS aus peak.position_ms kommen, nicht aus boundary.start_ms."""
    from tests.test_candidate_baseline_lock import make_session_with_peaks
    from core.project_archive import save_project_archive, load_project_archive

    session = make_session_with_peaks([60_000])
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))

    akte = root / ".peakcut" / "project.json"
    payload = json.loads(akte.read_text())
    payload["schema_version"] = 5
    payload["clip_candidates"] = [{
        "peak_id": 0, "boundary": {"start_ms": 45_000, "end_ms": 75_000},
        "status": "proposed", "transcript_excerpt": "", "reason": "", "score": None}]
    payload["peak_decisions"] = []
    payload.pop("candidate_decisions", None)
    akte.write_text(json.dumps(payload))

    loaded = load_project_archive(str(root), {})
    cand = loaded.clip_candidates[0]
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER
    assert cand.anchor_ms == 60_000
    assert cand.anchor_ms != cand.boundary.start_ms
