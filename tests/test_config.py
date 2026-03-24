"""Tests for config.py — thread-safe JSON config management."""
import json
import os
import threading

import pytest

import config


@pytest.fixture(autouse=True)
def reset_config(tmp_path, monkeypatch):
    """Reset config state and redirect to temp file for each test."""
    config._config = None
    config_path = str(tmp_path / "config.json")
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    yield
    config._config = None


class TestLoad:

    def test_creates_config_if_missing(self):
        cfg = config.load()
        assert cfg == config.DEFAULTS
        assert os.path.exists(config.CONFIG_PATH)

    def test_loads_existing_config(self):
        custom = {"threshold_factor": 0.5, "min_gap_ms": 8000}
        with open(config.CONFIG_PATH, "w") as f:
            json.dump(custom, f)

        cfg = config.load()
        assert cfg["threshold_factor"] == 0.5
        assert cfg["min_gap_ms"] == 8000

    def test_fills_missing_keys_with_defaults(self):
        with open(config.CONFIG_PATH, "w") as f:
            json.dump({"threshold_factor": 0.5}, f)

        cfg = config.load()
        assert cfg["threshold_factor"] == 0.5
        assert cfg["min_gap_ms"] == config.DEFAULTS["min_gap_ms"]
        assert cfg["fps"] == config.DEFAULTS["fps"]

    def test_corrupt_json_falls_back_to_defaults(self):
        with open(config.CONFIG_PATH, "w") as f:
            f.write("{broken json!!!")

        cfg = config.load()
        assert cfg == config.DEFAULTS


class TestGetSet:

    def test_get_returns_default_before_load(self):
        assert config.get("fps") == 25

    def test_set_value_persists(self):
        config.load()
        config.set_value("fps", 30)
        assert config.get("fps") == 30

        # Verify it was written to disk
        with open(config.CONFIG_PATH) as f:
            on_disk = json.load(f)
        assert on_disk["fps"] == 30

    def test_set_value_before_load(self):
        config.set_value("fps", 30)
        assert config.get("fps") == 30


class TestDefaults:

    def test_defaults_match_current_values(self):
        """Ensure DEFAULTS stay in sync with the documented config."""
        assert config.DEFAULTS["threshold_factor"] == 0.3
        assert config.DEFAULTS["min_gap_ms"] == 12000
        assert config.DEFAULTS["context_duration_ms"] == 15000
        assert config.DEFAULTS["fps"] == 25


class TestThreadSafety:

    def test_concurrent_reads(self):
        config.load()
        results = []

        def read_config():
            results.append(config.get("fps"))

        threads = [threading.Thread(target=read_config) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 25 for r in results)
        assert len(results) == 20
