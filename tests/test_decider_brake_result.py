"""#3-Revision Task 4 — Bremse neu schneiden mit drei Kategorien.

Spec §11 R4: INFRA_FEHLT (kein/ungültiger Key, Modell unerreichbar,
UnicodeEncodeError aus dem SDK) wird klar von DECIDER_VERWORFEN
(Claude antwortete, Bremse lehnte berechtigt ab) und OK getrennt.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.models import (  # noqa: E402
    BoundaryScaffold, BoundarySnapCandidate, BoundaryDecision,
    BoundaryError, BoundaryInfraError, BoundaryOutcome,
    BoundaryDecisionResult)
from core.clip_boundary.decider import (  # noqa: E402
    ClaudeBoundaryDecider, decide_with_brake, decide_with_brake_result)
from core.credentials import CredentialStatus  # noqa: E402

_CFG = {"smart_boundary_min_duration_ms": 12000,
        "smart_boundary_max_duration_ms": 180000,
        "smart_boundary_confidence_threshold": 0.5,
        "smart_boundary_fallback_before_ms": 45000,
        "smart_boundary_fallback_after_ms": 30000,
        "smart_boundary_snap_tolerance_ms": 1500}


def _scaffold():
    return BoundaryScaffold(
        peak_id=7, peak_ms=120000, window_start_ms=0, window_end_ms=240000,
        transcript_excerpt="x",
        snap_candidates=(BoundarySnapCandidate(0, "window_edge"),
                          BoundarySnapCandidate(95000, "sentence_end"),
                          BoundarySnapCandidate(150000, "pause"),
                          BoundarySnapCandidate(240000, "window_edge")))


def test_infra_error_is_subclass_of_boundary_error():
    # `except BoundaryError` fängt es weiter — aber Infra ist
    # unterscheidbar (Task 1, hier erneut bewacht).
    assert issubclass(BoundaryInfraError, BoundaryError)


# --- Decider: vier Infra-Wege werfen BoundaryInfraError ----------------

class _NullKey:
    def get_api_key(self):
        return None

    def status(self):
        return CredentialStatus(False, "missing", "")


class _GoodKey:
    def get_api_key(self):
        return "sk-ant-good"

    def status(self):
        return CredentialStatus(True, "ok", "")


def test_decider_no_key_is_infra():
    dec = ClaudeBoundaryDecider(model="claude-x",
                                 credential_provider=_NullKey())
    try:
        dec._call("prompt")
        assert False, "muss Infra werfen"
    except BoundaryInfraError:
        pass


def test_decider_no_model_is_infra():
    dec = ClaudeBoundaryDecider()        # kein Modell, kein call_model
    try:
        dec.decide(_scaffold())
        assert False
    except BoundaryInfraError:
        pass


def test_decider_unicode_encode_error_is_infra_no_key_leak():
    class _Bomb:
        class messages:                       # noqa: N801
            @staticmethod
            def create(**kw):
                # gemessener Smoke-Test-Fall: Nicht-ASCII-Bytes im Key
                raise UnicodeEncodeError(
                    "ascii", "sk-ant-corrupted-secret", 0, 1, "non-ascii")
    dec = ClaudeBoundaryDecider(
        model="claude-x", credential_provider=_GoodKey(),
        client_factory=lambda api_key: _Bomb())
    try:
        dec._call("prompt")
        assert False
    except BoundaryInfraError as e:
        # NIE Key/Wert in der Meldung — nur Fehlerklasse als Hinweis
        assert "corrupted" not in str(e) and "secret" not in str(e)


def test_decider_api_unreachable_is_infra():
    class _Net:
        class messages:                       # noqa: N801
            @staticmethod
            def create(**kw):
                raise ConnectionError("Claude-Endpoint down")
    dec = ClaudeBoundaryDecider(
        model="claude-x", credential_provider=_GoodKey(),
        client_factory=lambda api_key: _Net())
    try:
        dec._call("prompt")
        assert False
    except BoundaryInfraError:
        pass


# --- decide_with_brake_result: drei Kategorien --------------------------

class _GoodDecider:
    def decide(self, sc):
        # In Snap-Toleranz zu sentence_end (95000) und pause (150000).
        return BoundaryDecision(start_ms=95500, end_ms=150500,
                                 reason="ok", confidence=0.8)


class _UnplausibleDecider:
    def decide(self, sc):
        # Ende vor Peak -> Bremse muss verwerfen
        return BoundaryDecision(start_ms=80000, end_ms=100000,
                                 reason="schlecht", confidence=0.9)


class _InfraDecider:
    def decide(self, sc):
        raise BoundaryInfraError("API down")


def test_result_ok_returns_snapped_decision():
    res = decide_with_brake_result(_scaffold(), _GoodDecider(), config=_CFG)
    assert isinstance(res, BoundaryDecisionResult)
    assert res.category is BoundaryOutcome.OK
    assert res.decision is not None and res.decision.confidence > 0


def test_result_decider_verworfen_returns_fallback_conf_zero():
    res = decide_with_brake_result(
        _scaffold(), _UnplausibleDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.DECIDER_VERWORFEN
    assert res.decision is not None and res.decision.confidence == 0.0


def test_result_infra_returns_no_decision():
    res = decide_with_brake_result(_scaffold(), _InfraDecider(), config=_CFG)
    assert res.category is BoundaryOutcome.INFRA_FEHLT
    assert res.decision is None
    assert res.message                          # nicht leer


# --- Legacy decide_with_brake bleibt Kompat-Wrapper --------------------

def test_legacy_wrapper_ok_returns_decision():
    d = decide_with_brake(_scaffold(), _GoodDecider(), config=_CFG)
    assert isinstance(d, BoundaryDecision) and d.confidence > 0


def test_legacy_wrapper_verworfen_returns_fallback():
    d = decide_with_brake(_scaffold(), _UnplausibleDecider(), config=_CFG)
    assert isinstance(d, BoundaryDecision) and d.confidence == 0.0


def test_legacy_wrapper_infra_still_returns_fallback_for_back_compat():
    d = decide_with_brake(_scaffold(), _InfraDecider(), config=_CFG)
    assert isinstance(d, BoundaryDecision) and d.confidence == 0.0
