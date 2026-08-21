"""KI-2 — R2-Ausricht-Riegel (Carl-Plan 2026-06-15).

Ein zeitlich fehlausgerichtetes Transkript (Text-Spanne weicht stark von
der Audiodauer ab) darf KEINE Sinnabschnitt-Kandidaten erzeugen — sonst
landen plausible, aber zeitlich falsche Abschnitte mit Score in der
candidate_decisions-Sammlung (G5-Burggraben, nicht reparierbar). Der Riegel
sitzt zentral in prepare_smart_boundaries (nicht nur im Worker) und nutzt
die bestehende INFRA_FEHLT-Semantik (kein neuer Contract).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.pipeline import prepare_smart_boundaries  # noqa: E402
from core.clip_boundary.models import (  # noqa: E402
    BoundaryDecision, BoundaryOutcome,
)
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
    "smart_boundary_alignment_tolerance_ms": 120000,
}


def _peak(index, pos, ignored=False):
    return {"index": index, "position_ms": pos, "context_ms": 15000,
            "ignored": ignored}


def _session(peaks):
    s = PeakCutSession(PeakCutProject(), dict(_CFG))
    s.load_analysis_results({"peaks": peaks, "video_offsets": []})
    s.speaker_activity = []
    # Transkript-Spanne = 700000 ms (größtes Segment-Ende).
    s.transcript = Transcript(segments=(
        TranscriptSegment(0, 700000, "langer Gesprächsabschnitt"),))
    return s


class _SpyDecider:
    def __init__(self):
        self.calls = 0

    def decide(self, scaffold):
        self.calls += 1
        return BoundaryDecision(scaffold.window_start_ms,
                                scaffold.window_end_ms, "ok", 0.9)


def _cand(session, peak_id):
    return next(c for c in session.clip_candidates if c.peak_id == peak_id)


def test_misaligned_transcript_blocks_with_infra():
    s = _session([_peak(0, 120000), _peak(2, 300000)])
    # Audio nur 60s, Text 700s -> Drift 640s >> 120s Toleranz.
    s.transcript_ref = {"audio_duration_ms": 60000}
    spy = _SpyDecider()
    out = prepare_smart_boundaries(s, spy, config=_CFG)
    assert out.category is BoundaryOutcome.INFRA_FEHLT
    assert spy.calls == 0                       # Decider nie aufgerufen
    assert "zeitlich" in out.message.lower()
    for c in s.clip_candidates:
        assert c.score is None                  # keine Kandidaten-Scores


def test_aligned_transcript_runs_decider():
    s = _session([_peak(0, 120000)])
    s.transcript_ref = {"audio_duration_ms": 700000}   # passt
    spy = _SpyDecider()
    out = prepare_smart_boundaries(s, spy, config=_CFG)
    assert out.category is BoundaryOutcome.OK
    assert spy.calls >= 1
    assert _cand(s, 0).score is not None


def test_missing_duration_does_not_block():
    s = _session([_peak(0, 120000)])
    s.transcript_ref = {}                       # keine audio_duration_ms
    spy = _SpyDecider()
    out = prepare_smart_boundaries(s, spy, config=_CFG)
    assert out.category is BoundaryOutcome.OK
    assert spy.calls >= 1


def test_no_ref_does_not_block():
    s = _session([_peak(0, 120000)])
    s.transcript_ref = None
    spy = _SpyDecider()
    out = prepare_smart_boundaries(s, spy, config=_CFG)
    assert out.category is BoundaryOutcome.OK
    assert spy.calls >= 1


def test_drift_exactly_at_tolerance_still_runs():
    # |700000 - 580000| = 120000 == Toleranz -> NICHT > tol -> läuft.
    s = _session([_peak(0, 120000)])
    s.transcript_ref = {"audio_duration_ms": 580000}
    spy = _SpyDecider()
    out = prepare_smart_boundaries(s, spy, config=_CFG)
    assert out.category is BoundaryOutcome.OK
    assert spy.calls >= 1
