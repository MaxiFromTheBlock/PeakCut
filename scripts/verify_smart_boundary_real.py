#!/usr/bin/env python3
"""Roadmap #3 Task 10 — Hand-Realprüfung + Mess-Gate.

Echtes Whisper + echtes Claude an einer echten markierten Folge
(z.B. Hartmut Rosa). Druckt pro Drücker: altes ±Kontext-Fenster vs.
neuer Sinnabschnitt, Dauer, Score, Fallback ja/nein, Grund. Misst
zusätzlich die Analyse-Wanduhr OHNE vs. MIT parallel laufendem
Whisper und leitet daraus den finalen `smart_boundary_transcription
_start`-Default ab (Mess-Gate, §6/§7 der Spec).

KEINE App-Logik. Reine Helfer (unten) sind unit-getestet; echte
Engines werden NUR in main() / lazy importiert (Modul bleibt offline
importierbar — kein mlx_whisper/anthropic beim Import).
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Provisorische Mess-Gate-Schwelle: bremst paralleles Whisper die
# Analyse-Wanduhr um > 15 %, kippt der Default auf "nach der Analyse".
_SLOWDOWN_THRESHOLD = 1.15


def build_peak_report(peaks, candidates, context_ms):
    """Reiner Vergleich alt (±context) vs. neu (ClipCandidate.boundary).
    Kandidat fehlt -> new_*/fallback = None. score==0.0 == Fallback."""
    by_id = {c.peak_id: c for c in candidates}
    rows = []
    for p in peaks:
        c = by_id.get(p.index)
        row = {
            "peak_id": p.index,
            "old_start_ms": max(0, p.position_ms - context_ms),
            "old_end_ms": p.position_ms + context_ms,
            "new_start_ms": None,
            "new_end_ms": None,
            "duration_s": None,
            "score": None,
            "fallback": None,
            "reason": "",
        }
        if c is not None:
            row["new_start_ms"] = c.boundary.start_ms
            row["new_end_ms"] = c.boundary.end_ms
            row["duration_s"] = (c.boundary.end_ms - c.boundary.start_ms) // 1000
            row["score"] = c.score
            row["fallback"] = (c.score == 0.0)
            row["reason"] = c.reason
        rows.append(row)
    return rows


def decide_transcription_start(t_alone_s, t_with_whisper_s, *,
                               threshold=_SLOWDOWN_THRESHOLD):
    """Mess-Gate: ohne valide Baseline -> sicher 'parallel_analysis'
    (keine Fehlentscheidung). Sonst kippt nur bei STRIKT spürbarer
    Bremse (> threshold) auf 'after_analysis'."""
    if t_alone_s <= 0:
        return "parallel_analysis"
    # Ratio-Vergleich mit Epsilon: exakt auf der Schwelle bleibt
    # 'parallel' (Float: 100*1.15 == 114.999… -> sonst Fehlkipp).
    if (t_with_whisper_s / t_alone_s) - threshold > 1e-9:
        return "after_analysis"
    return "parallel_analysis"


def format_report_line(r):
    def tc(ms):
        return "-" if ms is None else f"{ms // 60000}:{(ms // 1000) % 60:02d}"
    if r["new_start_ms"] is None:
        return (f"Peak {r['peak_id']:>3}  alt {tc(r['old_start_ms'])}"
                f"–{tc(r['old_end_ms'])}  | KEIN Sinnabschnitt")
    fb = "FALLBACK" if r["fallback"] else "ok"
    return (f"Peak {r['peak_id']:>3}  alt {tc(r['old_start_ms'])}"
            f"–{tc(r['old_end_ms'])}  ->  neu {tc(r['new_start_ms'])}"
            f"–{tc(r['new_end_ms'])}  {r['duration_s']:>3}s  "
            f"score={r['score']}  [{fb}]  {r['reason']}")


def main():  # pragma: no cover — Hand-Werkzeug, echte Engines
    ap = argparse.ArgumentParser(description="Roadmap #3 Real-Prüfung")
    ap.add_argument("project_dir", help="Ordner mit dem echten Rohmaterial")
    ap.add_argument("--report", help="optionaler Report-Pfad (.txt)")
    args = ap.parse_args()

    from core.project import PeakCutProject
    from core.session import PeakCutSession
    from core.analysis_process import run_analysis
    from core.transcription_process import _build_engine, run_transcription
    from core.transcript_archive import (
        transcript_sidecar_path, write_transcript_json, build_transcript_ref)
    from core.transcription import Transcript
    from core.clip_boundary.pipeline import prepare_smart_boundaries
    from core.clip_boundary.decider import ClaudeBoundaryDecider
    import config as appcfg

    cfg = appcfg.load()
    files = [os.path.join(args.project_dir, f)
             for f in os.listdir(args.project_dir)
             if f.lower().endswith((".wav", ".mp4", ".mov", ".mp3"))]
    project = PeakCutProject()
    kb = next((f for f in files if "keyboard" in f.lower()
               or "keys" in f.lower()), files[0])
    mics = [f for f in files if f.endswith((".wav", ".mp3")) and f != kb]
    vids = [f for f in files if f.endswith((".mp4", ".mov"))]
    project.set_files(kb, mics, vids)
    session = PeakCutSession(project, cfg)
    reference = project.get_reference_track() or (mics[0] if mics else kb)

    # --- Mess-Gate: Analyse-Wanduhr ohne vs. mit parallelem Whisper ---
    base = {"keyboard_track": kb, "mic_tracks": mics, "videos": vids,
            "reference_track": reference, "temp_dir": "/tmp",
            "export_dir": project.export_dir, "default_people": [],
            "config": cfg}
    t0 = time.monotonic()
    run_analysis(dict(base))
    t_alone = time.monotonic() - t0

    import threading
    holder = {}

    def _whisper():
        holder["t"] = run_transcription(
            {"audio_path": reference,
             "engine": cfg.get("smart_boundary_whisper_engine"),
             "model": cfg.get("smart_boundary_whisper_model"),
             "language": cfg.get("smart_boundary_language")},
            engine=_build_engine({
                "engine": cfg.get("smart_boundary_whisper_engine")}))

    th = threading.Thread(target=_whisper)
    t1 = time.monotonic()
    th.start()
    results = run_analysis(dict(base))
    t_with = time.monotonic() - t1
    th.join()

    decision = decide_transcription_start(t_alone, t_with)

    # --- Echtes Whisper-Sidecar + Pipeline mit echtem Claude ---
    out = holder.get("t", {})
    if "transcript" in out:
        write_transcript_json(transcript_sidecar_path(project),
                              Transcript.from_dict(out["transcript"]))
        session.transcript_ref = build_transcript_ref(
            project, engine=cfg.get("smart_boundary_whisper_engine"),
            model=cfg.get("smart_boundary_whisper_model"),
            language=cfg.get("smart_boundary_language"),
            audio_path=reference)
    session.load_analysis_results(results)
    prepare_smart_boundaries(
        session,
        ClaudeBoundaryDecider(model=cfg.get("smart_boundary_claude_model")),
        config=cfg)

    rows = build_peak_report(session.peaks, session.clip_candidates,
                             cfg.get("context_duration_ms", 15000))
    lines = [format_report_line(r) for r in rows]
    n_fb = sum(1 for r in rows if r["fallback"])
    summary = [
        "",
        f"Analyse allein:           {t_alone:6.1f}s",
        f"Analyse + paralleles WS:  {t_with:6.1f}s "
        f"(x{t_with / t_alone:.2f})" if t_alone > 0 else "",
        f"MESS-GATE -> smart_boundary_transcription_start = {decision}",
        f"Drücker: {len(rows)} | Fallback: {n_fb} | "
        f"an Fenster-Decke: "
        f"{sum(1 for r in rows if r['new_start_ms'] == 0)}",
    ]
    text = "\n".join(lines + summary)
    print(text)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
