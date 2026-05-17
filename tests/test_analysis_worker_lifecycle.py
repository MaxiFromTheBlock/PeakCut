"""HC-2 Task 0 — rote Lifecycle-Tests für AnalysisWorker (Carl-Plan).

Gegen die ZIEL-API (injizierbare Fakes, request_stop, reparierter
Timeout). Auf aktuellem Stand MÜSSEN diese rot sein: __init__ kennt die
Factory-/Clock-Kwargs noch nicht und request_stop() existiert nicht.
Deterministisch — kein echter Prozess, kein sleep, kein .start().
"""

import os
import queue
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.workers import AnalysisWorker  # noqa: E402


class _FakeQueue:
    def __init__(self, items=None):
        self._items = list(items or [])

    def get(self, timeout=None):
        if self._items:
            return self._items.pop(0)
        raise queue.Empty

    def get_nowait(self):
        if self._items:
            return self._items.pop(0)
        raise queue.Empty

    def empty(self):
        return not self._items


class _FakeMpProc:
    """multiprocessing.Process-artig."""
    def __init__(self, alive_seq, exitcode=0):
        self._alive_seq = list(alive_seq)
        self.exitcode = exitcode
        self.started = self.terminated = self.killed = False
        self.joined_with = None

    def start(self):
        self.started = True

    def is_alive(self):
        return self._alive_seq.pop(0) if self._alive_seq else False

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def join(self, timeout=None):
        self.joined_with = timeout


class _FakeSubProc:
    """subprocess.Popen-artig."""
    def __init__(self, alive=True):
        self._alive = alive
        self.terminated = self.killed = False
        self.returncode = 0

    def poll(self):
        return None if self._alive else self.returncode

    def terminate(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self._alive = False


def _clock(values):
    it = iter(values)
    return lambda: next(it)


def _worker(**kw):
    s = type("S", (), {})()
    return AnalysisWorker(s, **kw)


def _sink(worker):
    rec = {"error": [], "progress": [], "finished": []}
    worker.error.connect(rec["error"].append)
    worker.progress.connect(rec["progress"].append)
    worker.finished.connect(rec["finished"].append)
    return rec


def test_multiprocess_timeout_fires_and_terminates():
    proc = _FakeMpProc(alive_seq=[True] * 50)
    w = _worker(
        process_factory=lambda **k: proc,
        queue_factory=lambda: _FakeQueue(),
        monotonic=_clock([0.0] + [10.0] * 50),
        analysis_timeout_s=1,
        progress_poll_s=0.0,
    )
    rec = _sink(w)
    w._run_multiprocess({})
    assert any("Timeout" in m for m in rec["error"]), rec
    assert proc.terminated or proc.killed


def test_multiprocess_exitcode_none_is_controlled():
    proc = _FakeMpProc(alive_seq=[True, False], exitcode=None)
    w = _worker(
        process_factory=lambda **k: proc,
        queue_factory=lambda: _FakeQueue(),
        monotonic=_clock([0.0] * 20),
        analysis_timeout_s=600,
        progress_poll_s=0.0,
    )
    rec = _sink(w)
    w._run_multiprocess({})
    assert any("unbekannt" in m.lower() or "Prozessstatus" in m
               for m in rec["error"]), rec
    assert not any(m == "Analyse fehlgeschlagen" for m in rec["error"])


def test_request_stop_terminates_subprocess_like_handle():
    w = _worker()
    proc = _FakeSubProc(alive=True)
    w._set_process(proc)
    w.request_stop()
    assert w._stop_requested is True
    assert proc.terminated or proc.killed


def test_request_stop_terminates_multiprocess_like_handle():
    w = _worker()
    proc = _FakeMpProc(alive_seq=[True, True, False])
    w._set_process(proc)
    w.request_stop()
    assert w._stop_requested is True
    assert proc.terminated or proc.killed
