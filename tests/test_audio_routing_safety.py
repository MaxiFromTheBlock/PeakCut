"""#71a Task 0 — Safety-Harness (Carl-Pin-1 für Audio-Routing-Slice).

Diese Tests müssen WÄHREND des gesamten #71a-Slice grün bleiben.
Sie fixieren drei Eigenschaften, die der Audio-Routing-Helfer
*nicht* anfassen darf:

1. **Pin-1 (Keyboardstellen-XML byte-identisch):** XMLExporter
   produziert dasselbe XML, wenn ``mic_tracks = [MIC1, MIC2, Mix]``.
   Wird über einen normalisierten SHA-256-Hash verriegelt
   (tmp-Pfade werden vor dem Hashen durch einen festen Platzhalter
   ersetzt, damit der Hash zwischen Maschinen reproduzierbar ist).

2. **Folgenschnitt-Exporter unangetastet:** Die
   ``FolgenschnittXMLExporter``-Klasse wird durch #71a nicht
   berührt — Import + öffentliche Pfadstruktur bleibt stabil.

3. **Persistenz-Schema unverändert:** ``project.mic_tracks`` wird
   in ``project_archive.save_project_archive`` /
   ``load_project_archive`` round-trip-exakt gespeichert/geladen,
   inklusive der Mix-Datei (Schema-v3 / Trennung kommt erst mit
   Task #77 Import-Refactor).
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from unittest.mock import patch

import pytest  # noqa: F401

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import XMLExporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.project_archive import (  # noqa: E402
    load_project_archive,
    save_project_archive,
)
from core.session import PeakCutSession  # noqa: E402

_BASE_CFG = {"fps": 25, "context_duration_ms": 15000}

# Stable per-machine placeholder so dass Pfad-Variabilität nicht
# in den XML-Hash einfließt.
_TMP_PLACEHOLDER = "__TMPDIR__"

# Pin-Hash für den Mix-in-Mic-Liste-Fall. Wird beim ersten Lauf
# erzeugt und hier eingetragen — dokumentierter bewusster Snapshot
# des aktuellen XMLExporter-Outputs *vor* #71a-Bau. Jede Änderung
# am Hash MUSS als bewusster Eingriff diskutiert werden.
_XML_PIN_HASH_MIX_IN_MICS = (
    "52be195e91ce5c4ab04f54abd53dcc2d8697f925f034c0222078726371302bce"
)


def _make_session_with_mix(tmp_path) -> PeakCutSession:
    """Realistische HM-Konstellation: Marker-Spur + 2 Mics + Mix.
    Mix-Datei taucht in mic_tracks auf (heutiges Verhalten, soll
    durch Pin-Tests fixiert werden)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "Sheila Mix.mp3", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [
            str(tmp_path / "MIC1.wav"),
            str(tmp_path / "MIC2.wav"),
            str(tmp_path / "Sheila Mix.mp3"),
        ],
        [str(tmp_path / "CAM.mp4")],
    )
    p.guest_name = "Sheila"
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
    """Tmp-Pfade durch festen Platzhalter ersetzen, damit Hash
    zwischen Maschinen / Test-Läufen identisch ist."""
    return xml_bytes.replace(
        str(tmp_path).encode("utf-8"),
        _TMP_PLACEHOLDER.encode("utf-8"),
    )


def _xml_hash(tmp_path) -> tuple[str, bytes]:
    s = _make_session_with_mix(tmp_path / "session")
    with patch(
        "core.exporters._probe_audio_info",
        return_value=(48000, 16, 2),
    ), patch(
        "core.exporters._probe_video_info",
        return_value=(1920, 1080),
    ):
        XMLExporter().export(s)
    xml_path = os.path.join(
        s.project.export_dir, f"Keyboardstellen - {s.project.guest_name}.xml"
    )
    raw = open(xml_path, "rb").read()
    normalized = _normalize(raw, tmp_path / "session")
    return hashlib.sha256(normalized).hexdigest(), normalized


