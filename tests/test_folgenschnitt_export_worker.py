from types import SimpleNamespace

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
