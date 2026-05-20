"""#3-Revision Task 7 — Zwei-Bedingungen-Barriere (Carl Task 7).

Sinnabschnitt-Zusatzdateien (TXT/XML) entstehen GENAU dann, wenn:
- Basis-Export fertig
- Smart-Lauf bereit (kein INFRA_FEHLT)
- noch nicht geschrieben
Beide Reihenfolgen testen (Smart→Export und Export→Smart). INFRA
blockiert die Dateien komplett. Neuer Smart-Lauf setzt das
„geschrieben"-Flag zurück.
"""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402
from core.clip_boundary.models import (  # noqa: E402
    BoundaryOutcome, SmartBoundaryRunResult)


class _Sig:
    def __init__(self, name, events):
        self._n, self._ev = name, events

    def emit(self, *a):
        self._ev.append(self._n)

    def connect(self, _cb):
        pass


def _fs(events):
    ns = types.SimpleNamespace()
    ns.session = types.SimpleNamespace(
        project=types.SimpleNamespace(export_dir="/tmp/x"),
        config={"smart_boundary_enabled": True}, clip_candidates=[])
    ns.export_btn = types.SimpleNamespace(setEnabled=lambda v: None)
    ns.status_message = _Sig("status", events)
    ns.session_changed = _Sig("session_changed", events)
    ns._export_worker = types.SimpleNamespace(deleteLater=lambda: None)
    ns._smart_worker = None
    # Task-7-State-Flags (in echter ReviewPage __init__/set_session
    # initialisiert — Tests setzen sie explizit, wo nötig).
    ns._base_export_done_for_run = False
    ns._smart_ready = False
    ns._sinnabschnitt_artifacts_written = False
    # Unbound-Pattern: die Hilfsmethode auf das Fake-Self auflösen.
    ns._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(ns)
    # #3-Rev Task 8: Status/Button-Refresh sind hier nicht im Fokus.
    ns._refresh_smart_status = lambda: None
    ns._refresh_sinn_btn = lambda: None
    return ns


_OK = SmartBoundaryRunResult((), BoundaryOutcome.OK, "", 1, 0)
_INFRA = SmartBoundaryRunResult((), BoundaryOutcome.INFRA_FEHLT,
                                  "kein Key", 0, 0)


def _patched_exporters(written):
    def _txt():
        m = types.SimpleNamespace()
        m.export = lambda s: written.append("txt")
        return m

    def _xml():
        m = types.SimpleNamespace()
        m.export = lambda s: written.append("xml")
        return m
    return _txt, _xml


# --- Beide Reihenfolgen schreiben einmal -------------------------------

def test_smart_then_export_writes_once():
    events, written = [], []
    fs = _fs(events)
    txt, xml = _patched_exporters(written)
    with patch("gui.review_page.SinnabschnittTXTExporter", txt), \
         patch("gui.review_page.SinnabschnittXMLExporter", xml):
        ReviewPage._on_smart_boundaries_done(fs, _OK)
        assert written == []                       # noch kein Export
        ReviewPage._on_export_done(fs, ["a.xml"])
        assert written == ["txt", "xml"]           # jetzt erst
        assert fs._sinnabschnitt_artifacts_written is True


def test_export_then_smart_writes_once():
    events, written = [], []
    fs = _fs(events)
    txt, xml = _patched_exporters(written)
    with patch("gui.review_page.SinnabschnittTXTExporter", txt), \
         patch("gui.review_page.SinnabschnittXMLExporter", xml):
        ReviewPage._on_export_done(fs, ["a.xml"])
        assert written == []                       # noch kein Smart
        ReviewPage._on_smart_boundaries_done(fs, _OK)
        assert written == ["txt", "xml"]
        assert fs._sinnabschnitt_artifacts_written is True


# --- INFRA blockiert komplett ------------------------------------------

def test_infra_never_writes_even_after_export():
    events, written = [], []
    fs = _fs(events)
    txt, xml = _patched_exporters(written)
    with patch("gui.review_page.SinnabschnittTXTExporter", txt), \
         patch("gui.review_page.SinnabschnittXMLExporter", xml):
        ReviewPage._on_export_done(fs, ["a.xml"])
        ReviewPage._on_smart_boundaries_done(fs, _INFRA)
        assert written == []                       # nie geschrieben
        assert fs._sinnabschnitt_artifacts_written is False
    assert "status" in events                      # lauter Hinweis


# --- Idempotenz: zweiter Export schreibt nicht doppelt -----------------

