"""HC-2 Task 4 — closeEvent muss den Worker NUR über die öffentliche
Lifecycle-API beenden (request_stop + bounded wait), nie über
_worker._process. Getestet als unbound method gegen ein minimales
Fake-self (kein schweres MainWindow-Konstrukt nötig)."""

import os
import sys
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.main_window import MainWindow, _WORKER_SHUTDOWN_WAIT_MS  # noqa: E402


class _FakeWorker:
    def __init__(self, running=True):
        self._running = running
        self.stop_called = False
        self.wait_called_with = None

    # bewusst KEIN _process-Attribut
    def request_stop(self):
        self.stop_called = True

    def isRunning(self):
        return self._running

    def wait(self, ms):
        self.wait_called_with = ms
        self._running = False


def _fake_self(worker):
    ns = types.SimpleNamespace()
    ns.assignment_page = types.SimpleNamespace(cleanup=lambda: None)
    ns.review_page = types.SimpleNamespace(cleanup=lambda: None)
    ns._worker = worker
    ns._autosave = lambda: None  # HC-4: closeEvent autosaved jetzt (orthogonal)
    ns._transcript_worker = None  # Roadmap #3: orthogonal (kein A/B-Mix)
    return ns


def test_close_event_uses_request_stop_not_process():
    worker = _FakeWorker(running=True)
    ev = types.SimpleNamespace(accepted=False,
                               accept=lambda: setattr(ev, "accepted", True))
    fs = _fake_self(worker)
    with patch("gui.main_window.stop_playback"):
        MainWindow.closeEvent(fs, ev)
    assert worker.stop_called is True
    assert worker.wait_called_with == _WORKER_SHUTDOWN_WAIT_MS  # bounded
    assert ev.accepted is True


def test_close_event_no_process_attribute_access():
    # Worker ohne _process darf NICHT zum AttributeError führen und
    # request_stop muss trotzdem laufen.
    worker = _FakeWorker(running=False)
    ev = types.SimpleNamespace(accept=lambda: None)
    with patch("gui.main_window.stop_playback"):
        MainWindow.closeEvent(_fake_self(worker), ev)
    assert worker.stop_called is True
    assert not hasattr(worker, "_process")


def test_close_event_also_stops_transcript_worker():
    # Roadmap #3: der entkoppelte TranscriptWorker (langer Job) muss
    # beim Schliessen ebenfalls sauber abgebrochen werden (HC-2-Stil:
    # request_stop + bounded wait), nie hängen/abreissen.
    worker = _FakeWorker(running=False)
    tw = _FakeWorker(running=True)
    ev = types.SimpleNamespace(accepted=False,
                               accept=lambda: setattr(ev, "accepted", True))
    fs = _fake_self(worker)
    fs._transcript_worker = tw
    with patch("gui.main_window.stop_playback"):
        MainWindow.closeEvent(fs, ev)
    assert tw.stop_called is True
    assert tw.wait_called_with == _WORKER_SHUTDOWN_WAIT_MS  # bounded
    assert ev.accepted is True
