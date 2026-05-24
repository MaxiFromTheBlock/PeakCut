"""Roadmap #3 Task 7 — Sinnabschnitte-Exporter (Carl).

Strikt getrennter Zusatz-Export: eigene Dateien, eigener Codepfad,
NICHT in _build_exporters / exported / vor .peakcut_done, kein Touch
am Keyboardstellen-Exporter. Nutzt ClipCandidate.boundary.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.sinnabschnitt_exporter import (  # noqa: E402
    SinnabschnittTXTExporter, SinnabschnittXMLExporter,
    _select_audio_reference)
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, PROPOSED, DISCARDED)
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _session(tmp_path, cands):
    p = PeakCutProject()
    p.set_files(str(tmp_path / "KB.wav"), [str(tmp_path / "MIC1 mix.wav")],
                [str(tmp_path / "CAM.mp4")])
    for f in ("KB.wav", "MIC1 mix.wav", "CAM.mp4"):
        (tmp_path / f).write_bytes(b"\x00")
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.project.export_dir = str(tmp_path / "export")
    s.clip_candidates = cands
    return s


def _cands():
    return [
        ClipCandidate(peak_id=0, boundary=ClipBoundary(100000, 160000),
                      status=PROPOSED,
                      transcript_excerpt="… Frage … [PEAK] … Pointe …",
                      reason="Frage bis Pointe", score=0.82),
        ClipCandidate(peak_id=1, boundary=ClipBoundary(300000, 330000),
                      status=DISCARDED, reason="ignoriert"),
    ]


def _session_with_mics(tmp_path, mic_names):
    p = PeakCutProject()
    for name in ("KB.wav", "CAM.mp4", *mic_names):
        (tmp_path / name).write_bytes(b"\x00")
    p.set_files(
        str(tmp_path / "KB.wav"),
        [str(tmp_path / name) for name in mic_names],
        [str(tmp_path / "CAM.mp4")],
    )
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.project.export_dir = str(tmp_path / "export")
    return s


def test_audio_reference_uses_mix_via_audio_routing(tmp_path):
    s = _session_with_mics(
        tmp_path, ["MIC1.wav", "Sheila Mix.mp3", "MIC2.wav"])

    ref = _select_audio_reference(s)

    assert os.path.basename(ref) == "Sheila Mix.mp3"


def test_audio_reference_falls_back_to_first_real_mic(tmp_path):
    s = _session_with_mics(tmp_path, ["MIC1.wav", "MIC2.wav"])

    ref = _select_audio_reference(s)

    assert os.path.basename(ref) == "MIC1.wav"


def test_audio_reference_falls_back_to_default_without_audio(tmp_path):
    s = _session_with_mics(tmp_path, [])

    assert _select_audio_reference(s) == "audio.wav"


def test_txt_has_all_required_fields_and_skips_discarded(tmp_path):
    s = _session(tmp_path, _cands())
    path = SinnabschnittTXTExporter().export(s)
    assert os.path.basename(path) == "Sinnabschnitte - Hartmut Rosa.txt"
    txt = open(path, encoding="utf-8").read()
    assert "0" in txt                       # peak-id
    assert "00:01:40:00" in txt             # start 100000ms @25fps
    assert "00:02:40:00" in txt             # end 160000ms
    assert "60" in txt                      # Dauer (s)
    assert "0.82" in txt                    # confidence
    assert "Frage bis Pointe" in txt        # reason
    assert "[PEAK]" in txt                  # excerpt
    assert "ignoriert" not in txt           # discarded übersprungen


def test_xml_uses_smart_boundary_valid_xmeml(tmp_path):
    s = _session(tmp_path, _cands())
    path = SinnabschnittXMLExporter().export(s)
    assert os.path.basename(path) == "Sinnabschnitte - Hartmut Rosa.xml"
    xml = open(path, encoding="utf-8").read()
    assert xml.startswith("<?xml")
    assert "<xmeml" in xml
    # Smart-Boundary in Frames (100000ms@25fps = 2500, 160000 = 4000)
    assert "2500" in xml and "4000" in xml
    assert "330000" not in xml              # discarded nicht enthalten
    # Carl Gate-E P2: echte file://-URL als pathurl, nicht Basename
    assert "<pathurl>file://" in xml


def test_only_writes_own_files_never_keyboardstellen(tmp_path):
    s = _session(tmp_path, _cands())
    SinnabschnittTXTExporter().export(s)
    SinnabschnittXMLExporter().export(s)
    files = sorted(os.listdir(s.project.export_dir))
    assert files == ["Sinnabschnitte - Hartmut Rosa.txt",
                     "Sinnabschnitte - Hartmut Rosa.xml"]
    assert not any(f.startswith("Keyboardstellen") for f in files)


def test_bootstrap_only_no_smart_writes_nothing(tmp_path):
    # Schritt-1-Realbefund: ohne Transkript bleiben alle Kandidaten
    # Bootstrap (proposed, score=None). KEINE Sinnabschnitte-Datei als
    # leeres Nebenprodukt (Carl-Checkliste). Konsistent zur Gate-G-
    # Vorschau-Semantik: score is not None == smarter Abschnitt.
    s = _session(tmp_path, [
        ClipCandidate(peak_id=0, boundary=ClipBoundary(105000, 135000),
                      status=PROPOSED, score=None),
        ClipCandidate(peak_id=1, boundary=ClipBoundary(285000, 315000),
                      status=PROPOSED, score=None)])
    assert SinnabschnittTXTExporter().export(s) == ""
    assert SinnabschnittXMLExporter().export(s) == ""
    assert not os.path.isdir(s.project.export_dir) or \
        os.listdir(s.project.export_dir) == []


def test_fallback_score_zero_still_exported(tmp_path):
    # Fallback (score=0.0) ist ECHTES Smart-Ergebnis -> sichtbar.
    s = _session(tmp_path, [ClipCandidate(
        peak_id=0, boundary=ClipBoundary(100000, 160000), status=PROPOSED,
        reason="Rückfall", score=0.0)])
    assert SinnabschnittTXTExporter().export(s).endswith(".txt")


def test_empty_or_all_discarded_writes_nothing(tmp_path):
    s = _session(tmp_path, [ClipCandidate(
        peak_id=0, boundary=ClipBoundary(1, 2), status=DISCARDED)])
    assert SinnabschnittTXTExporter().export(s) == ""
    assert SinnabschnittXMLExporter().export(s) == ""
    assert not os.path.isdir(s.project.export_dir) or \
        os.listdir(s.project.export_dir) == []


def test_exporter_not_in_build_exporters(tmp_path):
    from gui.workers import _build_exporters
    s = _session(tmp_path, _cands())
    names = [type(e).__name__ for e in _build_exporters(s)]
    assert not any("Sinnabschnitt" in n for n in names)
    assert "XMLExporter" in names           # Keyboardstellen unverändert da
