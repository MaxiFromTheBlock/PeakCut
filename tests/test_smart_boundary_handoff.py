"""Roadmap #3 Task 8 — ReviewPage-Hook NACH dem Export-Handoff (Carl).

SmartBoundaryWorker startet als LETZTE Aktion in _on_export_done
(nach session_changed.emit, Erfolgspfad), NIE aus _on_export_error.
Notbremse-gated. cleanup() bricht den Worker HC-2-sauber ab. Der
finished-Handler schreibt die Sinnabschnitte-Zusatzdateien guarded
und stößt Autosave an. Unbound-Method gegen Fake-self — kein
schweres ReviewPage-Konstrukt.
"""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402
from core.clip_boundary.decider import ClaudeBoundaryDecider  # noqa: E402


class _Sig:
    def __init__(self, name, events):
        self._name, self._events = name, events

    def emit(self, *a):
        self._events.append(self._name)

    def connect(self, _cb):
        pass


class _FakeSmart:
    instances = []

    def __init__(self, session, decider):
        self.session, self.decider = session, decider
        self.started = self.stopped = False
        self.wait_ms = None
        self._running = True
        self.finished = types.SimpleNamespace(connect=lambda cb: None)
        self.progress = types.SimpleNamespace(connect=lambda cb: None)
        _FakeSmart.instances.append(self)

    def start(self):
        self.started = True

    def request_stop(self):
        self.stopped = True

    def isRunning(self):
        return self._running

    def wait(self, ms):
        self.wait_ms = ms
        self._running = False


def _fake_self(events, enabled=True):
    ns = types.SimpleNamespace()
    ns.session = types.SimpleNamespace(
        project=types.SimpleNamespace(export_dir="/tmp/x"),
        config={"smart_boundary_enabled": enabled,
                "smart_boundary_claude_model": "claude-x"},
        clip_candidates=[])
    ns.export_btn = types.SimpleNamespace(setEnabled=lambda v: None)
    ns.status_message = _Sig("status", events)
    ns.session_changed = _Sig("session_changed", events)
    ns._export_worker = types.SimpleNamespace(deleteLater=lambda: None)
    ns._smart_worker = None
    ns._on_smart_boundaries_done = lambda c: None  # echte Methode separat getestet
    return ns


def _patched_smart(events):
    class S(_FakeSmart):
        def start(self):
            self.started = True
            events.append("smart_start")
    return S


def test_smart_starts_after_session_changed_only_when_enabled():
    events = []
    fs = _fake_self(events, enabled=True)
    with patch("gui.review_page.SmartBoundaryWorker", _patched_smart(events)):
        ReviewPage._on_export_done(fs, ["a.xml"])
    # Smart startet NACH session_changed (relative Reihenfolge zählt)
    assert events.count("smart_start") == 1
    assert events.index("session_changed") < events.index("smart_start")
    assert fs._smart_worker is not None
    assert isinstance(fs._smart_worker.decider, ClaudeBoundaryDecider)


def test_disabled_notbremse_no_smart_worker():
    events = []
    fs = _fake_self(events, enabled=False)
    with patch("gui.review_page.SmartBoundaryWorker", _patched_smart(events)):
        ReviewPage._on_export_done(fs, ["a.xml"])
    assert "smart_start" not in events       # Notbremse: nichts gestartet
    assert fs._smart_worker is None


def test_export_error_never_starts_smart():
    events = []
    fs = _fake_self(events)
    fs._log = None
    with patch("gui.review_page.SmartBoundaryWorker") as Smart:
        ReviewPage._on_export_error(fs, "Boom")
    Smart.assert_not_called()
    assert fs._smart_worker is None


def test_cleanup_stops_smart_worker_bounded():
    events = []
    fs = _fake_self(events)
    fs._play_timer = types.SimpleNamespace(stop=lambda: None)
    fs.video_preview = types.SimpleNamespace(cleanup=lambda: None)
    fs._export_worker = None
    sw = _FakeSmart(fs.session, None)
    fs._smart_worker = sw
    ReviewPage.cleanup(fs)
    assert sw.stopped is True
    assert sw.wait_ms is not None             # bounded wait


def test_finished_handler_runs_exporters_guarded_and_autosaves():
    events = []
    fs = _fake_self(events)
    calls = []
    with patch("gui.review_page.SinnabschnittTXTExporter") as T, \
         patch("gui.review_page.SinnabschnittXMLExporter") as X:
        T.return_value.export = lambda s: calls.append("txt")
        X.return_value.export = lambda s: calls.append("xml")
        ReviewPage._on_smart_boundaries_done(fs, fs.session.clip_candidates)
    assert calls == ["txt", "xml"]
    assert "session_changed" in events        # Autosave angestossen

    # Exporter-Fehler darf den Flow nie brechen
    events2 = []
    fs2 = _fake_self(events2)
    with patch("gui.review_page.SinnabschnittTXTExporter") as T2, \
         patch("gui.review_page.SinnabschnittXMLExporter"):
        T2.return_value.export = lambda s: (_ for _ in ()).throw(
            RuntimeError("kaputt"))
        ReviewPage._on_smart_boundaries_done(fs2, [])
    assert "session_changed" in events2       # trotzdem persistiert
