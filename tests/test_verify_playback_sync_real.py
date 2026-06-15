"""#76 Task 9 — reine Helfer des echten Drift-Messskripts (Carl-Plan).

Das Skript fährt den ECHTEN ReviewPlaybackController an echtem Material
(Max' Hardware, Gate I). Hier nur die Qt-freie Pass/Fail- + Format-Logik.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from verify_playback_sync_real import sync_passes, format_sync_report  # noqa: E402


def test_sync_passes_under_threshold():
    assert sync_passes({"max_drift_ms": 30}, 40) is True
    assert sync_passes({"max_drift_ms": 40}, 40) is True


def test_sync_fails_over_threshold():
    assert sync_passes({"max_drift_ms": 55}, 40) is False


def test_format_contains_verdict_and_numbers():
    rep = {"n_after_warmup": 50, "max_drift_ms": 30, "p95_drift_ms": 20}
    out = format_sync_report(rep, 40, 3)
    assert "BESTANDEN" in out and "30" in out and "3" in out
    out2 = format_sync_report(
        {"n_after_warmup": 50, "max_drift_ms": 55, "p95_drift_ms": 50}, 40, 9)
    assert "NICHT bestanden" in out2
