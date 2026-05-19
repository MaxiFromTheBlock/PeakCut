"""#3-Revision Task 5 — Pipeline-Ergebnis statt Liste (Spec §11 R4).

Carl Task 5 + Pin 3 + Task-4-Caveat:
- prepare_smart_boundaries() gibt SmartBoundaryRunResult (Pin 3:
  einzige semantische Vertragsänderung).
- Drei Kategorien aggregiert; INFRA_FEHLT bricht den Run ab und
  erzeugt KEINE Pseudo-Candidates.
- Pipeline nutzt decide_with_brake_result, NICHT mehr den alten
  Wrapper im Smart-Pfad.
- Worker-Signal wird object; ReviewPage konsumiert die neue Shape.
"""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.pipeline import prepare_smart_boundaries  # noqa: E402
from core.clip_boundary.models import (  # noqa: E402
    BoundaryDecision, BoundaryInfraError, BoundaryOutcome,
    SmartBoundaryRunResult)
from core.clip_candidates import PROPOSED  # noqa: E402
from core.transcription import Transcript, TranscriptSegment  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000,
        "smart_boundary_min_duration_ms": 12000,
        "smart_boundary_max_duration_ms": 180000,
        "smart_boundary_confidence_threshold": 0.5,
        "smart_boundary_fallback_before_ms": 45000,
        "smart_boundary_fallback_after_ms": 30000,
        "smart_boundary_snap_tolerance_ms": 1500,
        "smart_boundary_search_before_ms": 180000,
        "smart_boundary_search_after_ms": 60000,
        "smart_boundary_sentence_gap_ms": 900}


def _peak(idx, pos, ignored=False):
    return {"index": idx, "position_ms": pos, "context_ms": 15000,
            "ignored": ignored}


def _session(peaks):
    s = PeakCutSession(PeakCutProject(), dict(_CFG))
    s.load_analysis_results({"peaks": peaks, "video_offsets": []})
    s.speaker_activity = []
    s.transcript = Transcript(segments=(
        TranscriptSegment(0, 700_000, "langer Gesprächsabschnitt"),))
    return s


class _GoodDecider:
    def decide(self, sc):
        return BoundaryDecision(sc.window_start_ms, sc.window_end_ms,
                                 "ok", 0.9)


class _UnplausibleDecider:
    def decide(self, sc):
        # Ende vor Peak -> Bremse verwirft -> conf 0.0 Fallback
        return BoundaryDecision(sc.window_start_ms,
                                 sc.peak_ms - 1, "schlecht", 0.9)


class _InfraDecider:
    def decide(self, sc):
        raise BoundaryInfraError("kein Key")


# --- Pipeline -----------------------------------------------------------

def test_pipeline_returns_run_result_ok_with_ready_counts():
    # Peaks so positioniert, dass das (vom Decider zurückgegebene)
    # volle Suchfenster die Max-Dauer NICHT übersteigt — sonst lehnt
    # die Bremse berechtigt ab (das ist ein anderer Test).
    s = _session([_peak(0, 60_000), _peak(2, 100_000)])
    res = prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    assert isinstance(res, SmartBoundaryRunResult)
    assert res.category is BoundaryOutcome.OK
    assert res.ready_count == 2 and res.fallback_count == 0
    assert res.candidates == tuple(s.clip_candidates)


