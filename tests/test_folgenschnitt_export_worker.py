from types import SimpleNamespace

from core.folgenschnitt_pipeline import prepare_folgenschnitt_for_export
from gui.workers import _build_exporters


def test_build_exporters_skips_folgenschnitt_without_decisions():
    session = SimpleNamespace(folgenschnitt_edit_decisions=[])

    exporters = _build_exporters(session)
    names = [type(exporter).__name__ for exporter in exporters]

    assert names == ["MP3Exporter", "TXTExporter", "XMLExporter"]


def test_build_exporters_adds_folgenschnitt_when_decisions_exist():
    session = SimpleNamespace(folgenschnitt_edit_decisions=[object()])

    exporters = _build_exporters(session)
    names = [type(exporter).__name__ for exporter in exporters]

    assert names == ["MP3Exporter", "TXTExporter", "XMLExporter", "FolgenschnittXMLExporter"]


def test_incomplete_folgenschnitt_keeps_only_base_exporters():
    """Hard guardrail: incomplete assignment must never block Keyboardstellen."""
    session = SimpleNamespace(
        speaker_activity=[object()],
        speaker_activity_mic_assignments=[],
        folgenschnitt_mic_assignments=[],
        folgenschnitt_camera_assignments=[],
        speaker_turns=[],
        folgenschnitt_edit_decisions=[],
        folgenschnitt_skip_reason=None,
        project=SimpleNamespace(mic_tracks=[]),
    )

    reason = prepare_folgenschnitt_for_export(session)

    assert reason == "Zuordnung unvollstaendig"
    assert session.folgenschnitt_edit_decisions == []

    names = [type(exporter).__name__ for exporter in _build_exporters(session)]
    assert names == ["MP3Exporter", "TXTExporter", "XMLExporter"]
