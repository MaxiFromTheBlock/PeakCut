"""DATA-1 — save_project_archive + write_transcript_json schreiben atomar.

Beide Schreib-Stellen müssen über core.atomic_io laufen, damit ein Abbruch
mitten im Schreiben die bestehende Datei NIE truncieren kann.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import atomic_io  # noqa: E402
from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.project_archive import (  # noqa: E402
    save_project_archive, ARCHIVE_DIR, ARCHIVE_FILE,
)
from core import transcript_archive  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def _session(tmp):
    kb = _touch(tmp / "Mat" / "P8" / "KB.wav")
    m1 = _touch(tmp / "Mat" / "P8" / "MIC1.wav")
    cam = _touch(tmp / "Mat" / "CAM_A.mp4")
    proj = PeakCutProject()
    proj.set_files(kb, [m1], [cam])
    proj.guest_name = "Hartmut Rosa"
    s = PeakCutSession(proj, dict(_CFG))
    p0 = Peak(0, 60000, context_ms=15000)
    s.peaks = [p0]
    return s


def test_save_routes_through_atomic_io(tmp_path, monkeypatch):
    s = _session(tmp_path)
    calls = []
    real = atomic_io.write_json_atomic

    def spy(path, payload, **kw):
        calls.append(path)
        return real(path, payload, **kw)

    monkeypatch.setattr("core.atomic_io.write_json_atomic", spy)
    save_project_archive(s)
    assert any(c.endswith(os.path.join(ARCHIVE_DIR, ARCHIVE_FILE)) for c in calls)


def test_save_leaves_no_tmp_file(tmp_path):
    s = _session(tmp_path)
    path = save_project_archive(s)
    archive_dir = os.path.dirname(path)
    leftovers = [f for f in os.listdir(archive_dir) if f.endswith(".tmp")]
    assert leftovers == []


def test_failed_save_preserves_existing_archive(tmp_path, monkeypatch):
    s = _session(tmp_path)
    path = save_project_archive(s)
    before = open(path, "rb").read()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("core.atomic_io.write_json_atomic", boom)
    with pytest.raises(OSError):
        save_project_archive(s)

    assert open(path, "rb").read() == before
    archive_dir = os.path.dirname(path)
    assert [f for f in os.listdir(archive_dir) if f.endswith(".tmp")] == []


def test_write_transcript_json_routes_through_atomic_io(tmp_path, monkeypatch):
    calls = []
    real = atomic_io.write_json_atomic

    def spy(path, payload, **kw):
        calls.append(path)
        return real(path, payload, **kw)

    monkeypatch.setattr("core.atomic_io.write_json_atomic", spy)

    class _T:
        def to_dict(self):
            return {"segments": []}

    target = str(tmp_path / ".peakcut" / "transcript.json")
    transcript_archive.write_transcript_json(target, _T())
    assert calls == [target]
    assert json.loads(open(target).read()) == {"segments": []}
