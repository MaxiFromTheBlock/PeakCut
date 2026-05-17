"""HC-2 Task 5 — ScreenshotWorker-Cleanup darf den GUI-Thread nicht
mehr blockieren (kein wait(3000)); cleanup() muss laufende Worker
cancel-en (request_stop). Unbound-method-Tests gegen Fake-self."""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.video_preview_peak import PeakVideoPreview, ScreenshotWorker  # noqa: E402


class _FakeSignal:
    def __init__(self):
        self.disconnected = False

    def disconnect(self, *a, **k):
        self.disconnected = True


class _FakeSW:
    def __init__(self, running=True):
        self._running = running
        self.stop_called = False
        self.wait_called = False
        self.deleted = False
        self.screenshot_done = _FakeSignal()
        self.finished = _FakeSignal()

    def isRunning(self):
        return self._running

    def request_stop(self):
        self.stop_called = True

    def wait(self, *a, **k):
        self.wait_called = True

    def deleteLater(self):
        self.deleted = True


def _fake_self(workers):
    ns = types.SimpleNamespace()
    ns._screenshot_workers = list(workers)
    ns._lut_worker = types.SimpleNamespace(_stopped=False)
    ns._lut_worker.stop = lambda: setattr(ns._lut_worker, "_stopped", True)
    return ns


def test_cleanup_worker_does_not_block_gui_thread():
    w = _FakeSW(running=True)
    fs = _fake_self([w])
    PeakVideoPreview._cleanup_screenshot_worker(fs, w)
    assert w not in fs._screenshot_workers
    assert w.deleted is True
    assert w.wait_called is False  # kein wait(3000) auf dem GUI-Thread


def test_cleanup_cancels_running_workers_without_blocking():
    w = _FakeSW(running=True)
    fs = _fake_self([w])
    PeakVideoPreview.cleanup(fs)
    assert fs._lut_worker._stopped is True
    assert w.stop_called is True          # request_stop()
    assert w.wait_called is False         # nicht 3s pro Worker blockieren
    assert fs._screenshot_workers == []


def test_screenshot_worker_has_request_stop():
    assert hasattr(ScreenshotWorker, "request_stop")


class _FakeProc:
    """Zeichnet Aufrufe auf (statt zu werfen — sonst schlucken die
    breiten except in request_stop die Assertion)."""
    def __init__(self):
        self.terminated = self.waited = self.killed = False

    def poll(self):
        return None  # läuft noch

    def terminate(self):
        self.terminated = True

    def wait(self, *a, **k):
        self.waited = True

    def kill(self):
        self.killed = True


def test_request_stop_is_non_blocking():
    w = ScreenshotWorker("v.mp4", 0.0, "", "/luts", "Cam", "/out", 1, 25)
    fp = _FakeProc()
    with w._proc_lock:
        w._proc = fp
    w.request_stop()
    assert w._stopped is True
    assert fp.terminated is True
    assert fp.waited is False   # nicht blockieren
    assert fp.killed is False   # Reaping macht der Worker-Thread
