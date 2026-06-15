"""DATA-2 — Schema-Versions-Policy (Carl-Plan 2026-06-15).

Eine Akte aus der Zukunft (schema_version > CURRENT) darf NICHT still
"best effort" geladen und schon gar nicht ueberschrieben werden — sonst
schneidet ein aelterer Client beim naechsten Autosave neuere Felder weg
(stiller Datenverlust im G3-Multi-Mac-Szenario). Alte/fehlende Versionen
laden weiter wie bisher.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.peak import Peak  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from core.project_archive import (  # noqa: E402
    CURRENT_SCHEMA_VERSION, ProjectArchiveError,
    build_archive_payload, parse_archive_payload,
    save_project_archive,
)

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def _session(tmp):
    kb = _touch(tmp / "Mat" / "P8" / "KB.wav")
    m1 = _touch(tmp / "Mat" / "P8" / "MIC1.wav")
    cam = _touch(tmp / "Mat" / "CAM_A.mp4")
    proj = PeakCutProject()
    proj.set_files(kb, [m1], [cam])
    proj.guest_name = "Hartmut Rosa"
    s = PeakCutSession(proj, dict(_CFG))
    s.peaks = [Peak(0, 60000, context_ms=15000)]
    return s


def _payload(tmp):
    return build_archive_payload(_session(tmp), material_root=str(tmp / "Mat"))


# --- Load-Policy ---

def test_missing_schema_version_loads_as_v1(tmp_path):
    payload = _payload(tmp_path)
    payload.pop("schema_version", None)
    res = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert res["project"]["guest_name"] == "Hartmut Rosa"


def test_current_schema_loads(tmp_path):
    payload = _payload(tmp_path)
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    res = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert res["project"]["guest_name"] == "Hartmut Rosa"


def test_older_schema_still_loads(tmp_path):
    payload = _payload(tmp_path)
    payload["schema_version"] = 0
    res = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert res["project"]["guest_name"] == "Hartmut Rosa"


def test_future_schema_refused_on_load(tmp_path):
    payload = _payload(tmp_path)
    payload["schema_version"] = CURRENT_SCHEMA_VERSION + 996  # 999
    with pytest.raises(ProjectArchiveError):
        parse_archive_payload(payload, fallback_config={"fps": 25})


def test_invalid_schema_value_raises_controlled(tmp_path):
    payload = _payload(tmp_path)
    payload["schema_version"] = "not-a-number"
    with pytest.raises(ProjectArchiveError):
        parse_archive_payload(payload, fallback_config={"fps": 25})


# --- Save-Policy ---

def test_save_writes_when_no_existing_archive(tmp_path):
    s = _session(tmp_path)
    path = save_project_archive(s)
    assert os.path.isfile(path)


def test_save_overwrites_current_archive(tmp_path):
    s = _session(tmp_path)
    save_project_archive(s)
    path = save_project_archive(s)  # zweiter Save = current schema, erlaubt
    assert json.loads(open(path).read())["schema_version"] == CURRENT_SCHEMA_VERSION


def test_save_refuses_to_overwrite_future_archive(tmp_path):
    s = _session(tmp_path)
    path = save_project_archive(s)
    # Akte aus der Zukunft auf die Platte legen (simuliert neueren Client):
    data = json.loads(open(path).read())
    data["schema_version"] = 999
    data["project"]["future_only_field"] = "wichtig"
    with open(path, "w") as f:
        json.dump(data, f)
    before = open(path, "rb").read()

    with pytest.raises(ProjectArchiveError):
        save_project_archive(s)

    # Zukunfts-Akte unangetastet, kein Feld weggeschnitten.
    assert open(path, "rb").read() == before
