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
    assert CURRENT_SCHEMA_VERSION == 2  # v2: + clip_candidates/peak_decisions
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


# --- Carl P1: Assignment-Pfade verschiebbar + Folgenschnitt-Roundtrip ---

from core.folgenschnitt_models import MicAssignment, CameraAssignment, SHOT_WIDE
from core.folgenschnitt_pipeline import prepare_folgenschnitt_for_export


def _fs_frames():
    fr = []
    t = 0
    for i in range(40):
        spk = "mic_1" if (i // 5) % 2 == 0 else "mic_2"
        fr.append(ActivityFrame(t, t + 200,
                                {"mic_1": -20.0, "mic_2": -40.0},
                                {"mic_1": -50.0, "mic_2": -50.0},
                                20.0, spk, spk, 1.0))
        t += 200
    return fr


def _fs_session(tmp, root):
    base = tmp / root
    kb = _touch(base / "P8" / "KB.wav")
    m1 = _touch(base / "P8" / "MIC1.wav")
    m2 = _touch(base / "P8" / "MIC2.wav")
    c1 = _touch(base / "CAM_A.mp4")
    c2 = _touch(base / "CAM_B.mp4")
    proj = PeakCutProject()
    proj.set_files(kb, [m1, m2], [c1, c2])
    proj.guest_name = "Hartmut Rosa"
    s = PeakCutSession(proj, dict(_CFG))
    s.peaks = [Peak(0, 60000, context_ms=15000)]
    s.speaker_activity = _fs_frames()
    s.folgenschnitt_mic_assignments = [
        MicAssignment(0, m1, "Matze"), MicAssignment(1, m2, "Hartmut Rosa")]
    s.folgenschnitt_camera_assignments = [
        CameraAssignment(c1, SHOT_WIDE, "Matze"),
        CameraAssignment(c2, SHOT_WIDE, "Hartmut Rosa")]
    s.folgenschnitt_assignment_applied = True
    return s, base


def _cam_paths(session):
    prepare_folgenschnitt_for_export(session)
    return sorted({d.camera_path for d in session.folgenschnitt_edit_decisions})


def test_assignment_paths_follow_folder_move(tmp_path):
    s, base = _fs_session(tmp_path, "Mat")
    save_project_archive(s)
    moved = tmp_path / "Moved"
    base.rename(moved)
    L = load_project_archive(str(moved), dict(_CFG))
    for a in (L.folgenschnitt_mic_assignments
              + L.folgenschnitt_camera_assignments):
        assert a.path.startswith(str(moved)), a.path
        assert "Mat/" not in a.path or str(moved) in a.path
    for a in L.speaker_activity_mic_assignments:
        assert a.path.startswith(str(moved)), a.path


def test_folgenschnitt_roundtrip_identical_no_move(tmp_path):
    s, base = _fs_session(tmp_path, "Mat")
    before = _cam_paths(s)
    assert before  # Decisions tragen Kamerapfade
    save_project_archive(s)
    L = load_project_archive(str(base), dict(_CFG))
    after = _cam_paths(L)
    assert after == before, (before, after)


def test_folgenschnitt_roundtrip_new_root_after_move(tmp_path):
    s, base = _fs_session(tmp_path, "Mat")
    _cam_paths(s)
    save_project_archive(s)
    moved = tmp_path / "Moved"
    base.rename(moved)
    L = load_project_archive(str(moved), dict(_CFG))
    paths = _cam_paths(L)
    assert paths
    assert all(p.startswith(str(moved)) for p in paths), paths
    assert not any((str(tmp_path / "Mat") + os.sep) in p for p in paths), paths


# --- Task 3: .peakcut Schema v2 additiv ---

from core.clip_candidates import PROPOSED, DISCARDED, SELECTED


def test_schema_is_v2_and_archive_has_both_sections(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    path = save_project_archive(s)
    data = _json.loads(open(path).read())
    assert data["schema_version"] == 2
    assert "clip_candidates" in data and "peak_decisions" in data
    assert len(data["clip_candidates"]) == len(s.peaks)  # bootstrap je Peak


def test_v1_archive_without_sections_loads_and_bootstraps(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    path = save_project_archive(s)
    data = _json.loads(open(path).read())
    # v1 simulieren: Sektionen entfernen + Schema 1
    data["schema_version"] = 1
    del data["clip_candidates"]
    del data["peak_decisions"]
    open(path, "w").write(_json.dumps(data))
    L = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert len(L.clip_candidates) == len(L.peaks)  # aus Peaks gebootstrappt
    assert L.peak_decisions == []


def test_v2_clip_candidates_decisions_roundtrip_bitexact(tmp_path):
    s, *_ = _session(tmp_path, "Mat")
    save_project_archive(s)  # bootstrappt Candidates
    L1 = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    # einen Status legal ändern + erneut speichern/laden
    from core.clip_candidates import transition
    c0 = L1.clip_candidates[0]
    new, dec = transition(c0, SELECTED, now="2026-05-18T10:00:00")
    L1.clip_candidates[0] = new
    L1.peak_decisions.append(dec)
    save_project_archive(L1)
    L2 = load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
    assert [c.to_dict() for c in L2.clip_candidates] == \
        [c.to_dict() for c in L1.clip_candidates]
    assert [d.to_dict() for d in L2.peak_decisions] == \
        [d.to_dict() for d in L1.peak_decisions]
    assert L2.clip_candidates[0].status == SELECTED


def test_corrupt_v2_candidate_raises_projectarchiveerror(tmp_path):
    """Carl P2: semantisch kaputte v2-Akte -> ProjectArchiveError
    (nicht ClipCandidateError), damit main_window kontrolliert
    abfängt statt zu crashen."""
    from core.clip_candidates import ClipCandidateError
    s, *_ = _session(tmp_path, "Mat")
    path = save_project_archive(s)
    data = _json.loads(open(path).read())
    data["clip_candidates"][0]["status"] = "future_status"  # ungültig
    open(path, "w").write(_json.dumps(data))
    try:
        load_project_archive(str(tmp_path / "Mat"), dict(_CFG))
        assert False, "sollte ProjectArchiveError werfen"
    except ProjectArchiveError as e:
        assert "ClipCandidate-Daten unlesbar" in str(e)
    except ClipCandidateError:
        assert False, "ClipCandidateError darf NICHT roh rausfliegen"
