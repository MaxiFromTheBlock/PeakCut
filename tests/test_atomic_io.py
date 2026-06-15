"""DATA-1 — atomarer JSON-Schreiber (Carl-Plan 2026-06-15).

Ziel: project.json darf bei einem Abbruch mitten im Schreiben NIE
truncieren. tmp im selben Ordner -> os.replace -> alte Datei bleibt
bis zum atomaren Tausch byte-identisch.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.atomic_io import write_json_atomic  # noqa: E402


def test_write_produces_valid_json(tmp_path):
    p = tmp_path / "out.json"
    write_json_atomic(str(p), {"a": 1, "b": "x"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1, "b": "x"}


def test_no_tmp_file_remains_after_success(tmp_path):
    p = tmp_path / "out.json"
    write_json_atomic(str(p), {"a": 1})
    leftovers = [f for f in os.listdir(tmp_path) if f != "out.json"]
    assert leftovers == []


def test_failed_write_leaves_existing_file_byte_identical(tmp_path):
    p = tmp_path / "out.json"
    write_json_atomic(str(p), {"good": 1})
    before = p.read_bytes()

    # object() ist nicht JSON-serialisierbar -> json.dump wirft mitten im
    # Schreiben. Die alte Datei muss unangetastet bleiben.
    with pytest.raises(TypeError):
        write_json_atomic(str(p), {"bad": object()})

    assert p.read_bytes() == before
    leftovers = [f for f in os.listdir(tmp_path) if f != "out.json"]
    assert leftovers == []


def test_indent_and_ensure_ascii_respected(tmp_path):
    p = tmp_path / "out.json"
    write_json_atomic(str(p), {"ä": "ö"}, indent=2, ensure_ascii=False)
    text = p.read_text(encoding="utf-8")
    assert "ä" in text and "ö" in text
    assert "\n" in text  # indent erzeugt Zeilenumbrüche


def test_overwrites_existing_file(tmp_path):
    p = tmp_path / "out.json"
    write_json_atomic(str(p), {"v": 1})
    write_json_atomic(str(p), {"v": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}
