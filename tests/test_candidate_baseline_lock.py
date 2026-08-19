"""Task 0 — Netz VOR dem Umbau (Carl-Gate A, 2026-08-19).

Diese Datei beschreibt, was sich durch die Quellenunabhaengigkeit NICHT
aendern darf. Sie ist gruen gegen den heutigen Code.
"""
import pytest

from core.clip_candidates import PROPOSED, DISCARDED
from core.project import PeakCutProject
from core.session import PeakCutSession

# pytest.ini setzt bereits `pythonpath = src` — kein sys.path-Gefummel noetig.
_CFG = {"fps": 25, "context_duration_ms": 15000}


def make_session_with_peaks(peaks_ms, *, ignored=()):
    """Session mit synthetischen Peaks; ohne Audio/Video, rein Datenweg.

    PeakCutSession verlangt (project, config) — siehe src/core/session.py:37.
    Muster uebernommen aus tests/test_clip_candidates_session.py:21.
    """
    session = PeakCutSession(PeakCutProject(), dict(_CFG))
    session.load_analysis_results({
        "peaks": [
            {"index": i, "position_ms": ms,
             "in_point_ms": max(0, ms - 15000), "out_point_ms": ms + 15000,
             "context_ms": 15000, "ignored": i in ignored}
            for i, ms in enumerate(peaks_ms)
        ],
        "video_offsets": [],
    })
    return session


def test_baseline_ein_kandidat_je_peak():
    session = make_session_with_peaks([10_000, 60_000, 120_000])
    assert len(session.clip_candidates) == 3
    assert [c.peak_id for c in session.clip_candidates] == [0, 1, 2]


def test_baseline_ignorierter_peak_wird_discarded():
    session = make_session_with_peaks([10_000, 60_000], ignored=(1,))
    assert session.clip_candidates[0].status == PROPOSED
    assert session.clip_candidates[1].status == DISCARDED


def test_baseline_boundary_kommt_aus_in_out_des_peaks():
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.boundary.start_ms == 45_000
    assert cand.boundary.end_ms == 75_000


def test_ziel_kandidat_hat_identitaet_und_herkunft():
    from core.clip_candidates import ORIGIN_MARKER
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER


def test_ziel_anker_ist_der_tritt_nicht_der_anfang():
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.anchor_ms == 60_000          # der Tritt
    assert cand.anchor_ms != cand.boundary.start_ms   # NICHT der Anfang


@pytest.mark.xfail(strict=True, reason="Task 2: Reconcile noch nicht gebaut")
def test_ziel_neu_analyse_erhaelt_fremdquellen():
    from core.clip_candidates import ClipBoundary, ClipCandidate, ORIGIN_AUTO
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:abc", origin=ORIGIN_AUTO, anchor_ms=90_000,
        peak_id=None, boundary=ClipBoundary(80_000, 100_000)))
    session.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
                   "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    ids = {c.candidate_id for c in session.clip_candidates}
    assert "auto:abc" in ids, "Neu-Analyse hat den Auto-Kandidaten vernichtet"
