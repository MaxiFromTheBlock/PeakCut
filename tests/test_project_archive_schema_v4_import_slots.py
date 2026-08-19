"""#77 Task 4 — Schema v4: strukturelle Import-Slots in der Projektakte.

Die .peakcut-Akte trennt ab v4 Mix und Transkript strukturell:
``marker_track`` (canonical, war keyboard_track), echte ``mic_tracks`` OHNE
Mix, eigenes ``mix_track``, ``transcript_path``. v1-v3-Akten migrieren beim
Laden: der Mix wird aus den alten ``mic_tracks`` herausgezogen.

Pin-1-Naht: XMLExporter probt ``get_reference_track()`` (= ``mix_track``) fuer
das Audio-Format. Deshalb hier ein expliziter Save→Load→Re-Export-Pin, der die
Audio-Metadaten (channelcount/samplerate) durch die Migration verriegelt.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import XMLExporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.project_archive import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    ARCHIVE_DIR,
    ARCHIVE_FILE,
    ProjectArchiveError,
    load_project_archive,
    save_project_archive,
)
from core.session import PeakCutSession  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _bases(paths):
    return [os.path.basename(p) for p in paths]


def _make_session(tmp_path, with_transcript=True):
    """Marker + 2 echte Mics + Mix (+ optional Transkript) + Kamera.
    set_files bekommt den Mix in der Mic-Liste (Uebergangsform aus Task 2):
    mix_track wird gesetzt, der Mix bleibt vorerst zusaetzlich in mic_tracks."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    names = ["KB.wav", "MIC1.wav", "MIC2.wav", "Sheila Mix.mp3", "CAM.mp4"]
    if with_transcript:
        names.append("Transkript.docx")
    for n in names:
        (tmp_path / n).write_bytes(b"\x00")
    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [str(tmp_path / "MIC1.wav"), str(tmp_path / "MIC2.wav"),
         str(tmp_path / "Sheila Mix.mp3")],
        [str(tmp_path / "CAM.mp4")],
        transcript=str(tmp_path / "Transkript.docx") if with_transcript else None,
    )
    p.guest_name = "Sheila"
    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000,
                   "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    return s


def _read_archive(root):
    with open(os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE), encoding="utf-8") as f:
        return json.load(f)


def test_save_writes_schema_v4_structural_slots(tmp_path):
    s = _make_session(tmp_path / "mat")
    save_project_archive(s, root=str(tmp_path / "mat"))
    data = _read_archive(str(tmp_path / "mat"))

    # v4-Strukturslots bleiben in v5 erhalten (additiv) — Version ist jetzt 5.
    assert CURRENT_SCHEMA_VERSION == 6
    assert data["schema_version"] == 6
    proj = data["project"]
    # marker_track ist canonical, keyboard_track NICHT mehr geschrieben
    assert os.path.basename(proj["marker_track"]) == "KB.wav"
    assert "keyboard_track" not in proj
    # mix + transcript haben eigene Slots
    assert os.path.basename(proj["mix_track"]) == "Sheila Mix.mp3"
    assert os.path.basename(proj["transcript_path"]) == "Transkript.docx"
    # v4 ADDITIV: der Mix bleibt (noch) in mic_tracks, weil die
    # Keyboardstellen-XML ihre Audiospuren aus mic_tracks zieht (Pin-1).
    # Das Strippen zieht Task 5 (Exporter-Umhängung).
    assert _bases(proj["mic_tracks"]) == ["MIC1.wav", "MIC2.wav", "Sheila Mix.mp3"]


def test_v4_roundtrip_exact(tmp_path):
    s = _make_session(tmp_path / "mat")
    save_project_archive(s, root=str(tmp_path / "mat"))
    loaded = load_project_archive(str(tmp_path / "mat"), dict(_CFG))

    p = loaded.project
    assert os.path.basename(p.marker_track) == "KB.wav"
    assert os.path.basename(p.keyboard_track) == "KB.wav"  # Alias bleibt
    # additiv: Mix in mic_tracks (Pin-1) UND im eigenen Slot
    assert _bases(p.mic_tracks) == ["MIC1.wav", "MIC2.wav", "Sheila Mix.mp3"]
    assert os.path.basename(p.mix_track) == "Sheila Mix.mp3"
    assert os.path.basename(p.transcript_path) == "Transkript.docx"


