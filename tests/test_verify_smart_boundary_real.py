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


# --- #3-Rev Task 9 — neue Report-Felder ---------------------------------

def test_summarize_run_result_categories_and_counts():
    from core.clip_boundary.models import (
        SmartBoundaryRunResult, BoundaryOutcome)
    res = SmartBoundaryRunResult((), BoundaryOutcome.OK, "", 3, 1)
    s = vsbr.summarize_run_result(res)
    assert s["category"] == "OK"
    assert s["ready_count"] == 3 and s["fallback_count"] == 1

    res2 = SmartBoundaryRunResult(
        (), BoundaryOutcome.INFRA_FEHLT, "API-Key ungültig", 0, 0)
    s2 = vsbr.summarize_run_result(res2)
    assert s2["category"] == "INFRA_FEHLT"
    assert "ungültig" in s2["message"]


def test_format_key_status_never_includes_key_value():
    from core.credentials import CredentialStatus
    s = vsbr.format_key_status(
        CredentialStatus(True, "ok", "ignored detail with sk-ant-secret"))
    assert "sk-ant" not in s and "secret" not in s
    assert "✓" in s
    assert vsbr.format_key_status(
        CredentialStatus(False, "missing", "")).startswith("Key-Status: ✗")
    assert "kein Key" in vsbr.format_key_status(
        CredentialStatus(False, "missing", ""))
    assert "ungültig" in vsbr.format_key_status(
        CredentialStatus(False, "invalid", ""))
    assert "Dev-Fallback" in vsbr.format_key_status(
        CredentialStatus(True, "env", ""))


def test_format_fingerprint_compact_and_tolerant():
    assert vsbr.format_fingerprint({"size": 17, "mtime_ns": 42}) == \
        "size=17 mtime_ns=42"
    assert vsbr.format_fingerprint(None) == "—"
    assert vsbr.format_fingerprint({}) == "—"


def test_transcript_source_label():
    assert vsbr.transcript_source_label({"source": "descript"}) == "descript"
    assert vsbr.transcript_source_label({"path": "x"}) == "whisper"
    assert vsbr.transcript_source_label(None) == "—"


def test_cache_hit_label_three_states():
    fp = {"size": 1, "mtime_ns": 100}
    assert vsbr.cache_hit_label(None, fp) == "MISS (kein Vorlauf)"
    assert vsbr.cache_hit_label({"audio_fingerprint": fp}, fp) == "HIT"
    assert vsbr.cache_hit_label({"audio_fingerprint": {"size": 9}}, fp) == \
        "MISS (Fingerprint geändert)"


def test_classify_media_files_handles_uppercase_extensions():
    # Carl-Gegenreview [P2]: echte Recorder-Dateien tragen .WAV/.MOV.
    files = ["/x/Keyboard.WAV", "/x/MIC1 mix.WAV", "/x/CAM_A.MOV",
             "/x/song.MP3", "/x/talk.MP4"]
    kb, mics, vids = vsbr.classify_media_files(files)
    assert kb == "/x/Keyboard.WAV"
    assert "/x/MIC1 mix.WAV" in mics and "/x/song.MP3" in mics
    assert "/x/CAM_A.MOV" in vids and "/x/talk.MP4" in vids


def test_classify_media_files_keyboard_keywords_case_insensitive():
    files = ["/x/Mein KEYBOARD Take.wav", "/x/mix.wav", "/x/Cam.mov"]
    kb, mics, vids = vsbr.classify_media_files(files)
    assert "Keyboard".lower() in os.path.basename(kb).lower()
    assert "/x/mix.wav" in mics
    assert "/x/Cam.mov" in vids


def test_compose_report_summary_contains_all_diagnostic_fields():
    # Carl-Gegenreview [P2]: Schluss-Gate darf nicht blind sein —
    # Key-Status, Quelle, Cache, Fingerprint, Run-Kategorie/Message,
    # Handoff müssen alle in der Zusammenfassung landen.
    from core.clip_boundary.models import (
        SmartBoundaryRunResult, BoundaryOutcome)
    from core.credentials import CredentialStatus
    rows = [
        {"peak_id": 0, "old_start_ms": 0, "old_end_ms": 30000,
         "new_start_ms": 5000, "new_end_ms": 25000, "duration_s": 20,
         "score": 0.8, "fallback": False, "reason": "ok"},
        {"peak_id": 1, "old_start_ms": 60000, "old_end_ms": 90000,
         "new_start_ms": None, "new_end_ms": None, "duration_s": None,
         "score": None, "fallback": None, "reason": ""},
    ]
    res = SmartBoundaryRunResult(
        (), BoundaryOutcome.INFRA_FEHLT, "API-Key ungültig", 0, 0)
    lines = vsbr.compose_report_summary(
        rows=rows, t_alone=100.0, t_with=110.0,
        mess_gate_decision="parallel_analysis", run_result=res,
        key_status=CredentialStatus(False, "invalid", ""),
        cache_label="MISS (Fingerprint geändert)",
        source_label="descript",
        fingerprint_str="size=42 mtime_ns=99")
    text = "\n".join(lines)
    assert "Transkriptquelle: descript" in text
    assert "Cache: MISS (Fingerprint geändert)" in text
    assert "size=42 mtime_ns=99" in text
    assert "Key-Status: ✗ Key ungültig" in text
    assert "Run-Kategorie: INFRA_FEHLT" in text
    assert "API-Key ungültig" in text
    assert "Handoff:" in text
    assert "MESS-GATE" in text and "parallel_analysis" in text
    # Näherungs-Hinweis fürs Mess-Gate (Carl [P3]).
    assert "Näherung" in text


def test_format_handoff_summary_includes_counts_and_peaks_with_score():
    from core.clip_boundary.models import (
        SmartBoundaryRunResult, BoundaryOutcome)
    rows = [{"score": 0.8}, {"score": 0.0}, {"score": None}]
    res = SmartBoundaryRunResult((), BoundaryOutcome.OK, "", 1, 1)
    line = vsbr.format_handoff_summary(rows, res)
    assert "Transkript -> Decider -> Bremse -> Sinnabschnitte" in line
    assert "ready=1" in line and "fallback=1" in line
    assert "peaks_mit_score=2/3" in line
