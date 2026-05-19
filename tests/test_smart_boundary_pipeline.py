"""Roadmap #3 Task 6 — SmartBoundaryWorker + Pipeline (Stufe B), Carl.

Stufe B konsumiert NUR das gespeicherte Transkript (Spec-Rework: kein
transcriber-Param mehr — Abweichung von Carls Ur-Signatur, bewusst).
Füllt vorhandene ClipCandidate, Status bleibt proposed, Fehler pro
Peak isoliert, Totalfehler/kein Transkript -> Skip (Bootstrap bleibt).
Deterministisch — kein echtes Whisper/Claude.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.pipeline import prepare_smart_boundaries  # noqa: E402
from core.clip_boundary.models import BoundaryDecision  # noqa: E402
from core.clip_candidates import PROPOSED, DISCARDED  # noqa: E402
from core.transcription import Transcript, TranscriptSegment  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_CFG = {
    "fps": 25, "context_duration_ms": 15000,
    "smart_boundary_min_duration_ms": 12000,
    "smart_boundary_max_duration_ms": 180000,
    "smart_boundary_confidence_threshold": 0.5,
    "smart_boundary_fallback_before_ms": 45000,
    "smart_boundary_fallback_after_ms": 30000,
    "smart_boundary_snap_tolerance_ms": 1500,
    "smart_boundary_search_before_ms": 180000,
    "smart_boundary_search_after_ms": 60000,
    "smart_boundary_sentence_gap_ms": 900,
}


def _peak(index, pos, ignored=False):
    return {"index": index, "position_ms": pos, "context_ms": 15000,
            "ignored": ignored}


def _session(peaks):
    s = PeakCutSession(PeakCutProject(), dict(_CFG))
    s.load_analysis_results({"peaks": peaks, "video_offsets": []})
    s.speaker_activity = []
    s.transcript = Transcript(segments=(
        TranscriptSegment(0, 700000, "langer Gesprächsabschnitt"),))
    return s


class _GoodDecider:
    def decide(self, scaffold):
        return BoundaryDecision(scaffold.window_start_ms,
                                scaffold.window_end_ms, "ok", 0.9)


class _PerPeakBoom:
    def decide(self, scaffold):
        if scaffold.peak_id == 1:
            raise RuntimeError("Decider kaputt für genau diesen Peak")
        return BoundaryDecision(scaffold.window_start_ms,
                                scaffold.window_end_ms, "ok", 0.9)


def _cand(session, peak_id):
    return next(c for c in session.clip_candidates if c.peak_id == peak_id)


def test_fills_candidates_and_status_stays_proposed():
    s = _session([_peak(0, 120000), _peak(2, 300000)])
    prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    for pid in (0, 2):
        c = _cand(s, pid)
        assert c.status == PROPOSED
        assert c.score is not None
        assert c.reason != ""
        assert c.boundary.end_ms > c.boundary.start_ms


def test_ignored_peak_stays_discarded_untouched():
    s = _session([_peak(0, 120000), _peak(1, 300000, ignored=True)])
    prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    ig = _cand(s, 1)
    assert ig.status == DISCARDED
    assert ig.score is None                 # nicht angefasst
    assert _cand(s, 0).score is not None    # der andere schon


def test_per_peak_error_isolated_others_still_filled():
    s = _session([_peak(0, 120000), _peak(1, 300000), _peak(2, 480000)])
    prepare_smart_boundaries(s, _PerPeakBoom(), config=_CFG)
    # Peak 1 wirft im Decider -> Bremse fängt -> Fallback (score 0.0),
    # NICHT None, und bricht die anderen nicht ab.
    assert _cand(s, 1).score == 0.0
    assert _cand(s, 0).score is not None
    assert _cand(s, 2).score is not None
    assert all(c.status == PROPOSED for c in s.clip_candidates)


def test_no_transcript_skips_all_candidates_unchanged():
    s = _session([_peak(0, 120000), _peak(2, 300000)])
    s.transcript = None
    s.transcript_ref = None
    prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    for pid in (0, 2):
        c = _cand(s, pid)
        assert c.score is None              # Bootstrap unverändert
        assert c.status == PROPOSED


def test_returns_candidate_list():
    s = _session([_peak(0, 120000)])
    out = prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    assert out is s.clip_candidates


def test_cooperative_stop_between_peaks():
    s = _session([_peak(0, 120000), _peak(2, 300000)])
    calls = {"n": 0}

    def stop_after_first():
        calls["n"] += 1
        return calls["n"] > 1               # erst nach dem 1. Peak stoppen

    prepare_smart_boundaries(s, _GoodDecider(), config=_CFG,
                             should_stop=stop_after_first)
    scored = [c for c in s.clip_candidates if c.score is not None]
    assert len(scored) == 1                 # genau ein Peak verarbeitet


# --- SmartBoundaryWorker (Stufe B, nach Export-Handoff) ----------------

def test_smart_boundary_worker_runs_and_finishes():
    from gui.workers import SmartBoundaryWorker
    s = _session([_peak(0, 120000)])
    done = {}
    w = SmartBoundaryWorker(s, _GoodDecider())
    w.finished.connect(lambda lst: done.setdefault("n", len(lst)))
    w.run()
    assert done.get("n") == 1
    assert _cand(s, 0).score is not None


def test_smart_boundary_worker_request_stop_is_cooperative():
    from gui.workers import SmartBoundaryWorker
    s = _session([_peak(0, 120000), _peak(2, 300000)])
    w = SmartBoundaryWorker(s, _GoodDecider())
    w.request_stop()                         # vor Start -> nichts verarbeiten
    w.run()
    assert all(c.score is None for c in s.clip_candidates)
