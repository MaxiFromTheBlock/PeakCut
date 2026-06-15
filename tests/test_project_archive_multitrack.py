"""Slice B Task 6 — Schema-v3 Persistenz fuer Multi-Track-Toggle.

Verifiziert:
- CURRENT_SCHEMA_VERSION = 3.
- build_archive_payload serialisiert assignments.folgenschnitt_unused_clips_mode.
- v3-Akten: Save/Load Roundtrip exakt (disable + remove).
- v2-Akten (ohne Feld): Bootstrap mit DEFAULT_UNUSED_CLIPS_MODE.
- v3-Akten mit ungueltigem Wert: Fallback auf Default, kein Crash.
- Bestehende v2-Vertraege (clip_candidates, transcript-ref,
  Pfadrelativierung) bleiben unveraendert.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.project_archive import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    build_archive_payload,
    load_project_archive,
    save_project_archive,
)
from core.folgenschnitt_multitrack_layout import (  # noqa: E402
    DEFAULT_UNUSED_CLIPS_MODE,
    UNUSED_CLIPS_DISABLE,
    UNUSED_CLIPS_REMOVE,
)
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402


_BASE_CFG = {"fps": 25, "context_duration_ms": 15000}


# ---------------------------------------------------------------------
# 1. Schema-Version
# ---------------------------------------------------------------------


def test_schema_version_bumped_to_3():
    assert CURRENT_SCHEMA_VERSION == 3


# ---------------------------------------------------------------------
# 2. build_archive_payload schreibt unused_clips_mode
# ---------------------------------------------------------------------


def _make_session(tmp_path, mode=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "Test mix.wav", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [
            str(tmp_path / "MIC1.wav"),
            str(tmp_path / "MIC2.wav"),
            str(tmp_path / "Test mix.wav"),
        ],
        [str(tmp_path / "CAM.mp4")],
    )
    p.guest_name = "Test Guest"
    p.export_dir = str(tmp_path / "exp")
    s = PeakCutSession(p, dict(_BASE_CFG))
    s.load_analysis_results({"peaks": [], "video_offsets": []})
    if mode is not None:
        s.folgenschnitt_unused_clips_mode = mode
    return s


def test_payload_serializes_unused_clips_mode_default(tmp_path):
    """Fresh session → payload traegt DEFAULT_UNUSED_CLIPS_MODE."""
    s = _make_session(tmp_path / "s")
    payload = build_archive_payload(s, material_root=str(tmp_path / "s"))
    assert "folgenschnitt_unused_clips_mode" in payload["assignments"]
    assert (
        payload["assignments"]["folgenschnitt_unused_clips_mode"]
        == DEFAULT_UNUSED_CLIPS_MODE
    )


def test_payload_serializes_unused_clips_mode_remove(tmp_path):
    s = _make_session(tmp_path / "s", mode=UNUSED_CLIPS_REMOVE)
    payload = build_archive_payload(s, material_root=str(tmp_path / "s"))
    assert (
        payload["assignments"]["folgenschnitt_unused_clips_mode"]
        == UNUSED_CLIPS_REMOVE
    )


# ---------------------------------------------------------------------
# 3. Save/Load Roundtrip exakt
# ---------------------------------------------------------------------


def test_save_load_roundtrip_disable_mode(tmp_path):
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material, mode=UNUSED_CLIPS_DISABLE)
    archive_path = save_project_archive(s1, root=str(material))
    assert os.path.exists(archive_path)

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2 is not None
    assert s2.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_DISABLE


def test_save_load_roundtrip_remove_mode(tmp_path):
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material, mode=UNUSED_CLIPS_REMOVE)
    archive_path = save_project_archive(s1, root=str(material))

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_REMOVE


# ---------------------------------------------------------------------
# 4. v2-Akte (ohne Feld) → Default-Bootstrap
# ---------------------------------------------------------------------


def test_v2_archive_without_field_loads_with_default(tmp_path):
    """Aelteren v2-Akte (ohne folgenschnitt_unused_clips_mode) muss
    weiter ladbar sein und session-Default einsetzen."""
    import json
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material)
    archive_path = save_project_archive(s1, root=str(material))

    # Simuliere v2-Akte: Schema-Version + Feld manuell entfernen
    with open(archive_path) as f:
        data = json.load(f)
    data["schema_version"] = 2
    data["assignments"].pop("folgenschnitt_unused_clips_mode", None)
    with open(archive_path, "w") as f:
        json.dump(data, f)

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2 is not None
    assert s2.folgenschnitt_unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


def test_v1_archive_without_field_loads_with_default(tmp_path):
    """Auch noch aeltere v1-Akten (schema_version=1) bootstrappen
    auf den Default-Mode."""
    import json
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material)
    archive_path = save_project_archive(s1, root=str(material))

    with open(archive_path) as f:
        data = json.load(f)
    data["schema_version"] = 1
    data["assignments"].pop("folgenschnitt_unused_clips_mode", None)
    # v1 hatte keine clip_candidates/peak_decisions — simulieren
    data.pop("clip_candidates", None)
    data.pop("peak_decisions", None)
    with open(archive_path, "w") as f:
        json.dump(data, f)

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2.folgenschnitt_unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


# ---------------------------------------------------------------------
# 5. Ungueltiger Wert → Default-Fallback, kein Crash
# ---------------------------------------------------------------------


def test_invalid_mode_value_falls_back_to_default(tmp_path):
    """Tippfehler oder Migration-Schaden in der Akte (z.B. 'garbage'
    oder None) → loader fallback auf DEFAULT, kein Crash."""
    import json
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material, mode=UNUSED_CLIPS_REMOVE)
    archive_path = save_project_archive(s1, root=str(material))

    with open(archive_path) as f:
        data = json.load(f)
    data["assignments"]["folgenschnitt_unused_clips_mode"] = "garbage"
    with open(archive_path, "w") as f:
        json.dump(data, f)

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2.folgenschnitt_unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


def test_null_mode_falls_back_to_default(tmp_path):
    import json
    material = tmp_path / "material"
    material.mkdir()
    s1 = _make_session(material, mode=UNUSED_CLIPS_REMOVE)
    archive_path = save_project_archive(s1, root=str(material))

    with open(archive_path) as f:
        data = json.load(f)
    data["assignments"]["folgenschnitt_unused_clips_mode"] = None
    with open(archive_path, "w") as f:
        json.dump(data, f)

    s2 = load_project_archive(archive_path, dict(_BASE_CFG))
    assert s2.folgenschnitt_unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


# ---------------------------------------------------------------------
# 6. Existierende v2-Vertraege bleiben gruen (Backwards-Schutz)
# ---------------------------------------------------------------------


def test_existing_v2_payload_still_has_clip_candidates_and_transcript(tmp_path):
    """Schema-v3-Bump darf clip_candidates / peak_decisions /
    transcript nicht beschaedigen."""
    s = _make_session(tmp_path / "s")
    payload = build_archive_payload(s, material_root=str(tmp_path / "s"))
    assert "clip_candidates" in payload
    assert "peak_decisions" in payload
    assert "transcript" in payload
