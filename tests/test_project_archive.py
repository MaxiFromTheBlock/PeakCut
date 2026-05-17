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