def test_pipeline_no_transcript_is_infra_no_pseudo():
    s = _session([_peak(0, 120_000), _peak(2, 300_000)])
    s.transcript = None
    s.transcript_ref = None
    res = prepare_smart_boundaries(s, _GoodDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.INFRA_FEHLT
    assert res.ready_count == 0 and res.fallback_count == 0
    # Candidates unverändert (Bootstrap-Status, KEINE Pseudo-Scores)
    for c in s.clip_candidates:
        assert c.score is None
    assert "Transkript" in res.message


def test_pipeline_infra_mid_run_is_all_or_nothing():
    # Carl-Gegenreview [P2]: ein erstes OK-Ergebnis darf NICHT in
    # session.clip_candidates landen, wenn der zweite Peak Infra
    # signalisiert. UI sagt sonst "nicht berechnet", aber Autosave
    # persistiert ein Teil-Ergebnis als heimliche Wahrheit.
    class _OkThenInfra:
        def __init__(self):
            self.n = 0

        def decide(self, sc):
            self.n += 1
            if self.n == 1:
                return BoundaryDecision(sc.window_start_ms,
                                         sc.window_end_ms, "ok", 0.9)
            raise BoundaryInfraError("API erst spät verloren")

    s = _session([_peak(0, 60_000), _peak(2, 100_000)])
    res = prepare_smart_boundaries(s, _OkThenInfra(), config=_CFG)
    assert res.category is BoundaryOutcome.INFRA_FEHLT
    assert res.ready_count == 0 and res.fallback_count == 0
    # ALLE Scores None — auch der "erfolgreiche" erste Peak bleibt
    # unverändert. All-or-nothing.
    for c in s.clip_candidates:
        assert c.score is None


def test_pipeline_infra_decider_aborts_run_no_pseudo_candidates():
    s = _session([_peak(0, 120_000), _peak(1, 200_000), _peak(2, 300_000)])
    res = prepare_smart_boundaries(s, _InfraDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.INFRA_FEHLT
    # Keine Pseudo-Candidates -> alle Scores None
    for c in s.clip_candidates:
        assert c.score is None
    assert res.ready_count == 0 and res.fallback_count == 0


def test_pipeline_verworfen_counts_as_fallback_run_finishes_ok():
    s = _session([_peak(0, 120_000), _peak(2, 300_000)])
    res = prepare_smart_boundaries(s, _UnplausibleDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.OK    # Lauf abgeschlossen
    assert res.ready_count == 0 and res.fallback_count == 2
    for c in s.clip_candidates:
        assert c.score == 0.0                    # echtes Signal


def test_pipeline_uses_result_variant_not_legacy_wrapper():
    # Carl Task-4-Caveat: der Wrapper darf NICHT mehr im Produktions-
    # Smart-Pfad hängen. Belegt empirisch: ein Infra-Decider würde im
    # Wrapper still in einen Fallback fallen — die Pipeline muss
    # stattdessen die Run-Kategorie INFRA_FEHLT setzen.
    s = _session([_peak(0, 120_000)])
    res = prepare_smart_boundaries(s, _InfraDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.INFRA_FEHLT
    assert s.clip_candidates[0].score is None    # kein Wrapper-Fallback


# --- SmartBoundaryWorker emittiert das Run-Result -----------------------

def test_smart_worker_finished_emits_run_result():
    from gui.workers import SmartBoundaryWorker
    s = _session([_peak(0, 120_000)])
    out = {}
    w = SmartBoundaryWorker(s, _GoodDecider())
    w.finished.connect(lambda r: out.setdefault("res", r))
    w.run()
    res = out["res"]
    assert isinstance(res, SmartBoundaryRunResult)
    assert res.category is BoundaryOutcome.OK and res.ready_count == 1


# --- ReviewPage-Handler konsumiert die neue Shape ----------------------

class _Sig:
    def __init__(self, name, events):
        self._n, self._ev = name, events

    def emit(self, *a):
        self._ev.append(self._n)

    def connect(self, _cb):
        pass


def _fake_self(events):
    ns = types.SimpleNamespace()
    ns.session = types.SimpleNamespace(
        project=types.SimpleNamespace(export_dir="/tmp/x"),
        config={"smart_boundary_enabled": True},
        clip_candidates=[])
    ns.export_btn = types.SimpleNamespace(setEnabled=lambda v: None)
    ns.status_message = _Sig("status", events)
    ns.session_changed = _Sig("session_changed", events)
    ns._smart_worker = None
    return ns


def test_handler_runs_exporters_on_ok_and_persists():
    from gui.review_page import ReviewPage
    events = []
    fs = _fake_self(events)
    calls = []
    res = SmartBoundaryRunResult(
        (), BoundaryOutcome.OK, "", 1, 0)
    with patch("gui.review_page.SinnabschnittTXTExporter") as T, \
         patch("gui.review_page.SinnabschnittXMLExporter") as X:
        T.return_value.export = lambda s: calls.append("txt")
        X.return_value.export = lambda s: calls.append("xml")
        ReviewPage._on_smart_boundaries_done(fs, res)
    assert calls == ["txt", "xml"]
    assert "session_changed" in events


def test_handler_skips_exporters_on_infra_fehlt_loud_status():
    from gui.review_page import ReviewPage
    events = []
    fs = _fake_self(events)
    res = SmartBoundaryRunResult(
        (), BoundaryOutcome.INFRA_FEHLT, "kein Key", 0, 0)
    with patch("gui.review_page.SinnabschnittTXTExporter") as T, \
         patch("gui.review_page.SinnabschnittXMLExporter") as X:
        ReviewPage._on_smart_boundaries_done(fs, res)
        T.assert_not_called()
        X.assert_not_called()
    # Lauter Status statt stiller Stille
    assert "status" in events