def _write_v3_akte(material, with_external=False):
    material.mkdir(parents=True, exist_ok=True)
    for n in ("KB.wav", "MIC1.wav", "MIC2.wav", "Sheila Mix.mp3", "CAM.mp4"):
        (material / n).write_bytes(b"\x00")
    payload = {
        "schema_version": 3,
        "app": "PeakCut",
        "config": dict(_CFG),
        "project": {
            "keyboard_track": "KB.wav",
            "mic_tracks": ["MIC1.wav", "MIC2.wav", "Sheila Mix.mp3"],
            "videos": ["CAM.mp4"],
            "guest_name": "Sheila",
            "path_root_strategy": "common_parent",
            "has_external_paths": with_external,
        },
        "analysis_results": {
            "peaks": [], "video_offsets": [],
            "speaker_activity_csv": None,
            "speaker_activity_mic_assignments": [],
        },
        "assignments": {
            "folgenschnitt_assignment_applied": False,
            "folgenschnitt_mic_assignments": [],
            "folgenschnitt_camera_assignments": [],
            "folgenschnitt_unused_clips_mode": "disable",
        },
    }
    adir = material / ARCHIVE_DIR
    adir.mkdir(parents=True, exist_ok=True)
    with open(adir / ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_v3_akte_migrates_mix_to_structural_slot(tmp_path):
    """v3-Akte (Mix in mic_tracks, keyboard_track) -> mix_track wird ZUSÄTZLICH
    befüllt (additiv); der Mix bleibt in mic_tracks (Pin-1, Strippen in Task 5)."""
    material = tmp_path / "mat"
    _write_v3_akte(material)
    loaded = load_project_archive(str(material), dict(_CFG))

    p = loaded.project
    assert os.path.basename(p.marker_track) == "KB.wav"  # aus keyboard_track
    # Mix in mic_tracks gehoben -> mix_track (additiv, mic_tracks unverändert)
    assert os.path.basename(p.mix_track) == "Sheila Mix.mp3"
    assert _bases(p.mic_tracks) == ["MIC1.wav", "MIC2.wav", "Sheila Mix.mp3"]
    assert p.transcript_path is None


def test_folder_move_relativizes_all_slots(tmp_path):
    """Akte mit relativen Pfaden: nach Ordner-Umzug loesen Marker/Mics/Mix/
    Transkript/Videos unter dem neuen Ort auf."""
    s = _make_session(tmp_path / "orig")
    save_project_archive(s, root=str(tmp_path / "orig"))
    data = _read_archive(str(tmp_path / "orig"))
    # Pfade sind relativ gespeichert (kein absoluter Anker)
    assert not os.path.isabs(data["project"]["mix_track"])
    assert not os.path.isabs(data["project"]["transcript_path"])
    assert all(not os.path.isabs(p) for p in data["project"]["mic_tracks"])

    # Ganzen Ordner verschieben
    import shutil
    moved = tmp_path / "moved"
    shutil.move(str(tmp_path / "orig"), str(moved))
    loaded = load_project_archive(str(moved), dict(_CFG))
    p = loaded.project
    assert os.path.exists(p.mix_track) and str(moved) in p.mix_track
    assert all(os.path.exists(m) and str(moved) in m for m in p.mic_tracks)
    assert str(moved) in p.marker_track


def test_future_schema_v5_rejected(tmp_path):
    """Zukunfts-Schema-Guard (DATA-2) bleibt: v5-Akte wird nicht geladen."""
    material = tmp_path / "mat"
    _write_v3_akte(material)
    path = material / ARCHIVE_DIR / ARCHIVE_FILE
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    payload["schema_version"] = CURRENT_SCHEMA_VERSION + 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    with pytest.raises(ProjectArchiveError):
        load_project_archive(str(material), dict(_CFG))


def _xml_hash_for(session, tmp_root):
    """Deterministischer XML-Hash (tmp-Pfade normalisiert), per-Pfad-Probe:
    stereo Mix vs mono Mic — verriegelt auch die Audio-Metadaten."""
    def per_path_probe(path):
        return (48000, 24, 2) if "mix" in os.path.basename(path).lower() \
            else (44100, 16, 1)

    with patch("core.exporters._probe_audio_info", side_effect=per_path_probe), \
         patch("core.exporters._probe_video_info", return_value=(1920, 1080)):
        XMLExporter().export(session)
    xml_path = os.path.join(
        session.project.export_dir,
        f"Keyboardstellen - {session.project.guest_name}.xml")
    with open(xml_path, "rb") as f:
        raw = f.read()
    raw = raw.replace(str(tmp_root).encode("utf-8"), b"__ROOT__")
    return hashlib.sha256(raw).hexdigest()


def test_pin1_xml_identical_after_save_load_reexport(tmp_path):
    """Pin-1 durch die Migration: dieselbe Keyboardstellen-XML vor und nach
    Save→Load→Re-Export — inkl. Audio-Metadaten aus der Mix-Spur."""
    s = _make_session(tmp_path / "mat")
    s.project.export_dir = str(tmp_path / "exp_before")
    hash_before = _xml_hash_for(s, tmp_path / "mat")

    save_project_archive(s, root=str(tmp_path / "mat"))
    loaded = load_project_archive(str(tmp_path / "mat"), dict(_CFG))
    loaded.project.export_dir = str(tmp_path / "exp_after")
    hash_after = _xml_hash_for(loaded, tmp_path / "mat")

    assert hash_before == hash_after, (
        "Keyboardstellen-XML driftet durch Save/Load — die v4-Migration hat "
        "die Audioquelle (Mix) oder einen Pfad veraendert. Pin-1 verletzt."
    )
