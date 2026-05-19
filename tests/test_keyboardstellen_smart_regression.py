"""Roadmap #3 Schluss-Gate — scharfe Regression (Carl Gate-F).

Beweis statt Versprechen: der Keyboardstellen-/Base-Export ist
UNABHÄNGIG vom Smart-Schalter. TXT ist ffprobe-frei -> deterministischer
Byte-Vergleich Smart on vs off. _build_exporters darf sich durch den
Smart-Schalter NIE ändern und nie einen Sinnabschnitt-Exporter
enthalten. (Volle XML/MP3-Byte-Identität ist strukturell garantiert —
Smart nicht in _build_exporters, läuft erst nach dem Handoff — und
wird zusätzlich durch Max' App-Smoke an echtem Material bestätigt.)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import TXTExporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from gui.workers import _build_exporters  # noqa: E402

_BASE = {"fps": 25, "context_duration_ms": 15000}


def _session(tmp_path, smart_enabled):
    p = PeakCutProject()
    for f in ("KB.wav", "MIC1 mix.wav", "CAM.mp4"):
        (tmp_path / f).write_bytes(b"\x00")
    p.set_files(str(tmp_path / "KB.wav"), [str(tmp_path / "MIC1 mix.wav")],
                [str(tmp_path / "CAM.mp4")])
    p.guest_name = "Hartmut Rosa"
    cfg = dict(_BASE)
    cfg["smart_boundary_enabled"] = smart_enabled
    s = PeakCutSession(p, cfg)
    s.project.export_dir = str(tmp_path / f"exp_{smart_enabled}")
    s.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60000, "context_ms": 15000,
                   "ignored": False},
                  {"index": 1, "position_ms": 120000, "context_ms": 15000,
                   "ignored": False}],
        "video_offsets": []})
    return s


def test_keyboardstellen_txt_byte_identical_smart_on_vs_off(tmp_path):
    on = _session(tmp_path, smart_enabled=True)    # export_dir exp_True
    off = _session(tmp_path, smart_enabled=False)  # export_dir exp_False
    p_on = TXTExporter().export(on)
    p_off = TXTExporter().export(off)
    assert open(p_on, "rb").read() == open(p_off, "rb").read()


def test_build_exporters_invariant_to_smart_flag_no_sinnabschnitt(tmp_path):
    on = _session(tmp_path, smart_enabled=True)
    off = _session(tmp_path, smart_enabled=False)
    names_on = [type(e).__name__ for e in _build_exporters(on)]
    names_off = [type(e).__name__ for e in _build_exporters(off)]
    assert names_on == names_off                      # Schalter ändert nichts
    assert not any("Sinnabschnitt" in n for n in names_on)
    assert "TXTExporter" in names_on and "XMLExporter" in names_on