def test_second_export_does_not_rewrite_artifacts():
    events, written = [], []
    fs = _fs(events)
    txt, xml = _patched_exporters(written)
    with patch("gui.review_page.SinnabschnittTXTExporter", txt), \
         patch("gui.review_page.SinnabschnittXMLExporter", xml):
        ReviewPage._on_smart_boundaries_done(fs, _OK)
        ReviewPage._on_export_done(fs, ["a.xml"])
        assert written == ["txt", "xml"]
        fs._export_worker = types.SimpleNamespace(deleteLater=lambda: None)
        ReviewPage._on_export_done(fs, ["a.xml"])  # 2. Export
        assert written == ["txt", "xml"]            # unverändert


# --- Neuer Smart-Lauf setzt das geschrieben-Flag zurück ----------------

def test_starting_new_smart_worker_resets_artifacts_flag():
    # Vorbedingungen für _maybe_start_smart_worker erfüllen.
    events = []
    fs = _fs(events)
    fs.session.peaks = [1, 2]
    fs.session.transcript = "T"
    fs.session.transcript_error = None
    fs._sinnabschnitt_artifacts_written = True     # Vorlauf hat geschrieben
    fs._smart_ready = True

    class _FakeSmart:
        def __init__(self, *_a):
            self.started = False
            self.finished = types.SimpleNamespace(connect=lambda cb: None)
            self.progress = types.SimpleNamespace(connect=lambda cb: None)

        def start(self):
            self.started = True

        def isRunning(self):
            return False

    with patch("gui.review_page.SmartBoundaryWorker", _FakeSmart):
        ReviewPage._maybe_start_smart_worker(fs)
    assert fs._sinnabschnitt_artifacts_written is False
    assert fs._smart_ready is False                # neue Berechnung läuft


# --- set_session setzt die Flags zurück (neuer Stand, neuer Lauf) -----

def test_persisted_smart_results_open_barrier_without_new_worker():
    # Carl-Gegenreview [P2]: lädt man eine .peakcut mit schon
    # berechneten Smart-Scores, startet (richtig) kein neuer Worker —
    # aber der Riegel muss trotzdem aufgehen, sonst schreibt der
    # nächste Basis-Export keine TXT/XML obwohl alles bereit wäre.
    events, written = [], []
    fs = _fs(events)
    fs.session.peaks = [1, 2]
    fs.session.transcript = "T"
    fs.session.transcript_error = None
    # Bereits berechneter Stand (z. B. aus geladener Akte).
    fs.session.clip_candidates = [
        types.SimpleNamespace(score=0.8),
        types.SimpleNamespace(score=None)]

    class _FakeSmart:
        def __init__(self, *_a):
            self.started = False
            self.finished = types.SimpleNamespace(connect=lambda cb: None)
            self.progress = types.SimpleNamespace(connect=lambda cb: None)

        def start(self):
            self.started = True

        def isRunning(self):
            return False

    txt, xml = _patched_exporters(written)
    with patch("gui.review_page.SmartBoundaryWorker", _FakeSmart), \
         patch("gui.review_page.SinnabschnittTXTExporter", txt), \
         patch("gui.review_page.SinnabschnittXMLExporter", xml):
        ReviewPage._maybe_start_smart_worker(fs)
        # KEIN neuer Worker — und Smart-Seite des Riegels offen.
        assert fs._smart_worker is None
        assert fs._smart_ready is True
        # Bisher kein Export -> noch nicht geschrieben.
        assert written == []
        # Basis-Export folgt -> jetzt einmal schreiben.
        ReviewPage._on_export_done(fs, ["a.xml"])
        assert written == ["txt", "xml"]
        assert fs._sinnabschnitt_artifacts_written is True


def test_set_session_resets_barrier_flags():
    events = []
    fs = types.SimpleNamespace(
        camera_combo=types.SimpleNamespace(
            clear=lambda: None, addItem=lambda *a, **kw: None),
        video_preview=types.SimpleNamespace(
            set_videos=lambda v: None, set_session=lambda s: None,
            screenshot_done=types.SimpleNamespace(connect=lambda cb: None)),
        _populate_lut_combo=lambda: None,
        _maybe_start_smart_worker=lambda: None,
        _refresh_smart_status=lambda: None,
        _refresh_sinn_btn=lambda: None,
        camera_label=types.SimpleNamespace(setText=lambda t: None),
        _base_export_done_for_run=True,
        _smart_ready=True,
        _sinnabschnitt_artifacts_written=True)
    session = types.SimpleNamespace(folgenschnitt_camera_assignments=[])
    ReviewPage.set_session(fs, session, [])
    assert fs._base_export_done_for_run is False
    assert fs._smart_ready is False
    assert fs._sinnabschnitt_artifacts_written is False
