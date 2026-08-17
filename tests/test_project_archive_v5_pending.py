"""Import Slice 3 / Brocken B (i) — v5 PENDING-Import-Akte (Carl-Gate).

confirmImport laeuft VOR der Analyse (noch keine Peaks). Die Akte ist re-entrant,
aber klar noch NICHT analysiert: schema v5, confirmed_import_slots (die saubere WAHRHEIT,
Mics OHNE Mix), material_sources (Provenienz, KEINE Sicherheitsfreigabe), Pflichtsektionen
leer/default, analysis_state="pending".

Carl-Adapter (Option 2): confirmed_import_slots ist sauber getrennt, ABER die legacy
project-Sektion bleibt v4-foermig (Mix IN mic_tracks) -> der bestehende Loader/Exporter
bleibt Pin-1-sicher, ohne dass dieser Import-Slice den Export-Pfad anfasst.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.import_model import ConfirmedImportSlots  # noqa: E402
from core.project_archive import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    ARCHIVE_DIR,
    ARCHIVE_FILE,
    ANALYSIS_STATE_PENDING,
    ProjectArchiveError,
    save_pending_import_archive,
    save_project_archive,
    read_pending_import,
    load_project_archive,
)


def _real_media(root):
    """Echte (leere) Dateien — Loader/Reader pruefen Existenz."""
    os.makedirs(root, exist_ok=True)
    paths = {}
    for name in ("MIC4.wav", "P8Mix.wav", "MIC1.wav", "MIC2.wav", "Cam01.mp4", "Cam02.mp4"):
        p = os.path.join(root, name)
        with open(p, "wb") as f:
            f.write(b"x")
        paths[name] = p
    return paths


def _slots(m):
    return ConfirmedImportSlots(
        marker=m["MIC4.wav"], mix=m["P8Mix.wav"],
        mics=(m["MIC1.wav"], m["MIC2.wav"]),
        videos=(m["Cam01.mp4"], m["Cam02.mp4"]),
    )


def _archive_json(root):
    with open(os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE)) as f:
        return json.load(f)


def test_current_schema_is_5():
    assert CURRENT_SCHEMA_VERSION == 5


def test_pending_roundtrip(tmp_path):
    root = str(tmp_path / "mat")
    m = _real_media(root)
    path = save_pending_import_archive(root, _slots(m), material_sources=[root])
    assert path.endswith(os.path.join(ARCHIVE_DIR, ARCHIVE_FILE))

    data = _archive_json(root)
    assert data["schema_version"] == 5
    assert data["analysis_state"] == ANALYSIS_STATE_PENDING
    # Pflichtsektionen vorhanden (leer/default) -> re-entrant + alter Loader vertraegt es.
    for sec in ("project", "analysis_results", "assignments"):
        assert sec in data
    assert data["analysis_results"]["peaks"] == []

    pend = read_pending_import(root)
    assert pend is not None
    assert pend["analysis_state"] == ANALYSIS_STATE_PENDING
    rs = pend["slots"]
    assert rs.marker == m["MIC4.wav"]
    assert rs.mix == m["P8Mix.wav"]
    assert set(rs.mics) == {m["MIC1.wav"], m["MIC2.wav"]}
    assert set(rs.videos) == {m["Cam01.mp4"], m["Cam02.mp4"]}
    assert rs.has_speech()


def test_confirmed_slots_clean_but_project_section_pin1_legacy(tmp_path):
    # confirmed_import_slots: Mics SAUBER (ohne Mix). project-Sektion: Mix bleibt in
    # mic_tracks (v4-foermig) -> legacy-Loader/Export bleibt byte-stabil (Pin-1).
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    data = _archive_json(root)

    cis_mics = {os.path.basename(p) for p in data["confirmed_import_slots"]["mics"]}
    assert cis_mics == {"MIC1.wav", "MIC2.wav"}            # sauber, KEIN Mix
    assert os.path.basename(data["confirmed_import_slots"]["mix"]) == "P8Mix.wav"

    proj_mics = {os.path.basename(p) for p in data["project"]["mic_tracks"]}
    assert "P8Mix.wav" in proj_mics                        # Adapter: Mix in legacy mic_tracks


def test_material_sources_are_provenance(tmp_path):
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    pend = read_pending_import(root)
    assert [os.path.realpath(s) for s in pend["material_sources"]] == [os.path.realpath(root)]


def test_pending_akte_loads_as_empty_session(tmp_path):
    # Re-entrant: der bestehende Loader akzeptiert die pending-Akte (leere Analyse),
    # und das legacy-project hat den Mix in mic_tracks (Pin-1-Form).
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    session = load_project_archive(root, {"fps": 25})
    assert len(session.peaks) == 0
    assert any(os.path.basename(p) == "P8Mix.wav" for p in session.project.mic_tracks)


def test_read_pending_returns_none_for_non_pending(tmp_path):
    # Akte ohne analysis_state=pending (z.B. spaeter analysiert) -> kein pending-Import.
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    p = os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE)
    data = _archive_json(root)
    data["analysis_state"] = "analyzed"
    with open(p, "w") as f:
        json.dump(data, f)
    assert read_pending_import(root) is None


# --- Carl-P1: pending mit kaputtem/Zukunfts-Inhalt NIE still auf None (sonst faellt der
# Analysepfad auf die Namensheuristik zurueck) -> kontrollierter ProjectArchiveError. ---

def _write_pending_then_mutate(root, mutate):
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    p = os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE)
    data = _archive_json(root)
    mutate(data)
    with open(p, "w") as f:
        json.dump(data, f)
    return root


def test_pending_future_schema_rejected(tmp_path):
    # DATA-2 auch fuer den Pending-Reader: Zukunfts-Akte -> nicht still laden.
    root = _write_pending_then_mutate(
        str(tmp_path / "mat"),
        lambda d: d.__setitem__("schema_version", CURRENT_SCHEMA_VERSION + 1))
    with pytest.raises(ProjectArchiveError):
        read_pending_import(root)


def test_pending_missing_slots_rejected(tmp_path):
    root = _write_pending_then_mutate(
        str(tmp_path / "mat"), lambda d: d.pop("confirmed_import_slots"))
    with pytest.raises(ProjectArchiveError):
        read_pending_import(root)


def test_pending_broken_slots_rejected(tmp_path):
    root = _write_pending_then_mutate(
        str(tmp_path / "mat"),
        lambda d: d.__setitem__("confirmed_import_slots", "kaputt"))
    with pytest.raises(ProjectArchiveError):
        read_pending_import(root)


def test_pending_mics_not_list_rejected(tmp_path):
    # mics/videos muessen Listen sein, nicht still String-iteriert werden.
    root = _write_pending_then_mutate(
        str(tmp_path / "mat"),
        lambda d: d["confirmed_import_slots"].__setitem__("mics", "MIC1.wav"))
    with pytest.raises(ProjectArchiveError):
        read_pending_import(root)


def test_confirm_write_rejects_analyzed_akte(tmp_path):
    # Carl-P1b: save_pending darf eine bereits analysierte/normale Akte NIE auf leere
    # Pending-Sektionen zuruecksetzen -> ProjectArchiveError, Akte byte-unveraendert.
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    p = os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE)
    data = _archive_json(root)
    data.pop("analysis_state")          # -> analysiert/normal (kein pending mehr)
    with open(p, "w") as f:
        json.dump(data, f)
    with open(p, "rb") as f:
        before = f.read()
    with pytest.raises(ProjectArchiveError):
        save_pending_import_archive(root, _slots(m), material_sources=[root])
    with open(p, "rb") as f:
        assert f.read() == before       # unveraendert


def test_confirm_write_updates_existing_pending(tmp_path):
    # Carl-P1b: eine vorhandene PENDING-Akte darf aktualisiert werden (zweites Confirm).
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    slots2 = ConfirmedImportSlots(
        marker=m["MIC1.wav"], mics=(m["MIC2.wav"],), videos=(m["Cam01.mp4"],))
    save_pending_import_archive(root, slots2, material_sources=[root])
    pend = read_pending_import(root)
    assert os.path.basename(pend["slots"].marker) == "MIC1.wav"


def test_normal_save_does_not_preserve_pending(tmp_path):
    # Carl-P2: Pending wird NICHT ueber den normalen Autosave konserviert. Beabsichtigt —
    # der Analysepfad konsumiert Pending ueber read_pending_import() und speichert dann
    # FINAL analysiert. Ein normaler save_project_archive() auf der pending-geladenen
    # Session verliert confirmed_import_slots/material_sources/analysis_state.
    root = str(tmp_path / "mat")
    m = _real_media(root)
    save_pending_import_archive(root, _slots(m), material_sources=[root])
    session = load_project_archive(root, {"fps": 25})
    save_project_archive(session, root=root)
    data = _archive_json(root)
    assert "confirmed_import_slots" not in data
    assert data.get("analysis_state") is None
    assert read_pending_import(root) is None
