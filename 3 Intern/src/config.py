# config.py - Configuration management

import os
import json
import threading

# Config file path
INTERN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(INTERN_DIR, "config.json")

# Default values
DEFAULTS = {
    "threshold_factor": 0.3,
    "min_gap_ms": 12000,
    "preview_duration_ms": 1000,
    "context_duration_ms": 15000,
    "fps": 25,
    "tts_voice": "Anna",
    "lut_path": ""
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
