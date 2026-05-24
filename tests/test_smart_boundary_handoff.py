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

import pytest

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
    # #3-Rev Task 7: Riegel-Flags + Helfer als Unbound-Auflösung.
    ns._base_export_done_for_run = False
    ns._smart_ready = False
    ns._sinnabschnitt_artifacts_written = False
    ns._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(ns)
    ns._refresh_smart_status = lambda: None
    ns._refresh_sinn_btn = lambda: None
    return ns


def _patched_smart(events):
    class S(_FakeSmart):
        def start(self):
            self.started = True
            events.append("smart_start")
    return S


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
    # Task-7-Riegel: Smart fertig + Basis-Export schon durch
    # -> Zusatzdateien schreiben + autosave.
    events = []
    fs = _fake_self(events)
    fs._base_export_done_for_run = True
    fs._smart_ready = False
    fs._sinnabschnitt_artifacts_written = False
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
    fs2._base_export_done_for_run = True
    fs2._smart_ready = False
    fs2._sinnabschnitt_artifacts_written = False
    with patch("gui.review_page.SinnabschnittTXTExporter") as T2, \
         patch("gui.review_page.SinnabschnittXMLExporter"):
        T2.return_value.export = lambda s: (_ for _ in ()).throw(
            RuntimeError("kaputt"))
        ReviewPage._on_smart_boundaries_done(fs2, [])
    assert "session_changed" in events2       # trotzdem persistiert


# ══════════════════════════════════════════════════════════════════════
# #3-Revision Task 0 — Safety-Harness: Soll-Zustand des Handoffs (Spec
# §11 R1 / Gate 0) als ausführbare Spezifikation einfrieren. Absichtlich
# VOR der Umsetzung geschrieben. xfail(strict) markiert genau das, was
# erst der jeweilige Revisions-Task grün macht — so bleibt jeder Commit
# grün (kein roter Test auf develop), die Invariante ist aber sofort
# dokumentiert und schlägt automatisch zu, sobald ihr Task sie erfüllt.
# ══════════════════════════════════════════════════════════════════════


def test_rev_on_export_done_does_not_start_smart_worker():
    """R1 (Task 6 erfüllt): Der Export-Handoff stößt Job B nicht mehr
    an — Job B läuft im Review-Hintergrund (_maybe_start_smart_worker)."""
    events = []
    fs = _fake_self(events, enabled=True)
    with patch("gui.review_page.SmartBoundaryWorker", _patched_smart(events)):
        ReviewPage._on_export_done(fs, ["a.xml"])
    assert "smart_start" not in events
    assert fs._smart_worker is None


def test_rev_sinnabschnitt_never_in_base_export_handoff():
    """Gate 0 (durabel grün): die an _on_export_done übergebene
    exported-Liste ist der reine Basis-Export; _on_export_done schreibt
    selbst nie eine Sinnabschnitt-Datei und ergänzt die Liste nicht."""
    events = []
    fs = _fake_self(events, enabled=False)   # Notbremse: nur Basis-Pfad
    exported = ["Keyboardstellen - X.xml", "Keyboardstellen - X.mp3",
                "Keyboardstellen - X.txt"]
    with patch("gui.review_page.SinnabschnittTXTExporter") as T, \
         patch("gui.review_page.SinnabschnittXMLExporter") as X:
        ReviewPage._on_export_done(fs, exported)
        T.assert_not_called()
        X.assert_not_called()
    assert not any("Sinnabschnitt" in p for p in exported)
    assert fs._smart_worker is None


def test_rev_no_sinnabschnitt_artifact_before_base_export():
    """Gate 0: Wird Smart fertig BEVOR der Basis-Export durch ist, darf
    noch keine Sinnabschnitt-Datei entstehen."""
    events = []
    fs = _fake_self(events)
    fs._base_export_done_for_run = False     # Basis-Export NICHT fertig
    written = []
    with patch("gui.review_page.SinnabschnittTXTExporter") as T, \
         patch("gui.review_page.SinnabschnittXMLExporter") as X:
        T.return_value.export = lambda s: written.append("txt")
        X.return_value.export = lambda s: written.append("xml")
        ReviewPage._on_smart_boundaries_done(fs, fs.session.clip_candidates)
    assert written == []
