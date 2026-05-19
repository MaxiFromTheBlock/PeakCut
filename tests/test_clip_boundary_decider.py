"""Roadmap #3 Task 5 — Claude-Decider + Plausibilitätsbremse (Carl).

Kein echter API-Call in pytest (Fake-Decider / injiziertes call_model).
Gate D: Claude darf kreativ entscheiden, aber NIE strukturell kaputt
schreiben — die deterministische Bremse fängt alles ab und fällt
kontrolliert zurück.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.models import (  # noqa: E402
    BoundaryScaffold, BoundarySnapCandidate, BoundaryDecision)
from core.clip_boundary.decider import (  # noqa: E402
    decide_with_brake, build_decider_prompt, ClaudeBoundaryDecider)

_CFG = {
    "smart_boundary_min_duration_ms": 12000,
    "smart_boundary_max_duration_ms": 180000,
    "smart_boundary_confidence_threshold": 0.5,
    "smart_boundary_fallback_before_ms": 45000,
    "smart_boundary_fallback_after_ms": 30000,
}


def _scaffold():
    return BoundaryScaffold(
        peak_id=7, peak_ms=120000,
        window_start_ms=0, window_end_ms=240000,
        transcript_excerpt="[1:50] Frage\n[PEAK @ 2:00]\n[2:01] Antwort",
        snap_candidates=(
            BoundarySnapCandidate(0, "window_edge"),
            BoundarySnapCandidate(95000, "sentence_end"),
            BoundarySnapCandidate(150000, "pause"),
            BoundarySnapCandidate(240000, "window_edge")))


class _FixedDecider:
    def __init__(self, decision=None, boom=False):
        self._d = decision
        self._boom = boom

    def decide(self, scaffold):
        if self._boom:
            raise RuntimeError("Claude offline")
        return self._d


def _fallback_ok(d, sc):
    assert isinstance(d, BoundaryDecision)
    assert sc.window_start_ms <= d.start_ms < d.end_ms <= sc.window_end_ms
    assert d.start_ms <= sc.peak_ms < d.end_ms      # Peak drin, nicht am Ende
    assert d.confidence <= 0.1                        # als unsicher markiert
    assert d.reason                                   # klarer Grund


# --- Gutfall ------------------------------------------------------------

def test_valid_decision_passes_brake_unchanged():
    good = BoundaryDecision(95000, 150000, "Frage bis Pointe", 0.8)
    out = decide_with_brake(_scaffold(), _FixedDecider(good), config=_CFG)
    assert out == good


# --- Bremse: jeder strukturelle Defekt -> sicherer Rückfall ------------

def test_decider_exception_falls_back():
    out = decide_with_brake(_scaffold(), _FixedDecider(boom=True),
                            config=_CFG)
    _fallback_ok(out, _scaffold())


def test_outside_window_falls_back():
    sc = _scaffold()
    # voll im Fenster + valide -> bleibt unverändert
    inside = BoundaryDecision(95000, 150000, "drin", 0.9)
    assert decide_with_brake(sc, _FixedDecider(inside), config=_CFG) == inside
    # Ende jenseits der Fensterdecke -> Rückfall
    over = BoundaryDecision(95000, sc.window_end_ms + 50000, "drüber", 0.9)
    _fallback_ok(decide_with_brake(sc, _FixedDecider(over), config=_CFG), sc)


def test_peak_not_contained_falls_back():
    sc = _scaffold()
    d = BoundaryDecision(150000, 200000, "nach dem Peak", 0.9)  # Peak 120k davor
    _fallback_ok(decide_with_brake(sc, _FixedDecider(d), config=_CFG), sc)


def test_too_short_and_too_long_fall_back():
    sc = _scaffold()
    short = BoundaryDecision(119000, 119000 + 5000, "zu kurz", 0.9)
    _fallback_ok(decide_with_brake(sc, _FixedDecider(short), config=_CFG), sc)
    long = BoundaryDecision(0, 200000, "zu lang", 0.9)  # 200s > max 180s
    _fallback_ok(decide_with_brake(sc, _FixedDecider(long), config=_CFG), sc)


def test_end_at_or_before_peak_falls_back():
    sc = _scaffold()
    blunt = BoundaryDecision(60000, sc.peak_ms, "hart am Drücker", 0.9)
    _fallback_ok(decide_with_brake(sc, _FixedDecider(blunt), config=_CFG), sc)


def test_low_confidence_falls_back():
    sc = _scaffold()
    weak = BoundaryDecision(95000, 150000, "unsicher", 0.3)  # < 0.5
    _fallback_ok(decide_with_brake(sc, _FixedDecider(weak), config=_CFG), sc)


# --- Prompt-Regeln (Carl Gate-C: window_edge als Fallback rahmen) ------

def test_prompt_has_rules_peak_json_and_window_edge_as_fallback():
    p = build_decider_prompt(_scaffold())
    assert "PEAK" in p
    assert "json" in p.lower()
    low = p.lower()
    assert "fallback" in low or "rückfall" in low or "notkante" in low
    assert "window_edge" in p


# --- ClaudeBoundaryDecider: injiziertes call_model, kein Netz ----------

def test_claude_decider_parses_strict_json():
    sc = _scaffold()

    def fake_call(prompt):
        return '{"start_ms": 95000, "end_ms": 150000, ' \
               '"reason": "ok", "confidence": 0.7}'

    d = ClaudeBoundaryDecider(call_model=fake_call).decide(sc)
    assert d == BoundaryDecision(95000, 150000, "ok", 0.7)


def test_claude_decider_bad_json_then_brake_fallback():
    sc = _scaffold()
    dec = ClaudeBoundaryDecider(call_model=lambda p: "kein json")
    _fallback_ok(decide_with_brake(sc, dec, config=_CFG), sc)
