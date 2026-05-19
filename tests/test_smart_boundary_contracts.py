"""Roadmap #3 Gate A — Datenverträge einfrieren (Carl-Finalplan).

STOPP-Gate: Nach Freigabe nicht mehr an diesen Contracts drehen.
Reine Datenmodelle + Protocols. Kein Worker, kein Scaffold-/Decider-
Logik, keine Pipeline (= spätere Tasks/Gates).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.transcription import (  # noqa: E402
    TranscriptWord, TranscriptSegment, Transcript,
    TranscriptionEngine, TranscriptError,
)
from core.clip_boundary.models import (  # noqa: E402
    BoundarySnapCandidate, BoundaryScaffold, BoundaryDecision,
    BoundaryDecider, BoundaryError,
)
# #3-Revision Gate A — NEUE Verträge NEBEN den eingefrorenen (Pin 3:
# die obigen Kernmodelle bleiben byte-/feldstabil und werden NICHT
# angefasst).
from core.clip_boundary.models import (  # noqa: E402
    BoundaryInfraError, BoundaryOutcome,
    BoundaryDecisionResult, SmartBoundaryRunResult,
)
from core.credentials import (  # noqa: E402
    CredentialStatus, ClaudeCredentialProvider,
)


# --- Transcript-Verträge --------------------------------------------------

def test_transcript_word_validation():
    TranscriptWord(0, 1, "hi")  # ok
    for bad in ((5, 5, "x"), (4, 1, "x"), (-1, 10, "x")):
        try:
            TranscriptWord(*bad)
            assert False, f"ungueltig muss abgelehnt werden: {bad}"
        except ValueError:
            pass


def test_transcript_roundtrip_exact():
    w1 = TranscriptWord(1000, 1200, "Das")
    w2 = TranscriptWord(1200, 1500, "System")
    seg = TranscriptSegment(1000, 1500, "Das System", words=(w1, w2))
    t = Transcript(segments=(seg,))
    assert TranscriptWord.from_dict(w1.to_dict()) == w1
    assert TranscriptSegment.from_dict(seg.to_dict()) == seg
    assert Transcript.from_dict(t.to_dict()) == t
    # leeres Transcript ist gültig (kein Sprachinhalt -> Müll-Drücker)
    empty = Transcript()
    assert Transcript.from_dict(empty.to_dict()) == empty
    assert empty.segments == ()


def test_transcript_segment_words_optional_and_tuple():
    seg = TranscriptSegment(0, 100, "nur Segment")
    assert seg.words == ()
    assert TranscriptSegment.from_dict(seg.to_dict()) == seg


def test_transcription_engine_protocol_is_runtime_checkable():
    class FakeEngine:
        def transcribe(self, audio_path, *, language, model):
            return Transcript()

    assert isinstance(FakeEngine(), TranscriptionEngine)
    assert not isinstance(object(), TranscriptionEngine)


def test_transcript_error_exists():
    assert issubclass(TranscriptError, Exception)


# --- Clip-Boundary-Verträge ----------------------------------------------

def test_snap_candidate_validation():
    BoundarySnapCandidate(0, "sentence_end")  # ok
    BoundarySnapCandidate(5000, "pause", label="nach Frage")  # ok
    for bad in ((-1, "pause"), (100, "")):
        try:
            BoundarySnapCandidate(*bad)
            assert False, f"ungueltig: {bad}"
        except ValueError:
            pass


def test_scaffold_validation_peak_in_window():
    BoundaryScaffold(peak_id=3, peak_ms=60000,
                     window_start_ms=0, window_end_ms=120000)  # ok
    # window_end <= window_start
    try:
        BoundaryScaffold(peak_id=1, peak_ms=10, window_start_ms=50,
                         window_end_ms=50)
        assert False
    except ValueError:
        pass
    # Peak ausserhalb des Fensters
    try:
        BoundaryScaffold(peak_id=1, peak_ms=999999,
                         window_start_ms=0, window_end_ms=1000)
        assert False, "Peak ausserhalb Fenster muss abgelehnt werden"
    except ValueError:
        pass


def test_scaffold_roundtrip_exact():
    sc = BoundaryScaffold(
        peak_id=7, peak_ms=60000, window_start_ms=0, window_end_ms=180000,
        transcript_excerpt="… Text mit [PEAK] Markierung …",
        snap_candidates=(BoundarySnapCandidate(1000, "sentence_end"),
                         BoundarySnapCandidate(2000, "pause", "x")))
    assert BoundaryScaffold.from_dict(sc.to_dict()) == sc


def test_boundary_decision_validation_and_roundtrip():
    d = BoundaryDecision(123000, 171000, "Frage bis Pointe", 0.74)
    assert BoundaryDecision.from_dict(d.to_dict()) == d
    for bad in ((100, 100, "x", 0.5), (200, 100, "x", 0.5),
                (-1, 10, "x", 0.5),
                (0, 10, "x", -0.1), (0, 10, "x", 1.1)):
        try:
            BoundaryDecision(*bad)
            assert False, f"ungueltig: {bad}"
        except ValueError:
            pass


def test_boundary_decider_protocol_is_runtime_checkable():
    class FakeDecider:
        def decide(self, scaffold):
            return BoundaryDecision(0, 1, "stub", 0.0)

    assert isinstance(FakeDecider(), BoundaryDecider)
    assert not isinstance(object(), BoundaryDecider)


def test_boundary_error_exists():
    assert issubclass(BoundaryError, Exception)


# ══════════════════════════════════════════════════════════════════════
# #3-Revision Gate A — neue Ergebnis-/Credential-Verträge (Spec §11
# R3/R4, Carl Task 1 + Pin 3). NEU NEBEN den eingefrorenen Modellen;
# nach Freigabe nicht mehr beiläufig drehen.
# ══════════════════════════════════════════════════════════════════════


def test_boundary_infra_error_is_a_boundary_error():
    # Subklasse: bestehendes `except BoundaryError` fängt es weiter,
    # aber Infra ist gezielt unterscheidbar (R4).
    assert issubclass(BoundaryInfraError, BoundaryError)
    assert issubclass(BoundaryInfraError, Exception)


def test_boundary_outcome_categories():
    assert {o.value for o in BoundaryOutcome} == {
        "OK", "DECIDER_VERWORFEN", "INFRA_FEHLT"}
    # str-Enum -> serialisierbar/vergleichbar wie ein String
    assert BoundaryOutcome.OK == "OK"
    assert BoundaryOutcome("INFRA_FEHLT") is BoundaryOutcome.INFRA_FEHLT


def test_boundary_decision_result_shape_and_rules():
    d = BoundaryDecision(1000, 2000, "ok", 0.8)
    ok = BoundaryDecisionResult(BoundaryOutcome.OK, d, "")
    assert ok.category is BoundaryOutcome.OK and ok.decision is d
    # DECIDER_VERWORFEN trägt den conf-0.0-Rückfall (echtes Signal)
    fb = BoundaryDecision(1000, 2000, "Bremse: unplausibel", 0.0)
    verw = BoundaryDecisionResult(BoundaryOutcome.DECIDER_VERWORFEN, fb, "x")
    assert verw.decision.confidence == 0.0
    # INFRA_FEHLT -> KEINE Decision (kein Pseudo-Ergebnis)
    infra = BoundaryDecisionResult(BoundaryOutcome.INFRA_FEHLT, None,
                                   "API-Key ungültig")
    assert infra.decision is None
    for bad in ((BoundaryOutcome.OK, None, ""),               # OK ohne Decision
                (BoundaryOutcome.INFRA_FEHLT, d, "")):        # Infra mit Decision
        try:
            BoundaryDecisionResult(*bad)
            assert False, f"ungültig: {bad}"
        except ValueError:
            pass


def test_smart_boundary_run_result_no_pseudo_on_infra():
    cands = (object(), object())
    ok = SmartBoundaryRunResult(cands, BoundaryOutcome.OK, "", 2, 0)
    assert ok.candidates == cands and ok.ready_count == 2
    # INFRA_FEHLT: keine Pseudo-Candidates -> beide Zähler 0
    infra = SmartBoundaryRunResult((), BoundaryOutcome.INFRA_FEHLT,
                                   "kein Key", 0, 0)
    assert infra.ready_count == 0 and infra.fallback_count == 0
    for bad in ((cands, BoundaryOutcome.OK, "", -1, 0),       # negativ
                ((), BoundaryOutcome.INFRA_FEHLT, "", 1, 0),   # Infra + Zähler
                ((), BoundaryOutcome.INFRA_FEHLT, "", 0, 3)):
        try:
            SmartBoundaryRunResult(*bad)
            assert False, f"ungültig: {bad}"
        except ValueError:
            pass


def test_credential_status_shape():
    ok = CredentialStatus(True, "", "Key ok")
    bad = CredentialStatus(False, "missing", "Kein Key hinterlegt")
    assert ok.ok is True and bad.ok is False
    assert bad.reason == "missing"


def test_claude_credential_provider_protocol_runtime_checkable():
    class FakeProvider:
        def get_api_key(self):
            return "sk-test"

        def status(self):
            return CredentialStatus(True, "", "ok")

    assert isinstance(FakeProvider(), ClaudeCredentialProvider)
    assert not isinstance(object(), ClaudeCredentialProvider)
