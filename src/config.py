# config.py - Configuration management

import json
import os
import threading

from utils import DATA_DIR

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

# Default values
DEFAULTS = {
    "threshold_factor": 0.3,
    "min_gap_ms": 12000,
    "preview_duration_ms": 1000,
    "context_duration_ms": 15000,
    "fps": 25,
    "tts_voice": "Anna",
    "lut_path": "",
    # Roadmap #3 — Smarte Clip-Grenzen (provisorisch, kalibrierbar).
    # smart_boundary_enabled=False = Notbremse: Stufe A+B laufen nicht.
    "smart_boundary_enabled": True,
    "smart_boundary_transcription_start": "parallel_analysis",
    "smart_boundary_transcript_wait_s": 10,
    "smart_boundary_search_before_ms": 180000,
    "smart_boundary_search_after_ms": 60000,
    "smart_boundary_min_duration_ms": 12000,
    "smart_boundary_max_duration_ms": 180000,
    "smart_boundary_confidence_threshold": 0.5,
    "smart_boundary_fallback_before_ms": 45000,
    "smart_boundary_fallback_after_ms": 30000,
    "smart_boundary_sentence_gap_ms": 900,
    "smart_boundary_snap_tolerance_ms": 1500,
    "smart_boundary_claude_model": "claude-opus-4-7",
    "smart_boundary_whisper_engine": "mlx-whisper",
    "smart_boundary_whisper_model": "large-v3-turbo",
    "smart_boundary_language": "de"
}

_config = None
_lock = threading.Lock()


def load():
    """Load config from file, create with defaults if missing."""
    global _config

    with _lock:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    _config = json.load(f)
                for key, value in DEFAULTS.items():
                    if key not in _config:
                        _config[key] = value
            except (json.JSONDecodeError, ValueError, KeyError):
                import sys
                print(f"Warning: config.json corrupt, using defaults", file=sys.stderr)
                _config = DEFAULTS.copy()
        else:
            _config = DEFAULTS.copy()
            _save_unlocked()

        return _config.copy()


def save():
    """Save current config to file."""
    with _lock:
        _save_unlocked()


def _save_unlocked():
    """Save without acquiring lock (caller must hold _lock)."""
    global _config
    if _config is None:
        _config = DEFAULTS.copy()

    with open(CONFIG_PATH, 'w') as f:
        json.dump(_config, f, indent=2)


def get(key):
    """Get a config value (thread-safe)."""
    global _config
    if _config is None:
        load()
    with _lock:
        return _config.get(key, DEFAULTS.get(key))


def set_value(key, value):
    """Set a config value and save (thread-safe)."""
    global _config
    with _lock:
        if _config is None:
            _config = DEFAULTS.copy()
        _config[key] = value
        _save_unlocked()