def test_keyboardstellen_xml_byte_identical_with_mix_in_mic_list(
    tmp_path, capsys
):
    """Pin-1: XMLExporter-Output bleibt byte-identisch (modulo
    tmp-Pfad-Variabilität), wenn die Mix-Datei in mic_tracks
    enthalten ist. Verriegelt den heutigen Output gegen unbe-
    absichtigte Drift durch #71a."""
    actual_hash, normalized = _xml_hash(tmp_path)
    if _XML_PIN_HASH_MIX_IN_MICS.startswith("PLACEHOLDER"):
        with capsys.disabled():
            print(
                f"\n[#71a Task 0] Pin-Hash beim ersten Lauf erzeugt:"
                f"\n  {actual_hash}\n"
                f"  → in tests/test_audio_routing_safety.py eintragen,"
                f" dann Test grün."
            )
        pytest.skip(
            "Pin-Hash noch nicht eingetragen — Wert oben kopieren."
        )
    assert actual_hash == _XML_PIN_HASH_MIX_IN_MICS, (
        f"XMLExporter-Output hat sich geändert.\n"
        f"  erwartet: {_XML_PIN_HASH_MIX_IN_MICS}\n"
        f"  aktuell:  {actual_hash}\n"
        f"#71a darf XMLExporter NICHT berühren (Pin-1). Wenn die "
        f"Änderung außerhalb #71a beabsichtigt ist, bitte den "
        f"Hash bewusst aktualisieren und im Commit begründen."
    )


def test_keyboardstellen_xml_deterministic_within_same_session(tmp_path):
    """Determinismus-Sanity: zwei XML-Exporte aus identischen
    Sessions liefern denselben Hash. Fängt versteckte
    Nicht-Determinismen (Datums-Stempel etc.) ab, die einen
    Pin-Hash flaky machen würden."""
    h1, _ = _xml_hash(tmp_path / "a")
    h2, _ = _xml_hash(tmp_path / "b")
    assert h1 == h2, "XMLExporter ist nicht deterministisch — Pin nicht stabil"


def test_folgenschnitt_xml_exporter_module_unchanged():
    """Pin-2: FolgenschnittXMLExporter wird durch #71a nicht
    angefasst. Klasse + öffentliche Pfade bleiben importierbar."""
    from core.folgenschnitt_exporter import FolgenschnittXMLExporter

    assert FolgenschnittXMLExporter is not None
    # Öffentliche API: export(session) muss existieren.
    assert callable(getattr(FolgenschnittXMLExporter, "export", None))


def test_project_archive_preserves_mic_tracks_including_mix(tmp_path):
    """Pin-3: Save/Load round-trip lässt project.mic_tracks
    unverändert — Mix-Datei bleibt in der Liste. Schema-Trennung
    ist explizit OUT-of-scope für #71a (kommt mit #77 Import-
    Refactor)."""
    material = tmp_path / "material"
    material.mkdir()
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "Sheila Mix.mp3", "CAM.mp4"):
        (material / name).write_bytes(b"\x00")

    p1 = PeakCutProject()
    p1.set_files(
        str(material / "KB.wav"),
        [
            str(material / "MIC1.wav"),
            str(material / "MIC2.wav"),
            str(material / "Sheila Mix.mp3"),
        ],
        [str(material / "CAM.mp4")],
    )
    p1.guest_name = "Sheila"
    p1.export_dir = str(tmp_path / "exp")

    s1 = PeakCutSession(p1, dict(_BASE_CFG))
    s1.load_analysis_results({"peaks": [], "video_offsets": []})

    archive_path = save_project_archive(s1, root=str(material))
    assert os.path.exists(archive_path)

    # Frisches Projekt aus Akte laden (Archive-API verlangt
    # fallback_config — wir geben die identische Test-Config mit).
    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2 is not None

    before = [os.path.basename(p) for p in p1.mic_tracks]
    after = [os.path.basename(p) for p in s2.project.mic_tracks]

    assert after == before, (
        "project.mic_tracks hat sich durch Save/Load geändert. "
        "Mix muss in der Liste bleiben — Schema-Trennung kommt "
        "erst mit #77 Import-Refactor."
    )
    # Explizit: Mix ist nach wie vor unter den Mics.
    assert any("mix" in name.lower() for name in after), (
        "Sheila Mix.mp3 ist aus mic_tracks verschwunden — Pin-3 verletzt."
    )
