"""#3-Revision Task 2 (Teil A, Claude) — Cache + Ausricht-Schutz.

Reine Helfer + TranscriptWorker-Verhalten. Deterministisch: kein echtes
Whisper, kein echtes ffprobe, kein .start(), kein sleep. Naht zu Carls
Teil ist nur der eingefrorene Vertrag (Transcript / transcript_ref).
"""

import os
import queue
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.transcription import (  # noqa: E402
    Transcript, TranscriptSegment, TranscriptWord)
from core.transcript_archive import (  # noqa: E402
    transcript_span_ms, alignment_drift, cache_reusable_ref,
    transcript_root, write_transcript_sidecar)
from core.media_probe import run_ffprobe, probe_duration_ms  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402
from gui.workers import TranscriptWorker  # noqa: E402
import config as appcfg  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000,
        "smart_boundary_whisper_engine": "mlx-whisper",
        "smart_boundary_whisper_model": "m",
        "smart_boundary_language": "de"}


# --- reine Helfer --------------------------------------------------------

def _t(*spans):
    return Transcript(segments=tuple(
        TranscriptSegment(a, b, "x") for a, b in spans))


def test_transcript_span_ms():
    assert transcript_span_ms(_t((0, 1500), (1500, 4200))) == 4200
    assert transcript_span_ms(Transcript()) == 0


def test_alignment_drift_symmetric_with_tolerance():
    assert alignment_drift(4_200_000, 4_260_000, 120_000) is False  # 60s ok
    assert alignment_drift(4_200_000, 4_400_000, 120_000) is True   # 200s
    assert alignment_drift(4_400_000, 4_200_000, 120_000) is True   # auch kürzer
    # Audiodauer unbekannt -> kein Fehlalarm (eigener Status im Worker)
    assert alignment_drift(4_200_000, None, 120_000) is False


def test_config_has_alignment_tolerance_default():
    assert appcfg.DEFAULTS["smart_boundary_alignment_tolerance_ms"] == 120_000


# --- Cache-Entscheidung (pur) -------------------------------------------

def _media(tmp_path):
    d = tmp_path / "material"
    d.mkdir()
    kb, mix, cam = d / "KB.wav", d / "MIC1 mix.wav", d / "CAM.mp4"
    for f in (kb, mix, cam):
        f.write_bytes(b"\x00")
    return str(kb), [str(mix)], [str(cam)]


def _session(tmp_path):
    kb, mics, vids = _media(tmp_path)
    p = PeakCutProject()
    p.set_files(kb, mics, vids)
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results({"peaks": [], "video_offsets": []})
    return s


def _persist_prev(tmp_path):
    """Schreibt ein Sidecar + gibt (session, prev_ref, root) zurück."""
    s = _session(tmp_path)
    ref = write_transcript_sidecar(
        s.project, _t((0, 900)), engine="mlx-whisper", model="m",
        language="de", audio_path=s.project.get_reference_track())
    return s, ref, transcript_root(s.project)


def test_cache_hit_when_fingerprint_engine_match_and_sidecar_readable(tmp_path):
    s, prev, root = _persist_prev(tmp_path)
    got = cache_reusable_ref(
        prev, current_fingerprint=prev["audio_fingerprint"],
        engine="mlx-whisper", model="m", language="de", root=root)
    assert got == prev


def test_cache_miss_on_fingerprint_change(tmp_path):
    s, prev, root = _persist_prev(tmp_path)
    other = {"size": 999, "mtime_ns": 1}
    assert cache_reusable_ref(prev, current_fingerprint=other,
                              engine="mlx-whisper", model="m",
                              language="de", root=root) is None


def test_cache_miss_on_engine_or_model_or_language_change(tmp_path):
    s, prev, root = _persist_prev(tmp_path)
    fp = prev["audio_fingerprint"]
    for kw in ({"engine": "other"}, {"model": "x"}, {"language": "en"}):
        base = dict(engine="mlx-whisper", model="m", language="de")
        base.update(kw)
        assert cache_reusable_ref(prev, current_fingerprint=fp,
                                  root=root, **base) is None


def test_cache_miss_when_sidecar_unreadable(tmp_path):
    s, prev, root = _persist_prev(tmp_path)
    with open(os.path.join(root, ".peakcut", "transcript.json"), "w") as f:
        f.write("{ kaputt")
    assert cache_reusable_ref(prev, current_fingerprint=prev["audio_fingerprint"],
                              engine="mlx-whisper", model="m",
                              language="de", root=root) is None


