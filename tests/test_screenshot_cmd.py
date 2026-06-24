"""Lock fuer den gemeinsamen Screenshot-ffmpeg-Builder (core/screenshot_cmd).

Desktop ScreenshotWorker UND Web-Engine rufen genau diese Funktion. Die Tests
pinnen Argumente + Grade-Reihenfolge (Helligkeit-lutrgb VOR lut3d). Bricht jemand
die Reihenfolge/Flags, faellt es hier UND in den Web-Byte-Paritaets-Tests auf.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from core.screenshot_cmd import build_screenshot_cmd


def test_cmd_no_filters():
    cmd = build_screenshot_cmd("/v/CamA.mp4", 12.5, "", 0, "/out/s.jpg", ffmpeg="ffmpeg")
    assert cmd == [
        "ffmpeg", "-y", "-ss", "12.5", "-i", "/v/CamA.mp4", "-frames:v", "1",
        "-q:v", "2", "/out/s.jpg",
    ]


def test_cmd_brightness_only():
    # factor = 2**(50/100) = 1.4142..., :.4f -> 1.4142
    cmd = build_screenshot_cmd("/v/CamA.mp4", 3.0, "", 50, "/out/s.jpg", ffmpeg="ffmpeg")
    vf = cmd[cmd.index("-vf") + 1]
    assert vf == "lutrgb=r='clip(val*1.4142,0,255)':g='clip(val*1.4142,0,255)':b='clip(val*1.4142,0,255)'"


def test_cmd_brightness_before_lut(tmp_path):
    lut = tmp_path / "look.cube"
    lut.write_text("LUT_3D_SIZE 2\n")
    cmd = build_screenshot_cmd("/v/CamA.mp4", 1.0, str(lut), -100, "/out/s.jpg", ffmpeg="ffmpeg")
    vf = cmd[cmd.index("-vf") + 1]
    # Helligkeit (factor 0.5) zuerst, dann lut3d — Reihenfolge ist paritaet-kritisch
    assert vf == f"lutrgb=r='clip(val*0.5000,0,255)':g='clip(val*0.5000,0,255)':b='clip(val*0.5000,0,255)',lut3d='{lut}'"


def test_cmd_lut_missing_is_skipped():
    cmd = build_screenshot_cmd("/v/CamA.mp4", 1.0, "/does/not/exist.cube", 0, "/out/s.jpg", ffmpeg="ffmpeg")
    assert "-vf" not in cmd
