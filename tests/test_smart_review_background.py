"""#3-Revision Task 6 — Job B in den Review-Hintergrund (Spec §11 R1).

Carl Task 6 + Pin 2: SmartBoundaryWorker startet NICHT mehr aus
_on_export_done, sondern aus ReviewPage._maybe_start_smart_worker(),
aufgerufen aus set_session() und aus MainWindow nach
TranscriptWorker.finished (nur bei echtem Ref, nicht bei {}).
Deterministisch — kein echter Worker-Thread, kein echtes Whisper/
Claude. ReviewPage-Methoden werden unbound gegen _fake_self getestet.
"""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402


# --- Test-Harness wie test_smart_boundary_handoff.py -------------------

class _Sig:
    def __init__(self, name, events):
        self._n, self._ev = name, events

    def emit(self, *a):
        self._ev.append(self._n)

    def connect(self, _cb):
        pass


class _FakeSmart:
    def __init__(self, session, decider):
        self.session, self.decider = session, decider
        self.started = False
        self._running = False
        self.finished = types.SimpleNamespace(connect=lambda cb: None)
        self.progress = types.SimpleNamespace(connect=lambda cb: None)

    def start(self):
        self.started = True
        self._running = True

    def isRunning(self):
        return self._running

    def request_stop(self):
        pass


class _Cand:
    def __init__(self, score=None):
        self.score = score


def _fake_self(events, *, enabled=True, peaks=True, transcript=True,
               scores_present=False, running=False):
    ns = types.SimpleNamespace()
    cfg = {"smart_boundary_enabled": enabled,
           "smart_boundary_claude_model": "claude-x"}
    ns.session = types.SimpleNamespace(
        project=types.SimpleNamespace(export_dir="/tmp/x"),
        config=cfg,
        peaks=([1, 2] if peaks else []),
        transcript=("Transcript" if transcript else None),
        transcript_ref=({"path": "x"} if transcript else None),
        clip_candidates=([_Cand(0.7)] if scores_present else
                          [_Cand(None), _Cand(None)]))
    ns.status_message = _Sig("status", events)
    ns.session_changed = _Sig("session_changed", events)
    ns._smart_worker = _FakeSmart(ns.session, None) if running else None
    if running:
        ns._smart_worker.started = True
        ns._smart_worker._running = True       # tut wirklich laufen
    # #3-Rev Task 7: Riegel-Flags + Helfer als Unbound-Auflösung.
    ns._base_export_done_for_run = False
    ns._smart_ready = False
    ns._sinnabschnitt_artifacts_written = False
    ns._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(ns)
    return ns


def _patched_smart(events):
    class S(_FakeSmart):
        def start(self):
            self.started = True
            events.append("smart_start")
    return S


# --- _maybe_start_smart_worker: Gate-Bedingungen -----------------------

def _try_start(fs, events):
    with patch("gui.review_page.SmartBoundaryWorker",
                _patched_smart(events)):
        ReviewPage._maybe_start_smart_worker(fs)
    return fs


def test_starts_when_all_conditions_met():
    events = []
    fs = _try_start(_fake_self(events), events)
    assert "smart_start" in events
    assert fs._smart_worker is not None


def test_blocked_when_notbremse_off():
    events = []
    _try_start(_fake_self(events, enabled=False), events)
    assert "smart_start" not in events


def test_blocked_when_no_peaks():
    events = []
    _try_start(_fake_self(events, peaks=False), events)
    assert "smart_start" not in events


def test_blocked_when_no_transcript():
    events = []
    _try_start(_fake_self(events, transcript=False), events)
    assert "smart_start" not in events


def test_blocked_when_worker_already_running():
    events = []
    fs = _fake_self(events, running=True)
    _try_start(fs, events)
    # nichts neu gestartet — der laufende Worker bleibt unangetastet
    assert events.count("smart_start") == 0


def test_blocked_when_transcript_error_is_set_even_with_ref():
    # Carl-Gegenreview [P2]: geladene Akte mit transcript_ref UND
    # gesetztem transcript_error (kaputtes/fehlendes Sidecar) darf
    # Job B NICHT anstoßen — sonst Churn in INFRA_FEHLT.
    events = []
    fs = _fake_self(events, transcript=False)
    fs.session.transcript_ref = {"path": "x",
                                  "audio_fingerprint": {"size": 1}}
    fs.session.transcript_error = "Sidecar kaputt/fehlt"
    _try_start(fs, events)
    assert "smart_start" not in events


def test_blocked_when_smart_scores_already_present():
    # Spec/Carl: keine doppelte teure Berechnung — wenn schon Scores
    # in den Candidates stehen, nicht neu starten.
    events = []
    _try_start(_fake_self(events, scores_present=True), events)
    assert "smart_start" not in events


# --- set_session ruft _maybe_start_smart_worker ------------------------

def test_set_session_invokes_maybe_start():
    # Nur die Aufruf-Verkettung verifizieren — Inhalt von set_session
    # macht echte Qt-Sachen, daher nicht hier komplett ausführen.
    called = {}
    fs = types.SimpleNamespace(
        camera_combo=types.SimpleNamespace(
            clear=lambda: None, addItem=lambda *a, **kw: None),
        video_preview=types.SimpleNamespace(
            set_videos=lambda v: None, set_session=lambda s: None,
            screenshot_done=types.SimpleNamespace(connect=lambda cb: None)),
        _populate_lut_combo=lambda: None,
        _maybe_start_smart_worker=lambda: called.setdefault("yes", True),
        camera_label=types.SimpleNamespace(setText=lambda t: None))
    session = types.SimpleNamespace(folgenschnitt_camera_assignments=[])
    ReviewPage.set_session(fs, session, [])
    assert called.get("yes") is True


# --- Handler nach TranscriptWorker.finished (Pin 2) --------------------

class _Review:
    def __init__(self):
        self.notified = 0

    def _maybe_start_smart_worker(self):
        self.notified += 1


def test_transcript_finished_handler_skips_on_empty_ref():
    # Pin 2: {} = kontrollierter Skip -> kein Job B.
    from gui.main_window import _on_transcript_finished
    rv = _Review()
    autosaves = []
    _on_transcript_finished({}, autosave=lambda: autosaves.append(1),
                              review=rv)
    assert autosaves == [1]
    assert rv.notified == 0


def test_transcript_finished_handler_starts_review_on_real_ref():
    from gui.main_window import _on_transcript_finished
    rv = _Review()
    autosaves = []
    _on_transcript_finished(
        {"path": ".peakcut/transcript.json", "audio_fingerprint": {"size": 1}},
        autosave=lambda: autosaves.append(1), review=rv)
    assert autosaves == [1]
    assert rv.notified == 1


def test_transcript_finished_handler_skips_review_when_ref_lacks_fingerprint():
    # Pin 2: ref ohne audio_fingerprint zählt als Fortschritt/Stub,
    # nicht als Trigger für Job B.
    from gui.main_window import _on_transcript_finished
    rv = _Review()
    _on_transcript_finished({"path": "x"}, autosave=lambda: None, review=rv)
    assert rv.notified == 0
