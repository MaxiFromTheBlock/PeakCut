"""#77 Task 0 — Safety-Harness für den Import-Refactor (Carl-Plan 2026-06-16).

Diese Pins müssen WÄHREND des gesamten #77-Slice grün bleiben. Sie verriegeln,
was der Import-Umbau NICHT verändern darf:

1. **Audio-FORMAT-Quelle der Keyboardstellen-XML = die Mix-Spur.**
   ``XMLExporter`` probt für sample_rate/bit_depth/channelcount die Referenz aus
   ``project.get_reference_track()`` (exporters.py:252-254). Das ist die
   fragilste Naht der v4-Migration: zieht Task 4 den Mix aus ``mic_tracks``
   heraus, OHNE dass ``get_reference_track`` (Task 2) ZUERST ``project.mix_track``
   liest, probt die XML plötzlich ein mono Einzel-Mic → ``<channelcount>1</…>``
   statt 2 → andere Premiere-Bytes bei grün aussehenden Tests. Anders als der
   #71a-Pin (``test_audio_routing_safety.py``) mockt dieser Test
   ``_probe_audio_info`` NICHT flach, sondern PRO PFAD (stereo Mix vs. mono Mic)
   und verriegelt das Ergebnis im XML.

2. **Gastname stabil** für HM-typische Mix-Dateinamen (#77 Task 6 stellt
   ``guest_name.py`` auf den zentralen Klassifizierer um — darf die Namen nicht
   verschieben, sonst driftet der ``Marker - {Gastname}.xml``-Dateiname).

3. **Charakterisierung des heutigen Legacy-Imports** (KEIN Soll-Zustand): der Mix
   landet in den Audio-/Mic-Files, die ``.docx`` wird verworfen. Macht die
   Ausgangslage vor Task 7 sichtbar; Task 5/7 stellt das bewusst auf den
   Slot-Dialog um (Mix + Transkript bekommen eigene Slots).

Diese Tests pinnen das HEUTIGE Verhalten und sind beim Anlegen bereits grün —
das ist der Sinn eines Safety-Harness (Netz vor dem Modelldreh).
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import XMLExporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_BASE_CFG = {"fps": 25, "context_duration_ms": 15000}

# Distinktive Probe-Werte: die Mix-Spur ist stereo/48k/24bit, ein Einzel-Mic
# mono/44.1k/16bit. So macht jeder Quellen-Drift im XML einen sichtbaren
# Unterschied (channelcount 2↔1, samplerate 48000↔44100, depth 24↔16).
_MIX_PROBE = (48000, 24, 2)
_MIC_PROBE = (44100, 16, 1)


def _per_path_probe(path):
    name = os.path.basename(path).lower()
    return _MIX_PROBE if "mix" in name else _MIC_PROBE


def _make_session(tmp_path) -> PeakCutSession:
    """HM-Konstellation: Marker + 2 Mics + Mix + Kamera. Mix liegt heute in
    ``mic_tracks`` (Legacy-Form). Der Test ist bewusst NICHT auf diese interne
    Form angewiesen — er prüft nur, dass die XML-Audio-Metadaten aus der Mix-Spur
    stammen; nach der v4-Migration (Mix in ``mix_track``) muss das gleich bleiben.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "Sheila Mix.mp3", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [str(tmp_path / "MIC1.wav"),
         str(tmp_path / "MIC2.wav"),
         str(tmp_path / "Sheila Mix.mp3")],
        [str(tmp_path / "CAM.mp4")],
    )
    p.guest_name = "Sheila"
    p.export_dir = str(tmp_path / "exp")
    s = PeakCutSession(p, dict(_BASE_CFG))
    s.load_analysis_results({
        "peaks": [
            {"index": 0, "position_ms": 60_000,
             "context_ms": 15_000, "ignored": False},
            {"index": 1, "position_ms": 120_000,
             "context_ms": 15_000, "ignored": False},
        ],
        "video_offsets": [],
    })
    return s


def _export_xml(s) -> str:
    with patch("core.exporters._probe_audio_info", side_effect=_per_path_probe), \
         patch("core.exporters._probe_video_info", return_value=(1920, 1080)):
        XMLExporter().export(s)
    xml_path = os.path.join(
        s.project.export_dir, f"Marker - {s.project.guest_name}.xml")
    with open(xml_path, encoding="utf-8") as f:
        return f.read()


