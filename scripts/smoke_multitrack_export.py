#!/usr/bin/env python3
"""Slice B Task 9 — Premiere-Smoke-Helfer.

Liest die bereits existierende .peakcut-Akte vom Fremdmaterial-Test
2026-06-01 (Teil 2 von "1plus1"), exportiert die Folgenschnitt-XML
in beiden Modi (disable + remove) ueber den neuen Multitrack-Pfad,
und legt die XMLs in getrennte Download-Ordner. Max importiert beide
in Premiere, vergleicht.

Aufruf:
  cd ~/Desktop/MF/Vibecoding/PeakCut/App
  ./venv311/bin/python scripts/smoke_multitrack_export.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "src"
))

from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_multitrack_layout import (
    UNUSED_CLIPS_DISABLE,
    UNUSED_CLIPS_REMOVE,
)
from core.folgenschnitt_pipeline import prepare_folgenschnitt_for_export
from core.project_archive import load_project_archive


ARCHIVE = (
    "/Users/max/Desktop/Fremdproduktion/Material für Peakcut/"
    "Teil 2/.peakcut/project.json"
)
BASE_CONFIG = {"fps": 25, "context_duration_ms": 15000}


def _export_for_mode(mode: str) -> str:
    """Frische Session laden (kein State-Sharing zwischen Modi),
    Mode setzen, Decisions berechnen, Multitrack-XML schreiben."""
    session = load_project_archive(ARCHIVE, dict(BASE_CONFIG))
    session.folgenschnitt_unused_clips_mode = mode

    out_dir = os.path.expanduser(f"~/Downloads/Teil 2 - Smoke {mode}")
    os.makedirs(out_dir, exist_ok=True)
    session.project.export_dir = out_dir

    reason = prepare_folgenschnitt_for_export(session)
    if reason:
        sys.exit(f"[ERR] Folgenschnitt-Pipeline skippt: {reason}")

    decisions = session.folgenschnitt_edit_decisions
    xml_path = FolgenschnittXMLExporter().export(session)

    # Mini-Stats: wie viele disabled-Clips kommen raus?
    with open(xml_path, "rb") as f:
        body = f.read()
    disabled_count = body.count(b"<enabled>FALSE</enabled>")

    print(
        f"[OK] mode={mode:>7}  decisions={len(decisions):>4}  "
        f"disabled-clips={disabled_count:>4}  →  {xml_path}"
    )
    return xml_path


def main():
    print(f"Akte: {ARCHIVE}")
    print()
    for mode in (UNUSED_CLIPS_DISABLE, UNUSED_CLIPS_REMOVE):
        _export_for_mode(mode)
    print()
    print("Fertig. Beide XMLs in ~/Downloads/Teil 2 - Smoke <mode>/")
    print("Naechster Schritt: beide in Premiere (frisches Projekt) importieren.")


if __name__ == "__main__":
    main()
