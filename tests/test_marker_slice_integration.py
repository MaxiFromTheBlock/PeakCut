"""Slice "Marker + Vergleichbarkeit" — Task 5 (Safety/Integration, Carl).

Der eigentliche Beweis der Vergleichbarkeit: Keyboardstellen-XML
("Keyboardstellen raw") und Sinnabschnitt-XML ("Keyboardstellen smart")
tragen für gemeinsame Stellen DIESELBEN Marker-Nummern — obwohl die eine
über Peaks und die andere über Smart-Kandidaten läuft (candidate.peak_id
ist um ignorierte Peaks versetzt).

Die übrigen Task-5-Punkte (Sinnabschnitt bleibt aus _build_exporters,
Smart-an==aus am Keyboardstellen-Handoff) liegen bereits in
test_sinnabschnitt_exporter / test_keyboardstellen_smart_regression /
test_audio_routing_safety (Pin-1).
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import XMLExporter  # noqa: E402
from core.sinnabschnitt_exporter import SinnabschnittXMLExporter  # noqa: E402
from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, PROPOSED, ORIGIN_MARKER, marker_candidate_id)


def _marker_numbers(xml):
    return re.findall(r"<name>Stelle (\d+)</name>", xml)


_MICS = ["MIC1.wav", "MIC2.wav", "Mix.wav"]      # 2 Einzelmics + Mix


def _full_session(tmp_path):
    p = PeakCutProject()
    p.set_files(str(tmp_path / "KB.wav"), [str(tmp_path / m) for m in _MICS],
                [str(tmp_path / "CAM.mp4")])
    for f in ["KB.wav", "CAM.mp4", *_MICS]:
        (tmp_path / f).write_bytes(b"\x00")
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, {"fps": 25, "context_duration_ms": 15000})
    s.project.export_dir = str(tmp_path / "export")
    # 4 Peaks, index 1 ignoriert -> aktive Stellen 1,2,3 für index 0,2,3.
    p1 = Peak(index=1, position_ms=120000)
    p1.ignored = True
    s.peaks = [Peak(index=0, position_ms=60000), p1,
               Peak(index=2, position_ms=180000),
               Peak(index=3, position_ms=240000)]
    # Smart-Kandidaten nur für Peak 0 (Stelle 1) und Peak 3 (Stelle 3).
    s.clip_candidates = [
        ClipCandidate(candidate_id=marker_candidate_id(0), origin=ORIGIN_MARKER,
                      anchor_ms=60000, peak_id=0,
                      boundary=ClipBoundary(50000, 70000),
                      status=PROPOSED, score=0.8),
        ClipCandidate(candidate_id=marker_candidate_id(3), origin=ORIGIN_MARKER,
                      anchor_ms=240000, peak_id=3,
                      boundary=ClipBoundary(230000, 250000),
                      status=PROPOSED, score=0.7)]
    return s


def test_both_xmls_share_marker_numbers_for_common_peaks(tmp_path):
    s = _full_session(tmp_path)
    kb = open(XMLExporter().export(s), encoding="utf-8").read()
    sm = open(SinnabschnittXMLExporter().export(s), encoding="utf-8").read()

    kb_nums = _marker_numbers(kb)
    sm_nums = _marker_numbers(sm)

    assert kb_nums == ["1", "2", "3"]      # alle aktiven Peaks
    assert sm_nums == ["1", "3"]           # nur Peaks mit Smart-Kandidat
    # Stelle N in smart == Stelle N in raw (Teilmenge, identische Nummern)
    assert set(sm_nums).issubset(set(kb_nums))


def test_smart_has_same_audio_tracks_as_raw(tmp_path):
    # Vergleichbarkeit: "smart" trägt dieselben Tonspuren (Einzelmics + Mix)
    # wie "raw", nicht nur den Mix.
    s = _full_session(tmp_path)
    kb = open(XMLExporter().export(s), encoding="utf-8").read()
    sm = open(SinnabschnittXMLExporter().export(s), encoding="utf-8").read()
    for mic in _MICS:
        base = os.path.splitext(mic)[0]
        assert f"<name>{base}</name>" in kb      # in raw vorhanden (Vorlage)
        assert f"<name>{base}</name>" in sm      # jetzt auch in smart


def test_export_filenames_unchanged(tmp_path):
    s = _full_session(tmp_path)
    kb = XMLExporter().export(s)
    sm = SinnabschnittXMLExporter().export(s)
    assert os.path.basename(kb) == "Keyboardstellen - Hartmut Rosa.xml"
    assert os.path.basename(sm) == "Sinnabschnitte - Hartmut Rosa.xml"
