"""HC-4 Task 7 — GUI-Einhängung (Logik gezielt, ohne schweres
MainWindow-Konstrukt). _autosave darf NIE blocken/werfen;
_load_from_archive fällt bei kaputter Akte kontrolliert zurück."""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.main_window import MainWindow  # noqa: E402
from core.project_archive import ProjectArchiveError  # noqa: E402


def _statusbar():
    return types.SimpleNamespace(_msg=None,
                                 showMessage=lambda m, s=None: None)


def test_autosave_noop_without_session():
    fs = types.SimpleNamespace()
    MainWindow._autosave(fs)  # darf nicht werfen


def test_autosave_never_raises_on_save_failure(monkeypatch):
    import gui.main_window as mw
    monkeypatch.setattr(mw, "save_project_archive",
                        lambda s: (_ for _ in ()).throw(OSError("read-only")))
    msgs = []
    fs = types.SimpleNamespace(
        session=object(),
        statusbar=types.SimpleNamespace(showMessage=lambda m, *a: msgs.append(m)))
    MainWindow._autosave(fs)  # darf NICHT werfen (Beiwerk)
    assert any("nicht gespeichert" in m for m in msgs)


def test_load_from_archive_falls_back_on_broken(monkeypatch):
    import gui.main_window as mw
    monkeypatch.setattr(mw, "load_project_archive",
                        lambda a, c: (_ for _ in ()).throw(
                            ProjectArchiveError("unvollständig")))
    monkeypatch.setattr(mw.config, "load", lambda: {"fps": 25})
    msgs = []
    fs = types.SimpleNamespace(
        statusbar=types.SimpleNamespace(showMessage=lambda m, *a: msgs.append(m)))
    ok = MainWindow._load_from_archive(fs, "/x/.peakcut/project.json")
    assert ok is False  # Rückfall auf normalen Flow
    assert any("nicht ladbar" in m for m in msgs)


def test_load_from_archive_routes_to_review_when_applied(monkeypatch):
    import gui.main_window as mw

    fake_session = types.SimpleNamespace(
        project=types.SimpleNamespace(videos=["/m/CAM.mp4"], export_dir=None),
        folgenschnitt_assignment_applied=True)
    monkeypatch.setattr(mw, "load_project_archive",
                        lambda a, c: fake_session)
    monkeypatch.setattr(mw.config, "load", lambda: {"fps": 25})

    routed = {}
    fs = types.SimpleNamespace(
        _cli_export_dir=None,
        statusbar=types.SimpleNamespace(showMessage=lambda m, *a: None),
        stack=types.SimpleNamespace(
            setCurrentIndex=lambda i: routed.__setitem__("stack", i)),
        review_page=types.SimpleNamespace(
            set_session=lambda s, v: routed.__setitem__("review", True),
            navigate_to_peak=lambda i: None),
        assignment_page=types.SimpleNamespace(
            set_session=lambda s, v: routed.__setitem__("assign", True)))
    ok = MainWindow._load_from_archive(fs, "/m/.peakcut/project.json")
    assert ok is True
    assert routed.get("stack") == 3 and routed.get("review") is True
    assert "assign" not in routed  # applied -> direkt Review, nicht Zuordnung
