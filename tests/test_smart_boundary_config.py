"""Roadmap #3 Task 1 — Config + Notbremse (Carl-Finalplan).

Nur Defaults + Notbremse-Flag. Kein Worker/Pipeline (spätere Tasks);
die "Smart-off deaktiviert Stufe A/B"-Wirkung wird dort getestet, wo
Stufe A/B existieren.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402

_EXPECTED = {
    "smart_boundary_enabled": True,
    "smart_boundary_transcription_start": "parallel_analysis",
    "smart_boundary_transcript_wait_s": 10,
    "smart_boundary_search_before_ms": 180_000,
    "smart_boundary_search_after_ms": 60_000,
    "smart_boundary_min_duration_ms": 12_000,
    "smart_boundary_max_duration_ms": 180_000,
    "smart_boundary_confidence_threshold": 0.5,
    "smart_boundary_fallback_before_ms": 45_000,
    "smart_boundary_fallback_after_ms": 30_000,
    "smart_boundary_sentence_gap_ms": 900,
    "smart_boundary_whisper_engine": "mlx-whisper",
    "smart_boundary_whisper_model": "large-v3-turbo",
    "smart_boundary_language": "de",
}


def test_smart_boundary_defaults_present_and_exact():
    for key, val in _EXPECTED.items():
        assert key in config.DEFAULTS, f"fehlt in DEFAULTS: {key}"
        assert config.DEFAULTS[key] == val, key
        assert config.get(key) == val, key


def test_notbremse_flag_default_on_and_overridable():
    assert config.DEFAULTS["smart_boundary_enabled"] is True
    config.set_value("smart_boundary_enabled", False)
    try:
        assert config.get("smart_boundary_enabled") is False
    finally:
        config.set_value("smart_boundary_enabled", True)
