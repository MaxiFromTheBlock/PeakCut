"""HC-4 Task 5 / Gate F — Export-Identität.

Das „bit-identisch"-Äquivalent: speichern → laden → neues export_dir →
erneut exportieren muss byte-gleich sein. Geprüft am produktiven,
regression-gesicherten Keyboardstellen-XMLExporter.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.folgenschnitt_models import ActivityFrame  # noqa: E402
from core.exporters import XMLExporter  # noqa: E402
from core.project_archive import (  # noqa: E402
    save_project_archive, load_project_archive)

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def _orig_session(tmp):
    kb = _touch(tmp / "Mat" / "P8" / "KB.wav")
    m1 = _touch(tmp / "Mat" / "P8" / "MIC1.wav")
    cam = _touch(tmp / "Mat" / "CAM_A.mp4")
    proj = PeakCutProject()
    proj.set_files(kb, [m1], [cam])
    proj.guest_name = "Hartmut Rosa"
    s = PeakCutSession(proj, dict(_CFG))
    p0 = Peak(0, 60000, context_ms=15000)
    p0.set_in_point(50000)
    p0.set_out_point(80000)
    p1 = Peak(1, 120000, context_ms=15000)  # aktiv
    s.peaks = [p0, p1]
    s.video_offsets = [("CAM_A.mp4", "-00:00:02:00")]
    s.speaker_activity = [
        ActivityFrame(0, 200, {"mic_1": -20.0}, {"mic_1": -50.0}, 20.0,
                      "mic_1", "mic_1", 1.0)]
    return s, tmp / "Mat"


def _export_xml_bytes(session, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    session.project.export_dir = str(export_dir)
    with patch("core.exporters._probe_video_info", return_value=(1920, 1080)), \
         patch("core.exporters._probe_audio_info", return_value=(48000, 16, 2)):
        path = XMLExporter().export(session)
    assert path and os.path.isfile(path)
    with open(path, "rb") as f:
        return f.read()


def test_keyboardstellen_xml_byte_identical_after_save_load(tmp_path):
    s, mat_root = _orig_session(tmp_path)
    before = _export_xml_bytes(s, tmp_path / "exp_orig")

    save_project_archive(s)
    loaded = load_project_archive(str(mat_root), dict(_CFG))
    after = _export_xml_bytes(loaded, tmp_path / "exp_loaded")

    assert before == after, (
        "Keyboardstellen-XML nach Save/Load NICHT byte-identisch — "
        "Reload verändert den Export")
