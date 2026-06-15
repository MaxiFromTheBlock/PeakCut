"""#76 Task 4.5 — reine Report-Helfer des Drift-Spikes (Carl-Plan 2026-06-15).

Der Spike selbst (QApplication + 2 QMediaPlayer an echtem Material) läuft
manuell auf Max' Hardware und legt die Gate-Schwelle fest. Hier nur die
Qt-freie Auswertung: Warmup-Filter, Drift-Statistik, Schwellen-Vorschlag.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from verify_qmediaplayer_position_resolution import (  # noqa: E402
    summarize_drift, suggest_threshold_ms, median_interval_ms,
)


def _s(t, drift):
    return {"t_ms": t, "audio_ms": t, "video_ms": t + drift, "drift_ms": abs(drift)}


def test_warmup_samples_excluded():
    samples = [_s(0, 500), _s(200, 400), _s(600, 10), _s(800, 20)]
    rep = summarize_drift(samples, warmup_ms=500)
    assert rep["n"] == 4
    assert rep["n_after_warmup"] == 2          # nur t>=500
    assert rep["max_drift_ms"] == 20           # 500/400 (Warmup) ignoriert


def test_p95_and_mean():
    samples = [_s(t, 10) for t in range(500, 1500, 100)]  # alle drift 10
    rep = summarize_drift(samples, warmup_ms=500)
    assert rep["max_drift_ms"] == 10
    assert rep["p95_drift_ms"] == 10
    assert rep["mean_drift_ms"] == 10


def test_empty_after_warmup_is_safe():
    rep = summarize_drift([_s(0, 5)], warmup_ms=500)
    assert rep["n_after_warmup"] == 0
    assert rep["max_drift_ms"] == 0 and rep["p95_drift_ms"] == 0


def test_suggest_threshold_keeps_target_when_p95_under():
    assert suggest_threshold_ms({"p95_drift_ms": 25}, target_ms=40) == 40


def test_suggest_threshold_rounds_up_when_p95_over():
    assert suggest_threshold_ms({"p95_drift_ms": 63}, target_ms=40) == 70
    assert suggest_threshold_ms({"p95_drift_ms": 80}, target_ms=40) == 80


def test_median_interval():
    assert median_interval_ms([0, 100, 200, 300]) == 100
    assert median_interval_ms([0]) == 0
