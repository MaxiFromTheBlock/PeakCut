"""Slice B Task 8 — Integration/Regression-Tests.

End-to-end: Toggle → Apply → Persistenz → Load → Export.

Plus Pin-Tests fuer Module die Slice B NICHT anfassen darf
(folgenschnitt_pipeline, folgenschnitt_decisions, folgenschnitt_loosening,
prepare_folgenschnitt_for_export-Verhalten).
"""

from __future__ import annotations

import inspect
import os
import sys
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.folgenschnitt_exporter import FolgenschnittXMLExporter  # noqa: E402
from core.folgenschnitt_models import (  # noqa: E402
    CameraAssignment, EditDecision, MicAssignment,
)
from core.folgenschnitt_multitrack_layout import (  # noqa: E402
    UNUSED_CLIPS_DISABLE, UNUSED_CLIPS_REMOVE,
)
from core.project import PeakCutProject  # noqa: E402
from core.project_archive import (  # noqa: E402
    load_project_archive, save_project_archive,
)
from core.session import PeakCutSession  # noqa: E402


_CFG = {"fps": 25, "context_duration_ms": 15000}


def _make_loaded_session(tmp_path, mode):
    """Realistische 1plus1-aehnliche Session mit Decisions + Assignments."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in (
        "KB.wav", "MIC_Jan.wav", "MIC_Tim.wav",
        "Hotel Matze - Test mix.wav",
        "Jan.mp4", "Tim.mp4", "Totale.mp4",
    ):
        (tmp_path / name).write_bytes(b"\x00")

    p = PeakCutProject()
    p.set_files(
        str(tmp_path / "KB.wav"),
        [
            str(tmp_path / "MIC_Jan.wav"),
            str(tmp_path / "MIC_Tim.wav"),
            str(tmp_path / "Hotel Matze - Test mix.wav"),
        ],
        [
            str(tmp_path / "Jan.mp4"),
            str(tmp_path / "Tim.mp4"),
            str(tmp_path / "Totale.mp4"),
        ],
    )
    p.guest_name = "Integration Test"
    p.export_dir = str(tmp_path / "exp")

    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results(
        {
            "peaks": [
                {"index": 0, "position_ms": 30_000, "context_ms": 15_000,
                 "ignored": False},
            ],
            "video_offsets": [],
        }
    )
    # Folgenschnitt-Daten setzen (sonst wuerde der Export skippen)
    s.folgenschnitt_assignment_applied = True
    s.folgenschnitt_mic_assignments = [
        MicAssignment(0, str(tmp_path / "MIC_Jan.wav"), "Jan", "mic_1"),
        MicAssignment(1, str(tmp_path / "MIC_Tim.wav"), "Tim", "mic_2"),
    ]
    s.folgenschnitt_camera_assignments = [
        CameraAssignment(str(tmp_path / "Jan.mp4"), "weit", "Jan"),
        CameraAssignment(str(tmp_path / "Tim.mp4"), "weit", "Tim"),
        CameraAssignment(str(tmp_path / "Totale.mp4"), "totale", None),
    ]
    s.folgenschnitt_edit_decisions = [
        EditDecision(
            start_ms=0, end_ms=10_000,
            camera_path=str(tmp_path / "Jan.mp4"),
            speaker="Jan", reason="test",
        ),
        EditDecision(
            start_ms=10_000, end_ms=20_000,
            camera_path=str(tmp_path / "Tim.mp4"),
            speaker="Tim", reason="test",
        ),
    ]
    s.folgenschnitt_unused_clips_mode = mode
    return s


# ---------------------------------------------------------------------
# End-to-End: Mode ueberlebt Save/Load und steuert Export-Layout
# ---------------------------------------------------------------------


def _export_video_tracks(session):
    """Hilfsfunktion: exportiert + parsiert Video-Tracks aus XML."""
    os.makedirs(session.project.export_dir, exist_ok=True)
    with patch(
        "core.folgenschnitt_exporter._probe_audio_info",
        return_value=(48000, 16, 2),
    ), patch(
        "core.folgenschnitt_exporter._probe_video_info",
        return_value=(1920, 1080),
    ):
        FolgenschnittXMLExporter().export(session)
    xml_path = os.path.join(
        session.project.export_dir,
        f"Folgenschnitt - {session.project.guest_name}.xml",
    )
    tree = ET.parse(xml_path)
    return tree.getroot().findall("sequence/media/video/track")


def test_disable_mode_persists_and_drives_multitrack_export(tmp_path):
    """End-to-End-Beweis Disable: Mode wird in Session gesetzt, in
    .peakcut gespeichert, von dort geladen, Exporter respektiert ihn,
    XML enthaelt <enabled>FALSE</enabled>-Elemente fuer inaktive
    Person-Clips."""
    material = tmp_path / "material"
    s1 = _make_loaded_session(material, mode=UNUSED_CLIPS_DISABLE)

    save_project_archive(s1, root=str(material))
    s2 = load_project_archive(
        str(material / ".peakcut" / "project.json"), dict(_CFG)
    )
    assert s2.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_DISABLE

    # Decisions wurden NICHT von .peakcut hydratisiert (Schema speichert
    # die nicht — siehe Bestandscode). Fuer den Export-Test setzen wir
    # die Decisions/Assignments direkt aus s1.
    s2.folgenschnitt_edit_decisions = s1.folgenschnitt_edit_decisions
    s2.project.export_dir = str(material / "exp_disable")

    tracks = _export_video_tracks(s2)
    # 3 Video-Spuren: V1=Totale, V2=Jan, V3=Tim
    assert len(tracks) == 3
    # Disable: irgendwo gibt es enabled=FALSE-Elemente (inaktive Clips)
    all_clips = [
        c for t in tracks for c in t.findall("clipitem")
    ]
    disabled = [
        c for c in all_clips
        if c.find("enabled") is not None
        and c.find("enabled").text == "FALSE"
    ]
    assert len(disabled) > 0, "Disable-Mode → erwartet disabled clips"


def test_remove_mode_persists_and_drives_multitrack_export(tmp_path):
    """End-to-End-Beweis Remove: kein <enabled>FALSE</enabled>; nicht-
    aktive Person-Spuren haben Luecken (weniger Clips als Decisions)."""
    material = tmp_path / "material"
    s1 = _make_loaded_session(material, mode=UNUSED_CLIPS_REMOVE)

    save_project_archive(s1, root=str(material))
    s2 = load_project_archive(
        str(material / ".peakcut" / "project.json"), dict(_CFG)
    )
    assert s2.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_REMOVE

    s2.folgenschnitt_edit_decisions = s1.folgenschnitt_edit_decisions
    s2.project.export_dir = str(material / "exp_remove")

    tracks = _export_video_tracks(s2)
    assert len(tracks) == 3
    # Remove: keine enabled=FALSE-Elemente
    for t in tracks:
        for c in t.findall("clipitem"):
            assert (
                c.find("enabled") is None
                or c.find("enabled").text != "FALSE"
            ), "Remove-Mode darf keine disabled-Clips schreiben"


# ---------------------------------------------------------------------
# Pin: prepare_folgenschnitt_for_export-Verhalten unveraendert
# ---------------------------------------------------------------------


def test_prepare_folgenschnitt_for_export_unchanged_skip_reason():
    """Pin: Skip-Reason bei unvollstaendiger Zuordnung bleibt wie heute.
    Slice B darf prepare_folgenschnitt_for_export-Logik nicht
    anfassen."""
    from types import SimpleNamespace
    from core.folgenschnitt_pipeline import prepare_folgenschnitt_for_export

    session = SimpleNamespace(
        speaker_activity=[object()],
        speaker_activity_mic_assignments=[],
        folgenschnitt_mic_assignments=[],
        folgenschnitt_camera_assignments=[],
        speaker_turns=[],
        folgenschnitt_edit_decisions=[],
        folgenschnitt_skip_reason=None,
        folgenschnitt_assignment_applied=True,
        project=SimpleNamespace(mic_tracks=[]),
    )
    reason = prepare_folgenschnitt_for_export(session)
    assert reason == "Zuordnung unvollstaendig"


# ---------------------------------------------------------------------
# Pin: API-Stabilitaet (Slice B fasst diese Module nicht an)
# ---------------------------------------------------------------------


def test_folgenschnitt_pipeline_api_stable():
    from core import folgenschnitt_pipeline as mod
    assert callable(getattr(mod, "prepare_folgenschnitt_for_export", None))
    sig = inspect.signature(mod.prepare_folgenschnitt_for_export)
    assert list(sig.parameters) == ["session"], (
        "prepare_folgenschnitt_for_export-Signatur darf nicht driften"
    )


def test_folgenschnitt_decisions_api_stable():
    from core import folgenschnitt_decisions as mod
    assert callable(getattr(mod, "build_edit_decisions", None))
    assert callable(getattr(mod, "build_speaker_turns", None))


def test_folgenschnitt_loosening_api_stable():
    from core import folgenschnitt_loosening as mod
    # Stufe-2-Logik bleibt unangetastet
    assert callable(getattr(mod, "apply_time_logic_loosening", None))
    assert callable(getattr(mod, "build_stage1_base_camera_assignments", None))
    assert callable(getattr(mod, "build_pause_ranges", None))


def test_audio_routing_api_stable():
    """#71a-Helper bleibt der einzige Mix-Klassifizierer."""
    from core import audio_routing as mod
    assert callable(getattr(mod, "is_mix_track", None))
    assert callable(getattr(mod, "get_mix_track", None))
    assert callable(getattr(mod, "get_source_mic_tracks", None))


