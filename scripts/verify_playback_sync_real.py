#!/usr/bin/env python3
"""#76 Task 9 — echtes Drift-Messskript (Gate I).

Fährt den ECHTEN ReviewPlaybackController an einer echten .peakcut-Akte und
misst die Ton-gegen-Bild-Drift über die Cliplänge. Akzeptanz: max Drift nach
Warmup <= Schwelle (aus dem Spike / config). Läuft manuell auf Max' Hardware:

    ./venv311/bin/python scripts/verify_playback_sync_real.py \
        --archive "/pfad/zur/Episode" --mode speak --peak-index 0

Die Qt-freie Pass/Fail- + Format-Logik ist unit-getestet
(tests/test_verify_playback_sync_real.py). Die Drift-Statistik wird aus dem
Spike-Modul wiederverwendet (kein Duplikat).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # Geschwister-Import (Spike-Helfer)

from verify_qmediaplayer_position_resolution import summarize_drift  # noqa: E402


def sync_passes(report, threshold_ms):
    return report["max_drift_ms"] <= threshold_ms


def format_sync_report(report, threshold_ms, corrections):
    ok = sync_passes(report, threshold_ms)
    return "\n".join([
        "=== Playback-Sync (echter Controller, echtes Material) ===",
        f"Samples nach Warmup: {report['n_after_warmup']}",
        f"Drift: max {report['max_drift_ms']} ms, p95 {report['p95_drift_ms']} ms",
        f"Korrekturen (Drift > Schwelle): {corrections}",
        f"Schwelle {threshold_ms} ms: {'BESTANDEN' if ok else 'NICHT bestanden'}",
    ])


def main(argv=None):
    import argparse
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

    import config
    from PyQt6.QtWidgets import QApplication
    from core.project_archive import load_project_archive
    from core.playback_windows import build_playback_window
    from core.playback_audio_source import resolve_playback_audio_source
    from gui.video_preview_peak import PeakVideoPreview
    from gui.review_playback_controller import ReviewPlaybackController

    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--peak-index", type=int, default=0)
    ap.add_argument("--mode", default="speak", choices=["key", "speak", "smart"])
    ap.add_argument("--duration-s", type=float, default=8.0)
    ap.add_argument("--warmup-ms", type=int, default=500)
    ap.add_argument("--threshold-ms", type=int, default=None)
    args = ap.parse_args(argv)

    threshold = (args.threshold_ms if args.threshold_ms is not None
                 else config.DEFAULTS["playback_drift_tolerance_ms"])

    app = QApplication.instance() or QApplication(sys.argv)

    session = load_project_archive(args.archive, config.DEFAULTS)
    window = build_playback_window(session, args.mode, args.peak_index)
    if window.disabled:
        print("Fenster nicht abspielbar:", window.disabled_reason)
        return 2
    source = resolve_playback_audio_source(session, window)
    if source.disabled:
        print("Keine Audioquelle:", source.disabled_reason)
        return 2

    pv = PeakVideoPreview()
    pv.set_videos(list(session.project.videos))
    pv.set_session(session)
    ctrl = ReviewPlaybackController(pv, tolerance_ms=threshold)

    samples = []
    corrections = {"n": 0}
    t0 = time.monotonic()

    def on_drift(d):
        samples.append({"t_ms": (time.monotonic() - t0) * 1000, "drift_ms": d})
        if d > threshold:
            corrections["n"] += 1

    ctrl.drift_updated.connect(on_drift)
    done = {"f": False}
    ctrl.finished.connect(lambda: done.__setitem__("f", True))
    ctrl.play(window, source)

    end = time.monotonic() + args.duration_s
    while time.monotonic() < end and not done["f"]:
        app.processEvents()
        time.sleep(0.01)
    ctrl.stop()

    report = summarize_drift(samples, args.warmup_ms)
    print(format_sync_report(report, threshold, corrections["n"]))
    return 0 if sync_passes(report, threshold) else 1


if __name__ == "__main__":
    sys.exit(main())