def test_cache_miss_when_no_or_bad_prev_ref(tmp_path):
    _, _, root = _persist_prev(tmp_path)
    for bad in (None, "nope", {}, {"path": "x"}):
        assert cache_reusable_ref(bad, current_fingerprint={"size": 1},
                                  engine="e", model="m", language="de",
                                  root=root) is None


# --- ffprobe-Helfer tolerant --------------------------------------------

def test_probe_duration_ms_tolerant_on_missing_file(tmp_path):
    assert probe_duration_ms(str(tmp_path / "weg.wav")) is None
    assert run_ffprobe(["-show_entries", "format=duration",
                        str(tmp_path / "weg.wav")]) is None


# --- Worker: Cache überspringt den Child ganz ---------------------------

class _FakeQueue:
    def __init__(self, items=None):
        self._items = list(items or [])

    def get(self, timeout=None):
        if self._items:
            return self._items.pop(0)
        raise queue.Empty

    def get_nowait(self):
        return self.get()

    def empty(self):
        return not self._items


class _FakeProc:
    def __init__(self):
        self.started = False

    def start(self):
        self.started = True

    def is_alive(self):
        return False


def test_worker_cache_hit_skips_child_completely(tmp_path):
    s, prev, _ = _persist_prev(tmp_path)
    s.transcript_ref = prev                       # persistierter Vorlauf
    spawned, msgs, fin = [], [], {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: spawned.append(1) or _FakeProc(),
        queue_factory=lambda: _FakeQueue(), monotonic=lambda: 0.0)
    w.progress.connect(lambda m: msgs.append(m))
    w.finished.connect(lambda r: fin.setdefault("ref", r))
    w.run()
    assert spawned == []                          # KEIN Whisper-Child
    assert fin["ref"] == prev
    assert s.transcript_ref == prev and s.transcript is None
    assert any("Cache" in m for m in msgs)


def test_worker_alignment_drift_emits_loud_status_and_fields(tmp_path):
    s = _session(tmp_path)                         # kein prev -> Cache-Miss
    ref_from_child = {"path": ".peakcut/transcript.json",
                      "engine": "mlx-whisper", "model": "m",
                      "language": "de", "audio_path": "material/MIC1 mix.wav",
                      "source": "whisper", "audio_fingerprint": {"size": 1},
                      "transcript_span_ms": 600_000}     # Text 10 min
    qs = [_FakeQueue([{"ref": ref_from_child}]), _FakeQueue()]
    msgs, fin = [], {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: _FakeProc(),
        queue_factory=lambda: qs.pop(0), monotonic=lambda: 0.0)
    w.progress.connect(lambda m: msgs.append(m))
    w.finished.connect(lambda r: fin.setdefault("ref", r))
    with patch("gui.workers.probe_duration_ms", return_value=4_200_000):
        w.run()                                    # Audio 70 min -> Drift
    assert any("passt nicht zur Audiodauer" in m for m in msgs)
    assert fin["ref"]["audio_duration_ms"] == 4_200_000
    assert fin["ref"]["transcript_span_ms"] == 600_000


def test_worker_no_drift_finishes_clean(tmp_path):
    s = _session(tmp_path)
    ref_from_child = {"path": ".peakcut/transcript.json",
                      "engine": "mlx-whisper", "model": "m",
                      "language": "de", "audio_path": "material/MIC1 mix.wav",
                      "source": "whisper", "audio_fingerprint": {"size": 1},
                      "transcript_span_ms": 4_200_000}
    qs = [_FakeQueue([{"ref": ref_from_child}]), _FakeQueue()]
    msgs, fin = [], {}
    w = TranscriptWorker(
        s, process_factory=lambda **kw: _FakeProc(),
        queue_factory=lambda: qs.pop(0), monotonic=lambda: 0.0)
    w.progress.connect(lambda m: msgs.append(m))
    w.finished.connect(lambda r: fin.setdefault("ref", r))
    with patch("gui.workers.probe_duration_ms", return_value=4_230_000):
        w.run()                                    # 30s Diff -> ok
    assert not any("passt nicht" in m for m in msgs)
    assert fin["ref"]["audio_duration_ms"] == 4_230_000
    assert s.transcript_ref == fin["ref"]
