"""Slice B Task 0 — Safety-Harness / Pin-1 (Carl-Plan 2026-06-03).

Diese Tests muessen WAEHREND des gesamten Slice-B-Baus gruen bleiben.
Sie fixieren Eigenschaften, die der Multi-Track-Folgenschnitt-Slice
*nicht* anfassen darf:

1. **Pin-1 (Keyboardstellen-XML byte-identisch):** XMLExporter
   produziert denselben Output, **auch wenn**
   ``session.folgenschnitt_unused_clips_mode`` auf "disable" oder
   "remove" gesetzt ist. Multi-Track-Toggle darf den Keyboardstellen-
   Pfad nicht beeinflussen.

2. **core/exporters.py API stabil:** XMLExporter, MP3Exporter,
   TXTExporter bleiben in ihrer oeffentlichen Form bestehen — der
   Slice fasst sie nicht an.

3. **Determinismus:** Mehrere Exporte aus identischer Session liefern
   denselben Hash (verhindert flaky Pin-Hashes durch Datums-Stempel
   o.Ae.).

Carl-Anforderung (Plan-Task 0): „Stopp-Gate: Pin-1 gruen, bevor
irgendein Exporter-Code geaendert wird." → das ist diese Datei.
"""

from __future__ import annotations

import hashlib
import os
import sys
from unittest.mock import patch

import pytest  # noqa: F401

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import (  # noqa: E402
    MP3Exporter,
    TXTExporter,
    XMLExporter,
)
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_BASE_CFG = {"fps": 25, "context_duration_ms": 15000}

# Stabiler Platzhalter, damit tmp-Pfad-Variabilitaet nicht in den
# Hash einfliesst.
_TMP_PLACEHOLDER = "__TMPDIR__"


def _make_session(tmp_path) -> PeakCutSession:
    """Realistische HM-Konstellation mit zwei Peaks."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav",
                 "Hotel Matze - Pin Test mix.mp3", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [
            str(tmp_path / "MIC1.wav"),
            str(tmp_path / "MIC2.wav"),
            str(tmp_path / "Hotel Matze - Pin Test mix.mp3"),
        ],
        [str(tmp_path / "CAM.mp4")],
    )
    p.export_dir = str(tmp_path / "exp")
    s = PeakCutSession(p, dict(_BASE_CFG))
    s.load_analysis_results(
        {
            "peaks": [
                {"index": 0, "position_ms": 60_000,
                 "context_ms": 15_000, "ignored": False},
                {"index": 1, "position_ms": 120_000,
                 "context_ms": 15_000, "ignored": False},
            ],
            "video_offsets": [],
        }
    )
    return s


def _normalize(xml_bytes: bytes, tmp_path) -> bytes:
    return xml_bytes.replace(
        str(tmp_path).encode("utf-8"),
        _TMP_PLACEHOLDER.encode("utf-8"),
    )


def _export_and_hash(tmp_path, unused_clips_mode):
    """Export Keyboardstellen-XML mit gesetztem (oder nicht gesetztem)
    Multi-Track-Mode und gibt (hash, raw_normalized_xml) zurueck."""
    session_dir = tmp_path / f"session_{unused_clips_mode or 'unset'}"
    s = _make_session(session_dir)

    # Mode dynamisch setzen — Attribut existiert bis Task 1 noch nicht
    # offiziell auf der Session, Python erlaubt das dynamisch.
    if unused_clips_mode is not None:
        s.folgenschnitt_unused_clips_mode = unused_clips_mode

    with patch(
        "core.exporters._probe_audio_info",
        return_value=(48000, 16, 2),
    ), patch(
        "core.exporters._probe_video_info",
        return_value=(1920, 1080),
    ):
        XMLExporter().export(s)

    xml_path = os.path.join(
        s.project.export_dir,
        f"Keyboardstellen - {s.project.guest_name}.xml",
    )
    raw = open(xml_path, "rb").read()
    normalized = _normalize(raw, session_dir)
    return hashlib.sha256(normalized).hexdigest(), normalized


# ---------------------------------------------------------------------
# Pin-1: Keyboardstellen-XML byte-identisch unabhaengig vom Mode
# ---------------------------------------------------------------------


def test_keyboardstellen_xml_unchanged_when_mode_not_set(tmp_path):
    """Baseline: ohne Multi-Track-Mode produziert XMLExporter den
    bekannten Keyboardstellen-Output. Wird als Referenz-Hash fuer
    die anderen Modi genutzt."""
    h_unset, _ = _export_and_hash(tmp_path, None)
    # Determinismus auf demselben Modus
    h_unset_2, _ = _export_and_hash(tmp_path / "rep", None)
    assert h_unset == h_unset_2, (
        "XMLExporter ist nicht deterministisch — Pin nicht stabil."
    )


def test_keyboardstellen_xml_byte_identical_in_disable_mode(tmp_path):
    """Pin-1 Hauptfall: Mode 'disable' darf Keyboardstellen-XML
    nicht veraendern."""
    h_unset, _ = _export_and_hash(tmp_path / "unset", None)
    h_disable, _ = _export_and_hash(tmp_path / "disable", "disable")
    assert h_unset == h_disable, (
        "Keyboardstellen-XML hat sich durch unused_clips_mode='disable' "
        "geaendert — Multi-Track-Slice darf XMLExporter NICHT "
        "beeinflussen. Pin-1 verletzt.\n"
        f"  unset:   {h_unset}\n"
        f"  disable: {h_disable}"
    )


def test_keyboardstellen_xml_byte_identical_in_remove_mode(tmp_path):
    """Pin-1 Mode-Variante: Mode 'remove' darf Keyboardstellen-XML
    nicht veraendern."""
    h_unset, _ = _export_and_hash(tmp_path / "unset", None)
    h_remove, _ = _export_and_hash(tmp_path / "remove", "remove")
    assert h_unset == h_remove, (
        "Keyboardstellen-XML hat sich durch unused_clips_mode='remove' "
        "geaendert — Multi-Track-Slice darf XMLExporter NICHT "
        "beeinflussen. Pin-1 verletzt.\n"
        f"  unset:  {h_unset}\n"
        f"  remove: {h_remove}"
    )


# ---------------------------------------------------------------------
# Pin-2: core/exporters.py oeffentliche API stabil
# ---------------------------------------------------------------------


def test_core_exporters_public_api_stable():
    """XMLExporter / MP3Exporter / TXTExporter bleiben als Klassen
    mit export(session)-Methode importierbar. Slice B darf
    core/exporters.py nicht anfassen."""
    for cls in (XMLExporter, MP3Exporter, TXTExporter):
        assert cls is not None
        assert callable(getattr(cls, "export", None)), (
            f"{cls.__name__}.export verschwunden — Slice B darf "
            f"core/exporters.py nicht anfassen."
        )


def test_core_exporters_module_path_unchanged():
    """Strukturanker: core.exporters bleibt am bekannten Pfad
    importierbar. Wenn der Slice die Datei verschiebt oder umbenennt,
    schlaegt das hier auf."""
    import importlib

    mod = importlib.import_module("core.exporters")
    assert hasattr(mod, "XMLExporter")
    assert hasattr(mod, "MP3Exporter")
    assert hasattr(mod, "TXTExporter")
