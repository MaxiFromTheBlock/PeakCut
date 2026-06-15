"""#76 Task 1 — Playback-Mode-Contracts (Carl-Plan 2026-06-15).

Drei Wiedergabe-Modi key/speak/smart als eingefrorener Vertrag. Reines
Qt-freies Modul; die session.mode-Migration kommt erst mit der Controller-
Integration (Tasks 5-7).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.playback_modes import (  # noqa: E402
    PLAYBACK_MODE_KEY, PLAYBACK_MODE_SPEAK, PLAYBACK_MODE_SMART,
    PLAYBACK_MODE_ORDER, normalize_playback_mode, next_playback_mode,
    label_for_mode,
)
import config  # noqa: E402


def test_constants_and_order():
    assert PLAYBACK_MODE_KEY == "key"
    assert PLAYBACK_MODE_SPEAK == "speak"
    assert PLAYBACK_MODE_SMART == "smart"
    assert PLAYBACK_MODE_ORDER == ("key", "speak", "smart")


def test_normalize_valid_values():
    assert normalize_playback_mode("key") == "key"
    assert normalize_playback_mode("speak") == "speak"
    assert normalize_playback_mode("smart") == "smart"


def test_normalize_invalid_falls_back_to_key():
    assert normalize_playback_mode(None) == "key"
    assert normalize_playback_mode("") == "key"
    assert normalize_playback_mode("bogus") == "key"
    assert normalize_playback_mode(123) == "key"


def test_normalize_is_case_insensitive_and_trims():
    assert normalize_playback_mode(" SPEAK ") == "speak"
    assert normalize_playback_mode("Smart") == "smart"


def test_normalize_maps_legacy_values():
    # Übergang: alte session.mode-Werte sauber überführen.
    assert normalize_playback_mode("keyboard") == "key"
    assert normalize_playback_mode("mic") == "speak"


def test_next_cycles():
    assert next_playback_mode("key") == "speak"
    assert next_playback_mode("speak") == "smart"
    assert next_playback_mode("smart") == "key"


def test_next_normalizes_unknown_first():
    assert next_playback_mode("bogus") == "speak"  # bogus->key->speak


def test_labels():
    assert label_for_mode("key") == "Key"
    assert label_for_mode("speak") == "Speak"
    assert label_for_mode("smart") == "Smart"


def test_config_default_playback_mode():
    assert normalize_playback_mode(config.DEFAULTS["playback_mode"]) == "key"
