"""Roadmap #3 Task 9 — Verifizierungs-Vorschau + P2-Race-Fix (Carl).

Vorschau: spielt den Sinnabschnitt des aktuellen Drückers via
video_preview.play_from(boundary). P2 (Carl Gate-8): finished-Handler
an die konkrete Worker-Instanz gebunden — ein alter Worker, der spät
fertig wird, räumt NICHT den neuen auf. Unbound-Method gegen
Fake-self, kein echter Mediendecode.
"""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402
from core.clip_candidates import (  # noqa: E402
    ClipCandidate, ClipBoundary, PROPOSED)


class _Sig:
    def __init__(self, ev, name):
        self._ev, self._name = ev, name

    def emit(self, *a):
        self._ev.append((self._name, a))

    def connect(self, cb):
        self._cb = cb


class _Worker:
    def __init__(self):
        self.deleted = False
        self.finished = _Sig([], "finished")
        self.progress = _Sig([], "progress")
        self.started = False

    def start(self):
        self.started = True

    def deleteLater(self):
        self.deleted = True


def _fs(events):
    ns = types.SimpleNamespace()
    ns.session = types.SimpleNamespace(
        project=types.SimpleNamespace(export_dir="/tmp/x"),
        config={"smart_boundary_enabled": True,
                "smart_boundary_claude_model": "m"},
        clip_candidates=[], peaks=[], current_peak=0)
    ns.export_btn = types.SimpleNamespace(setEnabled=lambda v: None)
    ns.status_message = _Sig(events, "status")
    ns.session_changed = _Sig(events, "session_changed")
    ns._export_worker = types.SimpleNamespace(deleteLater=lambda: None)
    ns._smart_worker = None
    ns.video_preview = types.SimpleNamespace(
        play_from=lambda a, b: events.append(("play_from", a, b)))
    ns._stop_play_state = lambda: events.append(("stop_play_state",))
    # #3-Rev Task 7: Riegel-Flags + Helfer als Unbound-Auflösung.
    ns._base_export_done_for_run = False
    ns._smart_ready = False
    ns._sinnabschnitt_artifacts_written = False
    ns._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(ns)
    ns._refresh_smart_status = lambda: None
    ns._refresh_sinn_btn = lambda: None
    return ns


# --- P2: alter Worker darf den neuen nicht aufräumen -------------------

def test_stale_worker_finish_does_not_clear_new_worker():
    # #3-Rev Task 6 (R1): Smart startet jetzt im Review-Hintergrund,
    # nicht in _on_export_done. Race-Schutz im Handler bleibt aber
    # gleich wichtig — Worker direkt setzen und den Handler prüfen.
    events = []
    fs = _fs(events)
    w1, w2 = _Worker(), _Worker()
    # w2 ist aktuell, w1 ist "alt" (spät fertig).
    fs._smart_worker = w2

    with patch("gui.review_page.SinnabschnittTXTExporter"), \
         patch("gui.review_page.SinnabschnittXMLExporter"):
        ReviewPage._on_smart_boundaries_done(fs, [], w1)
        assert fs._smart_worker is w2              # nicht durch alt aufgeräumt
        assert w1.deleted is True                  # alter trotzdem entsorgt
        ReviewPage._on_smart_boundaries_done(fs, [], w2)
        assert fs._smart_worker is None
        assert w2.deleted is True


# --- Vorschau ----------------------------------------------------------

def test_preview_plays_candidate_boundary_and_shows_meta():
    events = []
    fs = _fs(events)
    fs.session.peaks = [types.SimpleNamespace(index=7, position_ms=120000)]
    fs.session.current_peak = 0
    fs.session.clip_candidates = [ClipCandidate(
        peak_id=7, boundary=ClipBoundary(95000, 150000), status=PROPOSED,
        reason="Frage bis Pointe", score=0.82)]
    ReviewPage._on_play_sinnabschnitt(fs)
    assert ("play_from", 95000, 150000) in events
    txt = " ".join(str(a) for n, *a in events if n == "status")
    assert "0.82" in txt and "Frage bis Pointe" in txt


def test_preview_stops_running_audio_before_video(tmp_path=None):
    events = []
    fs = _fs(events)
    fs.session.peaks = [types.SimpleNamespace(index=7, position_ms=120000)]
    fs.session.current_peak = 0
    fs.session.clip_candidates = [ClipCandidate(
        peak_id=7, boundary=ClipBoundary(95000, 150000), status=PROPOSED,
        reason="r", score=0.5)]
    with patch("gui.review_page.stop_playback") as sp:
        ReviewPage._on_play_sinnabschnitt(fs)
    sp.assert_called_once()
    names = [e[0] for e in events]
    # Audio-Stop + Play-State-Reset VOR play_from
    assert names.index("stop_play_state") < names.index("play_from")


def test_preview_without_candidate_is_graceful_no_play():
    events = []
    fs = _fs(events)
    fs.session.peaks = [types.SimpleNamespace(index=3, position_ms=1000)]
    fs.session.current_peak = 0
    fs.session.clip_candidates = []            # kein Kandidat
    ReviewPage._on_play_sinnabschnitt(fs)      # darf nicht krachen
    assert not any(n == "play_from" for n, *_ in events)
    assert any(n == "status" for n, *_ in events)   # Hinweis


def test_preview_no_session_is_noop():
    events = []
    fs = _fs(events)
    fs.session = None
    ReviewPage._on_play_sinnabschnitt(fs)      # kein Crash
    assert not any(n == "play_from" for n, *_ in events)
