# config.py - Configuration management

import os
import json

# Config file path
INTERN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(INTERN_DIR, "config.json")

# Default values
DEFAULTS = {
    "threshold_factor": 0.4,
    "min_gap_ms": 15000,
    "preview_duration_ms": 1000,
    "context_duration_ms": 15000,
    "fps": 25,
    "tts_voice": "Anna",
    "lut_path": "",
    "lut_recent": []
}

_config = None


def load():
    """Load config from file, create with defaults if missing."""
    global _config

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                _config = json.load(f)
            # Add any missing keys from defaults
            for key, value in DEFAULTS.items():
                if key not in _config:
                    _config[key] = value
        except Exception:
            _config = DEFAULTS.copy()
    else:
        _config = DEFAULTS.copy()
        save()

    return _config


def save():
    """Save current config to file."""
    global _config
    if _config is None:
        _config = DEFAULTS.copy()

    with open(CONFIG_PATH, 'w') as f:
        json.dump(_config, f, indent=2)


def get(key):
    """Get a config value."""
    global _config
    if _config is None:
        load()
    return _config.get(key, DEFAULTS.get(key))


def set(key, value):
    """Set a config value and save."""
    global _config
    if _config is None:
        load()
    _config[key] = value
    save()
