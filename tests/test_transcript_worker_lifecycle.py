"""Roadmap #3 Task 2 — TranscriptWorker Lifecycle + Verhalten (Carl).

Gegen die ZIEL-API: injizierbare Fakes (HC-2-Stil), request_stop()
ohne blindes wait(), kein Mix -> kontrollierter Skip, Erfolg ->
Sidecar via transcript_archive (NICHT save_project_archive) +
session.transcript*. Deterministisch — kein echter Prozess, kein
echtes Whisper, kein .start(), kein sleep.
"""

import os
import queue
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.workers import TranscriptWorker  # noqa: E402
from core.transcription import Transcript, TranscriptSegment  # noqa: E402
from core.transcript_archive import transcript_sidecar_path  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000,
        "smart_boundary_whisper_engine": "mlx-whisper",
        "smart_boundary_whisper_model": "large-v3-turbo",
        "smart_boundary_language": "de"}


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


def _media(tmp_path):
    d = tmp_path / "material"
    d.mkdir()
    kb = d / "KB.wav"
    mix = d / "MIC1 mix.wav"
    cam = d / "CAM_A.mp4"
    for f in (kb, mix, cam):
        f.write_bytes(b"\x00")
    return str(kb), [str(mix)], [str(cam)]


def _session(tmp_path, with_mix=True):
    kb, mics, vids = _media(tmp_path)
    if not with_mix:
        mics = [m.replace("MIC1 mix.wav", "MIC1.wav") for m in mics]
        os.rename(os.path.join(os.path.dirname(kb), "MIC1 mix.wav"),
                  os.path.join(os.path.dirname(kb), "MIC1.wav"))
    p = PeakCutProject()
    p.set_files(kb, mics, vids)
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results({"peaks": [], "video_offsets": []})
    return s


def _transcript_dict():
    return Transcript(segments=(
        TranscriptSegment(0, 1200, "Das System"),)).to_dict()


# --- Lifecycle (HC-2-Stil) ----------------------------------------------

def test_accepts_injectable_factories_and_request_stop_terminates(tmp_path):
    s = _session(tmp_path)
    proc = _FakeMpProc(alive_seq=[True, True])
    w = TranscriptWorker(
        s, process_factory=lambda **kw: proc,
        queue_factory=lambda: _FakeQueue(), monotonic=lambda: 0.0)
    w._set_process(proc)
    w.request_stop()
    assert proc.terminated is True          # kein blindes wait()
    assert w._stop_requested is True


def test_no_mix_is_controlled_skip_no_child(tmp_path):
    s = _session(tmp_path, with_mix=False)
    spawned = []
    emitted = {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: spawned.append(1),
        queue_factory=lambda: _FakeQueue())
    w.finished.connect(lambda ref: emitted.setdefault("fin", ref))
    w.error.connect(lambda m: emitted.setdefault("err", m))
    w.run()
    assert spawned == []                    # kein Kind gestartet
    assert "err" not in emitted             # kein Fehler
    assert emitted.get("fin") == {}         # kontrollierter Skip


def test_success_writes_sidecar_via_archive_not_save(tmp_path):
    s = _session(tmp_path)
    result_q = _FakeQueue([{"transcript": _transcript_dict()}])
    qs = [result_q, _FakeQueue()]           # 1. result, 2. progress
    proc = _FakeMpProc(alive_seq=[False])   # sofort fertig
    refs = {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: proc,
        queue_factory=lambda: qs.pop(0), monotonic=lambda: 0.0)
    w.finished.connect(lambda ref: refs.setdefault("ref", ref))
    w.run()

    sidecar = transcript_sidecar_path(s.project)
    assert os.path.isfile(sidecar), "transcript.json muss geschrieben sein"
    # Besitz-Trennung: KEIN project.json (das schreibt erst späteres Autosave)
    assert not os.path.isfile(
        os.path.join(os.path.dirname(sidecar), "project.json"))
    assert refs["ref"]["path"].endswith("transcript.json")
    assert s.transcript is not None
    assert s.transcript_ref == refs["ref"]
    assert s.transcript_error is None
