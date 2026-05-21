"""Unit-Tests für scripts/verify_audio_routing_real.py — reine
Helfer-Funktionen. Das eigentliche Real-Skript läuft NICHT in CI
(braucht reale Audiodaten + ffmpeg + .peakcut-Akte)."""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from verify_audio_routing_real import build_routing_report  # noqa: E402


class _StubProject:
    def __init__(self, mic_tracks):
        self.mic_tracks = list(mic_tracks)


def test_build_routing_report_with_mix_in_mic_list():
    """HM-Standardfall: Mix in mic_tracks, paar Peaks aktiv, einer
    ignored. Report soll Mix als Quelle für aktive Peaks ausweisen
    und den ignorierten korrekt als skipped markieren."""
    p = _StubProject(
        ["/x/MIC1.wav", "/x/MIC2.wav", "/x/Sheila Mix.mp3"]
    )
    peaks = [
        {"index": 0, "position_ms": 60_000, "ignored": False},
        {"index": 1, "position_ms": 90_000, "ignored": True},
        {"index": 2, "position_ms": 120_000, "ignored": False},
    ]
    report = build_routing_report(p, peaks)

    assert report["mix"] == "Sheila Mix.mp3"
    assert report["real_mics"] == ["MIC1.wav", "MIC2.wav"]
    assert report["all_mic_tracks"] == [
        "MIC1.wav",
        "MIC2.wav",
        "Sheila Mix.mp3",
    ]
    sources = [row["source"] for row in report["rows"]]
    assert sources == ["mix_only", "skipped (peak ignored)", "mix_only"]


def test_build_routing_report_without_mix():
    """Produktion ohne Mix-Datei → Mics werden overlayed."""
    p = _StubProject(["/x/MIC1.wav", "/x/MIC2.wav"])
    peaks = [{"index": 0, "position_ms": 60_000, "ignored": False}]
    report = build_routing_report(p, peaks)

    assert report["mix"] is None
    assert report["real_mics"] == ["MIC1.wav", "MIC2.wav"]
    assert report["rows"][0]["source"] == "mic_overlay"


def test_build_routing_report_no_audio_source():
    """Edge-Case: gar keine Mics in der Liste."""
    p = _StubProject([])
    peaks = [{"index": 0, "position_ms": 60_000, "ignored": False}]
    report = build_routing_report(p, peaks)

    assert report["mix"] is None
    assert report["real_mics"] == []
    assert report["rows"][0]["source"] == "none (no audio source)"


def test_build_routing_report_with_only_mix():
    """Edge-Case: nur eine Mix-Datei, keine echten Mics. Quelle bleibt
    mix_only (Mix allein klingt synchron, kein Overlay-Risiko)."""
    p = _StubProject(["/x/Sheila Mix.mp3"])
    peaks = [{"index": 0, "position_ms": 60_000, "ignored": False}]
    report = build_routing_report(p, peaks)

    assert report["mix"] == "Sheila Mix.mp3"
    assert report["real_mics"] == []
    assert report["rows"][0]["source"] == "mix_only"


def test_build_routing_report_empty_peaks():
    """Edge-Case: kein einziger Peak in der Akte."""
    p = _StubProject(["/x/MIC1.wav"])
    report = build_routing_report(p, [])

    assert report["rows"] == []
