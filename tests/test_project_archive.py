"""HC-4 Task 0 — .peakcut/project.json Format einfrieren (Carl-Plan).

Gate A: Format steht, Schema-Version + bekannte Sektionen vorhanden,
unbekannte/zukünftige Felder crashen nicht.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.project_archive import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    ARCHIVE_DIR,
    ARCHIVE_FILE,
    ProjectArchiveError,
    build_archive_payload,
    parse_archive_payload,
)


class _FakeProject:
    def __init__(self):
        self.keyboard_track = "/m/P8/KB.wav"
        self.mic_tracks = ["/m/P8/MIC1.wav", "/m/P8/MIC2.wav"]
        self.videos = ["/m/CAM_A.mp4"]
        self.guest_name = "Hartmut Rosa"


class _FakeSession:
    def __init__(self):
        self.project = _FakeProject()
        self.config = {"fps": 25, "context_duration_ms": 15000}
        self.peaks = []
        self.video_offsets = []
        self.speaker_activity = []
        self.speaker_activity_csv = None
        self.speaker_activity_mic_assignments = []
        self.folgenschnitt_mic_assignments = []
        self.folgenschnitt_camera_assignments = []
        self.folgenschnitt_assignment_applied = True


def test_constants_are_frozen():
    assert CURRENT_SCHEMA_VERSION == 1
    assert ARCHIVE_DIR == ".peakcut"
    assert ARCHIVE_FILE == "project.json"


def test_archive_payload_has_schema_version_and_known_sections():
    payload = build_archive_payload(_FakeSession(), material_root="/m")
    assert payload["schema_version"] == CURRENT_SCHEMA_VERSION
    assert payload["app"] == "PeakCut"
    for section in ("config", "project", "analysis_results", "assignments"):
        assert section in payload, section
    # export_dir wird NICHT persistiert (Laufumgebung, nicht Identität)
    assert "export_dir" not in payload["project"]
    assert payload["config"]["fps"] == 25


def test_unknown_future_fields_are_ignored():
    payload = build_archive_payload(_FakeSession(), material_root="/m")
    payload["totally_new_top_level"] = {"x": 1}
    payload["project"]["future_field"] = "ok"
    # darf nicht crashen
    result = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert result["project"]["guest_name"] == "Hartmut Rosa"


def test_lower_or_newer_schema_with_required_fields_loads_best_effort():
    payload = build_archive_payload(_FakeSession(), material_root="/m")
    payload["schema_version"] = 999  # zukünftige Version
    res_new = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert res_new["project"]["guest_name"] == "Hartmut Rosa"

    payload["schema_version"] = 0  # uralt
    res_old = parse_archive_payload(payload, fallback_config={"fps": 25})
    assert res_old["project"]["guest_name"] == "Hartmut Rosa"


def test_missing_required_section_raises_controlled():
    bad = {"schema_version": 1, "app": "PeakCut"}  # keine project-Sektion
    try:
        parse_archive_payload(bad, fallback_config={"fps": 25})
        assert False, "sollte ProjectArchiveError werfen"
    except ProjectArchiveError:
        pass


# --- Tasks 1-4: echte Round-Trips (Gates B-E) ---

import json as _json
from core.peak import Peak
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.folgenschnitt_models import ActivityFrame
from core.project_archive import (
    save_project_archive, load_project_archive,
    find_project_archive_for_files, material_root, peak_to_dict,
)

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def _frames():
    return [
        ActivityFrame(0, 200, {"mic_1": -20.0, "mic_2": -40.0},
                      {"mic_1": -50.0, "mic_2": -50.0}, 20.0,
                      "mic_1", "mic_1", 1.0),
        ActivityFrame(200, 400, {"mic_1": -45.0, "mic_2": -44.0},
                      {"mic_1": -50.0, "mic_2": -50.0}, 1.0,
                      None, None, 0.0),
    ]


def _session(tmp, root):
    kb = _touch(tmp / root / "P8" / "KB.wav")
    m1 = _touch(tmp / root / "P8" / "MIC1.wav")
    cam = _touch(tmp / root / "CAM_A.mp4")
    proj = PeakCutProject()
    proj.set_files(kb, [m1], [cam])
    proj.guest_name = "Hartmut Rosa"
    s = PeakCutSession(proj, dict(_CFG))
    p0 = Peak(0, 60000, context_ms=15000)
    p0.set_in_point(50000)
    p0.set_out_point(80000)
    p1 = Peak(1, 120000, context_ms=15000)
    p1.ignored = True
    s.peaks = [p0, p1]
    s.video_offsets = [("CAM_A.mp4", "-00:00:02:00")]
    s.speaker_activity = _frames()
    s.folgenschnitt_assignment_applied = True
    return s, kb, m1, cam


def test_paths_relative_no_dotdot_when_common_folder(tmp_path):
    s, kb, m1, cam = _session(tmp_path, "Mat")
    path = save_project_archive(s)
    assert path.endswith(".peakcut/project.json")
    data = _json.loads(open(path).read())
    for p in ([data["project"]["keyboard_track"]]
              + data["project"]["mic_tracks"] + data["project"]["videos"]):
        assert not p.startswith(".."), p
    assert data["project"]["has_external_paths"] is False


def test_load_resolves_after_folder_move(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    save_project_archive(s)
    moved = tmp_path / "Moved"
    (tmp_path / "Mat").rename(moved)
    loaded = load_project_archive(str(moved), dict(_CFG))
    assert loaded.project.guest_name == "Hartmut Rosa"
    assert os.path.isfile(loaded.project.keyboard_track)
    assert loaded.project.keyboard_track.startswith(str(moved))


def test_missing_file_raises_controlled(tmp_path):
    s, kb, *_ = _session(tmp_path, "Mat")
    save_project_archive(s)
    os.remove(kb)
    try:
        load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
        assert False, "sollte ProjectArchiveError werfen"
    except ProjectArchiveError as e:
        assert "KB.wav" in str(e)


def test_peak_round_trip_exact(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    save_project_archive(s)
    L = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert L.peaks[0].in_point_ms == 50000
    assert L.peaks[0].out_point_ms == 80000
    assert L.peaks[1].ignored is True
    assert [p.position_ms for p in L.peaks] == [60000, 120000]


def test_peak_clamp_survives_reload(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    s.peaks[0]._duration_ms = 70000  # out würde auf 70000 clampen
    assert s.peaks[0].out_point_ms == 70000
    save_project_archive(s)
    L = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert L.peaks[0].out_point_ms == 70000  # exportgleich nach Reload


def test_speaker_activity_csv_referenced_not_inlined(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    path = save_project_archive(s)
    data = _json.loads(open(path).read())
    assert data["analysis_results"]["speaker_activity_csv"] == \
        ".peakcut/speaker_activity.csv"
    assert "speaker_activity" not in data["analysis_results"]
    assert os.path.isfile(tmp_path / "Mat" / ".peakcut"
                          / "speaker_activity.csv")
    L = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert len(L.speaker_activity) == 2
    assert L.speaker_activity[1].smoothed_speaker is None  # "unknown"->None


def test_missing_csv_raises_controlled(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    save_project_archive(s)
    os.remove(tmp_path / "Mat" / ".peakcut" / "speaker_activity.csv")
    try:
        load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
        assert False
    except ProjectArchiveError as e:
        assert "speaker_activity" in str(e)


def test_session_full_round_trip(tmp_path):
    s, kb, m1, cam = _session(tmp_path, "Mat")
    save_project_archive(s)
    L = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert L.project.keyboard_track == kb
    assert L.project.mic_tracks == [m1]
    assert L.project.videos == [cam]
    assert L.project.guest_name == "Hartmut Rosa"
    assert L.video_offsets == [("CAM_A.mp4", "-00:00:02:00")]
    assert L.folgenschnitt_assignment_applied is True
    assert L.config["fps"] == 25


def test_find_archive_for_files(tmp_path):
    s, kb, m1, cam = _session(tmp_path, "Mat")
    assert find_project_archive_for_files([kb, m1, cam]) is None
    save_project_archive(s)
    found = find_project_archive_for_files([kb, m1, cam])
    assert found and found.endswith(".peakcut/project.json")
