"""Task 2 — Neu-Analyse darf Fremdquellen und Entscheidungen nicht vernichten.

GRENZE (Carl): Diese Tests laufen mit UNVERAENDERTEM Marker-Satz.
marker:<peak_id> ist bei eingefuegten/entfernten Markern ueber Analyselaeufe
hinweg nicht stabil — echte Reanalyse braucht zeitliches Event-Matching und
wird hier bewusst NICHT versprochen.
"""
import pytest

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, CandidateDecision, ClipCandidateError,
    ORIGIN_AUTO, ORIGIN_MARKER, PROPOSED, SELECTED)
from tests.test_candidate_baseline_lock import make_session_with_peaks

PEAKS = [60_000]
SAME_ANALYSIS = {
    "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
               "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False}],
    "video_offsets": [],
}
# Fix-Runde 1 (Pruefer-Befund 1b): zwei Peaks im Analyse-Ergebnis mit
# demselben index -> bauen beide denselben marker:<index>-Kandidaten.
DUPLICATE_INDEX_ANALYSIS = {
    "peaks": [
        {"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
         "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False},
        {"index": 0, "position_ms": 90_000, "in_point_ms": 75_000,
         "out_point_ms": 105_000, "context_ms": 15_000, "ignored": False},
    ],
    "video_offsets": [],
}


def _with_auto(session):
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:abc", origin=ORIGIN_AUTO, anchor_ms=90_000,
        peak_id=None, boundary=ClipBoundary(80_000, 100_000)))
    return session


def test_neu_analyse_erhaelt_auto_kandidaten():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.load_analysis_results(SAME_ANALYSIS)
    assert "auto:abc" in {c.candidate_id for c in session.clip_candidates}


def test_neu_analyse_erhaelt_das_entscheidungslog():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.peak_decisions.append(CandidateDecision(
        candidate_id="auto:abc", from_status=PROPOSED, to_status=SELECTED,
        decided_at="2026-08-19T10:00:00"))
    session.load_analysis_results(SAME_ANALYSIS)
    assert len(session.peak_decisions) == 1


def test_bearbeitungszustand_eines_marker_kandidaten_bleibt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates[0] = ClipCandidate(
        candidate_id="marker:0", origin=ORIGIN_MARKER, anchor_ms=60_000,
        peak_id=0, boundary=ClipBoundary(50_000, 70_000),
        status=SELECTED, reason="von Hand justiert", score=0.9)
    session.load_analysis_results(SAME_ANALYSIS)
    cand = next(c for c in session.clip_candidates if c.candidate_id == "marker:0")
    assert cand.status == SELECTED
    assert cand.reason == "von Hand justiert"
    assert cand.boundary.start_ms == 50_000


def test_fehlender_marker_kandidat_wird_ergaenzt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates = []
    session.load_analysis_results(SAME_ANALYSIS)
    assert [c.candidate_id for c in session.clip_candidates] == ["marker:0"]


def test_sortierung_ist_deterministisch_nach_anker():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.load_analysis_results(SAME_ANALYSIS)
    ankers = [c.anchor_ms for c in session.clip_candidates]
    assert ankers == sorted(ankers)


def test_doppelte_candidate_id_wird_abgelehnt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates.append(ClipCandidate(
        candidate_id="marker:0", origin=ORIGIN_AUTO, anchor_ms=99_000,
        peak_id=None, boundary=ClipBoundary(90_000, 110_000)))
    with pytest.raises(ClipCandidateError):
        session.load_analysis_results(SAME_ANALYSIS)


def test_fremdkandidat_mit_marker_id_kollidiert_beim_neubau():
    """Fix-Runde 1, Pruefer-Befund 1(a): ein Fremdkandidat traegt eine
    marker:<n>-ID, fuer die noch KEIN Marker-Kandidat existiert. Die
    Reconciliation baut dafuer einen neuen Marker-Kandidaten -> zwei
    Eintraege mit derselben candidate_id. Der alte Code prüfte
    Eindeutigkeit nur gegen die EINGANGS-Liste und übersah das."""
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates = [ClipCandidate(
        candidate_id="marker:0", origin=ORIGIN_AUTO, anchor_ms=10_000,
        peak_id=None, boundary=ClipBoundary(5_000, 9_000))]
    with pytest.raises(ClipCandidateError):
        session.load_analysis_results(SAME_ANALYSIS)


def test_zwei_peaks_mit_gleichem_index_kollidieren_beim_neubau():
    """Fix-Runde 1, Pruefer-Befund 1(b): zwei Peaks im Analyse-Ergebnis mit
    demselben index bauen beide denselben marker:<index>-Kandidaten ->
    Dublette, die erst WAEHREND der Reconciliation entsteht."""
    session = make_session_with_peaks(PEAKS)
    with pytest.raises(ClipCandidateError):
        session.load_analysis_results(DUPLICATE_INDEX_ANALYSIS)


def test_nach_fehler_bleiben_peaks_und_kandidaten_unveraendert():
    """Fix-Runde 1, Pruefer-Befund 2: load_analysis_results muss atomar
    sein. Fliegt die Reconciliation, darf die Session NICHT mit neuen
    Peaks + alten (dazu nicht mehr passenden) Kandidaten stehen bleiben —
    self.peaks und self.clip_candidates müssen exakt die Objekte von
    vor dem Aufruf bleiben (Identitätsprüfung, nicht nur Werte)."""
    session = make_session_with_peaks(PEAKS)
    peaks_before = session.peaks
    candidates_before = session.clip_candidates
    with pytest.raises(ClipCandidateError):
        session.load_analysis_results(DUPLICATE_INDEX_ANALYSIS)
    assert session.peaks is peaks_before
    assert session.clip_candidates is candidates_before
