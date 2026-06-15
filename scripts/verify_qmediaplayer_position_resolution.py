#!/usr/bin/env python3
"""#76 Task 4.5 — Drift-Spike: QMediaPlayer-Positions-Auflösung messen.

Minimaler Doppel-QMediaPlayer-Prototyp (NOCH NICHT in ReviewPage integriert).
Spielt Audio + (stummes) Video gemeinsam an echtem Material und misst, wie
gut zwei QMediaPlayer auf macOS/AVFoundation synchron laufen — das legt die
Gate-Schwelle für den echten Controller (Task 5) empirisch fest.

Läuft manuell auf Max' Hardware:
    ./venv311/bin/python scripts/verify_qmediaplayer_position_resolution.py \
        --audio "/pfad/Folge - Mix.wav" --video "/pfad/Jan.mp4" \
        --start-ms 60000 --duration-s 8

Ziel-Schwelle ≤ 40 ms; reportet AVFoundation gröber, wird die Schwelle
empirisch (und dokumentiert) auf den p95-Wert gesetzt.

Die Auswertungs-Helfer unten sind Qt-frei und unit-getestet
(tests/test_qmediaplayer_spike_report.py). Qt wird nur in main() geladen.
"""

import math


def summarize_drift(samples, warmup_ms=500):
    """samples: Liste von {t_ms, audio_ms, video_ms, drift_ms}. Erste
    warmup_ms ignorieren (Anlauf), dann Drift-Statistik."""
    after = [s for s in samples if s["t_ms"] >= warmup_ms]
    drifts = [s["drift_ms"] for s in after]
    return {
        "n": len(samples),
        "n_after_warmup": len(after),
        "max_drift_ms": max(drifts) if drifts else 0,
        "p95_drift_ms": _percentile(drifts, 95) if drifts else 0,
        "mean_drift_ms": (sum(drifts) / len(drifts)) if drifts else 0,
    }


def _percentile(values, pct):
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def suggest_threshold_ms(report, target_ms=40):
    """Ziel-Schwelle halten, wenn p95 darunter; sonst auf nächste 10ms
    aufrunden (dokumentierte empirische Schwelle)."""
    p95 = report["p95_drift_ms"]
    if p95 <= target_ms:
        return target_ms
    return int(math.ceil(p95 / 10.0) * 10)


def median_interval_ms(timestamps_ms):
    """Median-Abstand zwischen positionChanged-Zeitstempeln (Kadenz)."""
    if len(timestamps_ms) < 2:
        return 0
    deltas = sorted(t2 - t1 for t1, t2 in zip(timestamps_ms, timestamps_ms[1:]))
    n = len(deltas)
    mid = n // 2
    return deltas[mid] if n % 2 else (deltas[mid - 1] + deltas[mid]) / 2


def _format_report(report, audio_cadence, video_cadence, start_latency_ms,
                   target_ms=40):
    thr = suggest_threshold_ms(report, target_ms)
    ok = report["p95_drift_ms"] <= target_ms
    lines = [
        "=== QMediaPlayer Drift-Spike ===",
        f"Samples: {report['n']} (nach {0}-Warmup: {report['n_after_warmup']})",
        f"Start-Latenz bis beide ready+playing: {start_latency_ms} ms",
        f"positionChanged-Kadenz: Audio ~{audio_cadence} ms / Video ~{video_cadence} ms",
        f"Drift (nach Warmup): max {report['max_drift_ms']} ms, "
        f"p95 {report['p95_drift_ms']} ms, mean {report['mean_drift_ms']:.1f} ms",
        f"Ziel <= {target_ms} ms: {'ERFÜLLT' if ok else 'NICHT erfüllt'}",
        f"=> empfohlene Controller-Schwelle: {thr} ms",
    ]
    return "\n".join(lines)


def main(argv=None):
    import argparse
    import os
    import sys
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl, QTimer
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--start-ms", type=int, default=0)
    ap.add_argument("--duration-s", type=float, default=8.0)
    ap.add_argument("--warmup-ms", type=int, default=500)
    ap.add_argument("--target-ms", type=int, default=40)
    args = ap.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)

    a_out = QAudioOutput()
    a_player = QMediaPlayer()
    a_player.setAudioOutput(a_out)

    v_out = QAudioOutput()
    v_out.setMuted(True)
    v_player = QMediaPlayer()
    v_player.setAudioOutput(v_out)
    v_sink = QVideoSink()
    v_player.setVideoOutput(v_sink)

    a_player.setSource(QUrl.fromLocalFile(os.path.abspath(args.audio)))
    v_player.setSource(QUrl.fromLocalFile(os.path.abspath(args.video)))

    a_ts, v_ts = [], []
    t0 = time.monotonic()
    a_player.positionChanged.connect(
        lambda _p: a_ts.append((time.monotonic() - t0) * 1000))
    v_player.positionChanged.connect(
        lambda _p: v_ts.append((time.monotonic() - t0) * 1000))

    READY = (QMediaPlayer.MediaStatus.LoadedMedia,
             QMediaPlayer.MediaStatus.BufferedMedia)

    def _ready(p):
        return p.mediaStatus() in READY

    # Auf Readiness beider Player warten (max 5s).
    deadline = time.monotonic() + 5.0
    while not (_ready(a_player) and _ready(v_player)):
        app.processEvents()
        if time.monotonic() > deadline:
            print("FEHLER: Medien nicht innerhalb 5s ready.")
            return 2
        time.sleep(0.01)

    a_player.setPosition(args.start_ms)
    v_player.setPosition(args.start_ms)
    a_player.play()
    v_player.play()
    start_latency_ms = int((time.monotonic() - t0) * 1000)

    samples = []

    def sample():
        t = (time.monotonic() - t0) * 1000 - start_latency_ms
        ap_ms, vp_ms = a_player.position(), v_player.position()
        samples.append({"t_ms": t, "audio_ms": ap_ms, "video_ms": vp_ms,
                        "drift_ms": abs(ap_ms - vp_ms)})

    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(sample)
    timer.start()

    end = time.monotonic() + args.duration_s
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    timer.stop()
    a_player.stop()
    v_player.stop()

    report = summarize_drift(samples, args.warmup_ms)
    print(_format_report(report, int(median_interval_ms(a_ts)),
                         int(median_interval_ms(v_ts)), start_latency_ms,
                         args.target_ms))
    return 0 if report["p95_drift_ms"] <= args.target_ms else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
