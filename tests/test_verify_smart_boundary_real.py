"""Roadmap #3 Task 10 — Hand-Skript: reine Teile testbar (Carl).

NUR die reinen Helfer (Peak-Report + Mess-Gate-Entscheidung). Kein
echtes Whisper/Claude — das Modul darf offline importierbar sein
(mlx_whisper/anthropic dürfen beim Import NICHT gezogen werden).
"""

import importlib.util
import os
import sys
import types

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts",
                       "verify_smart_boundary_real.py")
_spec = importlib.util.spec_from_file_location("vsbr", _SCRIPT)
vsbr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vsbr)


def _peak(index, pos):
    return types.SimpleNamespace(index=index, position_ms=pos)


def _cand(peak_id, s, e, score, reason="r"):
    return types.SimpleNamespace(
        peak_id=peak_id,
        boundary=types.SimpleNamespace(start_ms=s, end_ms=e),
        score=score, reason=reason)


def test_offline_importable_no_heavy_engines():
    assert "mlx_whisper" not in sys.modules
    assert "anthropic" not in sys.modules


def test_peak_report_old_vs_new_duration_fallback_flag():
    peaks = [_peak(0, 120000), _peak(1, 300000)]
    cands = [_cand(0, 95000, 150000, 0.82, "Frage bis Pointe"),
             _cand(1, 270000, 330000, 0.0, "Rückfall")]   # score 0.0 = Fallback
    rows = vsbr.build_peak_report(peaks, cands, context_ms=15000)
    r0 = rows[0]
    assert r0["peak_id"] == 0
    assert r0["old_start_ms"] == 105000 and r0["old_end_ms"] == 135000
    assert r0["new_start_ms"] == 95000 and r0["new_end_ms"] == 150000
    assert r0["duration_s"] == 55
    assert r0["score"] == 0.82
    assert r0["fallback"] is False
    assert "Frage bis Pointe" in r0["reason"]
    assert rows[1]["fallback"] is True            # score 0.0


def test_peak_report_handles_missing_candidate():
    rows = vsbr.build_peak_report([_peak(7, 60000)], [], context_ms=15000)
    assert rows[0]["peak_id"] == 7
    assert rows[0]["new_start_ms"] is None        # kein Smart-Kandidat
    assert rows[0]["fallback"] is None


def test_mess_gate_decision_parallel_vs_after():
    # unter Schwelle -> parallel bleibt
    assert vsbr.decide_transcription_start(100.0, 110.0) == "parallel_analysis"
    # über Schwelle -> kippt auf nach-Analyse
    assert vsbr.decide_transcription_start(100.0, 130.0) == "after_analysis"
    # genau auf Schwelle (nicht strikt größer) -> parallel
    assert vsbr.decide_transcription_start(100.0, 115.0) == "parallel_analysis"
    # keine Baseline -> sicher parallel (keine Fehlentscheidung)
    assert vsbr.decide_transcription_start(0.0, 50.0) == "parallel_analysis"
