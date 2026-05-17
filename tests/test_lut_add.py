import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lib import lut_processor  # noqa: E402
from lib.lut_processor import add_lut_to_library  # noqa: E402

_VALID = """LUT_3D_SIZE 2
0 0 0
1 0 0
0 1 0
1 1 0
0 0 1
1 0 1
0 1 1
1 1 1
"""
_BROKEN = "LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n"  # only 3 of 8


def _w(p, text):
    p.write_text(text)
    return str(p)


def test_valid_cube_is_copied(tmp_path):
    src = _w(tmp_path / "MyLook.cube", _VALID)
    luts = tmp_path / "luts"
    r = add_lut_to_library(src, str(luts))
    assert r.ok and r.reason == "added" and r.filename == "MyLook.cube"
    assert os.path.isfile(luts / "MyLook.cube")


def test_non_cube_rejected(tmp_path):
    src = _w(tmp_path / "notlut.txt", _VALID)
    r = add_lut_to_library(src, str(tmp_path / "luts"))
    assert not r.ok and r.reason == "not_cube"


def test_missing_src_rejected(tmp_path):
    r = add_lut_to_library(str(tmp_path / "nope.cube"), str(tmp_path / "luts"))
    assert not r.ok and r.reason == "not_found"


def test_broken_cube_rejected_not_copied(tmp_path):
    src = _w(tmp_path / "Broken.cube", _BROKEN)
    luts = tmp_path / "luts"
    r = add_lut_to_library(src, str(luts))
    assert not r.ok and r.reason == "invalid"
    assert not (luts / "Broken.cube").exists()


def test_collision_blocks_then_overwrites(tmp_path):
    luts = tmp_path / "luts"
    luts.mkdir()
    (luts / "Look.cube").write_text("OLD")
    src = _w(tmp_path / "Look.cube", _VALID)

    blocked = add_lut_to_library(src, str(luts), overwrite=False)
    assert not blocked.ok and blocked.reason == "exists"
    assert (luts / "Look.cube").read_text() == "OLD"  # untouched

    done = add_lut_to_library(src, str(luts), overwrite=True)
    assert done.ok and done.reason == "overwritten"
    assert (luts / "Look.cube").read_text() == _VALID


def test_self_copy_guard_no_copy_attempt(tmp_path):
    # src IS already the library file -> ok, no copy, file untouched
    luts = tmp_path / "luts"
    luts.mkdir()
    target = luts / "InPlace.cube"
    target.write_text(_VALID)
    r = add_lut_to_library(str(target), str(luts))
    assert r.ok and r.reason == "added" and r.filename == "InPlace.cube"
    assert target.read_text() == _VALID  # still valid, untouched


def test_io_failure_returns_controlled_reason(tmp_path, monkeypatch):
    src = _w(tmp_path / "Look.cube", _VALID)
    luts = tmp_path / "luts"

    def boom_perm(*a, **k):
        raise PermissionError("read-only bundle")

    monkeypatch.setattr(lut_processor.shutil, "copy2", boom_perm)
    r = add_lut_to_library(src, str(luts))
    assert not r.ok and r.reason == "permission"

    def boom_os(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(lut_processor.shutil, "copy2", boom_os)
    r2 = add_lut_to_library(src, str(luts))
    assert not r2.ok and r2.reason == "copy_failed"
