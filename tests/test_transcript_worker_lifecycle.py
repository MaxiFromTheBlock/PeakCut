"""Roadmap #3 Task 2 — TranscriptWorker Lifecycle + Verhalten (Carl).

Inkl. Gate-B-Fixes: P1a (Child schreibt Sidecar selbst, nur kleiner
Ref durch die Queue), P1b (Priorität best-effort im Child), P2 (spawn-
Context-Default). Deterministisch — kein echter Prozess, kein echtes
Whisper, kein .start(), kein sleep.
"""

import os
import queue
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.workers import TranscriptWorker, _TRANSCRIPT_MP_CONTEXT  # noqa: E402
import core.transcription_process as tp  # noqa: E402
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


class _FakeEngine:
    def transcribe(self, audio_path, *, language, model):
        return Transcript(segments=(TranscriptSegment(0, 1200, "Das System"),))


def _media(tmp_path, with_mix=True):
    d = tmp_path / "material"
    d.mkdir()
    kb = d / "KB.wav"
    mix = d / ("MIC1 mix.wav" if with_mix else "MIC1.wav")
    cam = d / "CAM_A.mp4"
    for f in (kb, mix, cam):
        f.write_bytes(b"\x00")
    return str(kb), [str(mix)], [str(cam)]


def _session(tmp_path, with_mix=True):
    kb, mics, vids = _media(tmp_path, with_mix)
    p = PeakCutProject()
    p.set_files(kb, mics, vids)
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results({"peaks": [], "video_offsets": []})
    return s


# --- P2: spawn-Context-Default ------------------------------------------

def test_default_factories_use_spawn_context():
    assert _TRANSCRIPT_MP_CONTEXT.get_start_method() == "spawn"


# --- Lifecycle (HC-2-Stil) ----------------------------------------------

def test_request_stop_terminates_without_blind_wait(tmp_path):
    s = _session(tmp_path)
    proc = _FakeMpProc(alive_seq=[True, True])
    w = TranscriptWorker(
        s, process_factory=lambda **kw: proc,
        queue_factory=lambda: _FakeQueue(), monotonic=lambda: 0.0)
    w._set_process(proc)
    w.request_stop()
    assert proc.terminated is True
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
    assert spawned == []
    assert "err" not in emitted
    assert emitted.get("fin") == {}


# --- P1a: Parent setzt nur die Referenz (kein voller Payload) -----------

def test_parent_sets_ref_only_no_save_no_full_transcript(tmp_path):
    s = _session(tmp_path)
    ref = {"path": ".peakcut/transcript.json", "engine": "mlx-whisper",
           "model": "m", "language": "de", "audio_path": "material/MIC1 mix.wav"}
    result_q = _FakeQueue([{"ref": ref}])     # KEIN volles Transcript!
    qs = [result_q, _FakeQueue()]
    proc = _FakeMpProc(alive_seq=[False])
    got = {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: proc,
        queue_factory=lambda: qs.pop(0), monotonic=lambda: 0.0)
    w.finished.connect(lambda r: got.setdefault("ref", r))
    w.run()
    assert got["ref"] == ref
    assert s.transcript_ref == ref
    assert s.transcript is None               # Stufe B liest Sidecar
    assert s.transcript_error is None
    sidecar = transcript_sidecar_path(s.project)
    # Parent schreibt NICHTS (Child-Job war gefakt) — kein project.json
    assert not os.path.isfile(
        os.path.join(os.path.dirname(sidecar), "project.json"))


# --- P1a: Child schreibt Sidecar selbst, gibt nur kleinen Ref ----------

def test_child_writes_sidecar_and_returns_small_ref(tmp_path):
    sidecar = str(tmp_path / ".peakcut" / "transcript.json")
    ref = {"path": ".peakcut/transcript.json", "engine": "mlx-whisper"}
    req = {"audio_path": "x.wav", "engine": "mlx-whisper", "model": "m",
           "language": "de", "sidecar_path": sidecar, "transcript_ref": ref}
    out = tp._emit_into_sidecar(req, engine=_FakeEngine())
    assert out == {"ref": ref}                # klein, kein "transcript"
    assert "transcript" not in out
    assert os.path.isfile(sidecar)


def test_child_engine_error_returns_error_no_file(tmp_path):
    class _BoomEngine:
        def transcribe(self, audio_path, *, language, model):
            raise RuntimeError("whisper kaputt")

    sidecar = str(tmp_path / ".peakcut" / "transcript.json")
    req = {"audio_path": "x", "engine": "e", "model": "m", "language": "de",
           "sidecar_path": sidecar, "transcript_ref": {"path": "p"}}
    out = tp._emit_into_sidecar(req, engine=_BoomEngine())
    assert "error" in out and "ref" not in out
    assert not os.path.isfile(sidecar)


# --- P1b: Priorität best-effort -----------------------------------------

def test_apply_low_priority_sets_env_caps_and_attempts_nice():
    keys = ("TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS")
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        with patch("core.transcription_process.os.nice") as mock_nice:
            tp._apply_low_priority()
        assert os.environ["TOKENIZERS_PARALLELISM"] == "false"
        assert os.environ["OMP_NUM_THREADS"] == "1"
        assert os.environ["VECLIB_MAXIMUM_THREADS"] == "1"
        mock_nice.assert_called_once_with(10)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