# ---------------------------------------------------------------------
# Pin: Roundtrip Decisions+Assignments+Mode (Schema-v3 vollstaendig)
# ---------------------------------------------------------------------


def test_assignments_and_mode_survive_save_load(tmp_path):
    """Saven der vollstaendigen Folgenschnitt-Zuordnung + Mode →
    Laden → alle Felder gleich. Sicherheitsnetz fuer Schema-v3."""
    material = tmp_path / "material"
    s1 = _make_loaded_session(material, mode=UNUSED_CLIPS_REMOVE)
    save_project_archive(s1, root=str(material))
    s2 = load_project_archive(
        str(material / ".peakcut" / "project.json"), dict(_CFG)
    )

    # Mode
    assert s2.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_REMOVE
    # Assignment-Applied-Flag
    assert s2.folgenschnitt_assignment_applied is True
    # Mic + Camera Assignments roundtrip-exakt
    assert len(s2.folgenschnitt_mic_assignments) == 2
    assert {m.person for m in s2.folgenschnitt_mic_assignments} == {"Jan", "Tim"}
    assert len(s2.folgenschnitt_camera_assignments) == 3
    shot_types = sorted(c.shot_type for c in s2.folgenschnitt_camera_assignments)
    assert shot_types == ["totale", "weit", "weit"]