def test_xml_audio_format_probed_from_mix(tmp_path):
    """Pin: die fürs XML-Audioformat geprobte Referenz IST die Mix-Spur
    (get_reference_track), nicht ein Einzel-Mic."""
    s = _make_session(tmp_path)
    seen = []

    def spy(path):
        seen.append(path)
        return _per_path_probe(path)

    with patch("core.exporters._probe_audio_info", side_effect=spy), \
         patch("core.exporters._probe_video_info", return_value=(1920, 1080)):
        XMLExporter().export(s)

    assert seen, "XMLExporter hat keine Audio-Info geprobt"
    assert all("mix" in os.path.basename(p).lower() for p in seen), (
        "XMLExporter probt fürs Audioformat nicht die Mix-Spur: "
        f"{[os.path.basename(p) for p in seen]}. Nach der v4-Migration muss "
        "get_reference_track() weiter den Mix liefern (Task 2 VOR Task 4)."
    )


def test_xml_audio_metadata_is_stereo_mix_not_mono_mic(tmp_path):
    """Pin (Kern des Cross-Reviews): channelcount/samplerate/depth in der XML
    kommen aus dem stereo Mix, nicht aus einem mono Mic. Fängt den
    channelcount-Drift der v4-Migration, den der flach gemockte #71a-Pin
    NICHT fangen kann."""
    xml = _export_xml(_make_session(tmp_path))
    assert "<channelcount>2</channelcount>" in xml
    assert "<samplerate>48000</samplerate>" in xml
    assert "<depth>24</depth>" in xml
    assert "<channelcount>1</channelcount>" not in xml, (
        "XML enthält channelcount 1 — Audioformat stammt aus einem mono Mic "
        "statt aus dem stereo Mix (v4-Migrations-Regression, siehe Docstring)."
    )
    assert "<samplerate>44100</samplerate>" not in xml


def test_xml_audio_metadata_independent_of_mic_order(tmp_path):
    """Determinismus (Task #72): die Mix-Wahl hängt nicht von der
    mic_tracks-Reihenfolge ab. #77 darf diese Eigenschaft nicht verlieren."""
    s1 = _make_session(tmp_path / "a")
    s2 = _make_session(tmp_path / "b")
    s2.project.mic_tracks = list(reversed(s2.project.mic_tracks))
    assert "<channelcount>2</channelcount>" in _export_xml(s1)
    assert "<channelcount>2</channelcount>" in _export_xml(s2)


def test_guest_name_stable_for_hm_mix_filenames():
    """Pin: HM-typische Mix-Dateinamen → heutige Gastnamen (eingefroren, weil
    #77 Task 6 guest_name.py auf den zentralen Klassifizierer umstellt)."""
    from core.guest_name import extract_guest_name

    cases = [
        (["Hotel Matze - Sheila de Liz Mix.mp3"], "Sheila de Liz"),
        (["Sheila Mix.mp3"], "Unknown"),
        (["Episode - Mix.mp3"], "Unknown"),
        (["Podcast_mixdown.wav"], "Unknown"),
    ]
    for paths, expected in cases:
        assert extract_guest_name(paths) == expected, (
            f"extract_guest_name({paths!r}) driftet — erwartet {expected!r}. "
            "#77 Task 6 darf die HM-Gastnamen nicht verändern (sonst driftet der "
            "Keyboardstellen-Dateiname → Pin-1 indirekt verletzt)."
        )


def test_legacy_import_today_puts_mix_in_mics_and_drops_docx():
    """Charakterisierung (KEIN Soll-Zustand): heute klassifiziert
    _categorize_files den Mix als Mic und verwirft die .docx. Task 7 stellt das
    bewusst auf den Slot-Dialog um (Mix + Transkript bekommen eigene Slots)."""
    from gui.main_window import MainWindow

    fake = types.SimpleNamespace()
    files = ["/m/keyboard.wav", "/m/MIC1.wav", "/m/MIC2.wav",
             "/m/Sheila Mix.mp3", "/m/CAM.mp4", "/m/Transkript.docx"]
    MainWindow._categorize_files(fake, files)

    mics = [os.path.basename(x) for x in fake._mic_files]
    assert "Sheila Mix.mp3" in mics, "Heute landet der Mix in den Mics (Ist-Zustand)."
    assert os.path.basename(fake._keyboard_file) == "keyboard.wav"
    assert [os.path.basename(x) for x in fake._video_files] == ["CAM.mp4"]

    categorized = mics + [os.path.basename(fake._keyboard_file)] + \
        [os.path.basename(x) for x in fake._video_files]
    assert not any("docx" in name.lower() for name in categorized), (
        "Transkript.docx wird heute komplett verworfen — Task 7/8 gibt ihr "
        "einen eigenen Transkript-Slot."
    )
