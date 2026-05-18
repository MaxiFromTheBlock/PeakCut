"""Roadmap #3 Task 4 — Deterministischer Vorbau (Scaffold), Carl-Plan.

Voll deterministisch, ohne Modell testbar. Wiederverwendung von
build_pause_ranges aus Stufe 2 (KEINE neue Pause-Erkennung). Gate C.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.clip_boundary.scaffold import build_scaffold  # noqa: E402
from core.clip_boundary.models import BoundaryScaffold  # noqa: E402
from core.transcription import (  # noqa: E402
    Transcript, TranscriptSegment, TranscriptWord)

_CFG = {
    "smart_boundary_search_before_ms": 180000,
    "smart_boundary_search_after_ms": 60000,
    "smart_boundary_sentence_gap_ms": 900,
}


class _Frame:
    def __init__(self, start_ms, end_ms, smoothed_speaker):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.smoothed_speaker = smoothed_speaker


def _t(segments):
    return Transcript(segments=tuple(segments))


def test_window_clamped_at_episode_start():
    sc = build_scaffold(peak_id=0, peak_ms=30000, transcript=_t([]),
                        activity_frames=[], config=_CFG,
                        total_duration_ms=600000)
    assert isinstance(sc, BoundaryScaffold)
    assert sc.window_start_ms == 0          # 30s - 180s -> geklemmt auf 0
    assert sc.window_end_ms == 90000        # 30s + 60s
    assert sc.window_start_ms <= sc.peak_ms <= sc.window_end_ms


def test_window_clamped_at_episode_end():
    sc = build_scaffold(peak_id=1, peak_ms=595000, transcript=_t([]),
                        activity_frames=[], config=_CFG,
                        total_duration_ms=600000)
    assert sc.window_end_ms == 600000       # 595s + 60s -> geklemmt
    assert sc.window_start_ms == 415000     # 595s - 180s


def test_empty_inputs_still_valid_minimal_candidate_set():
    sc = build_scaffold(peak_id=2, peak_ms=120000, transcript=_t([]),
                        activity_frames=[], config=_CFG,
                        total_duration_ms=600000)
    times = {c.time_ms for c in sc.snap_candidates}
    # Mindestens die Fensterkanten — Decider hat immer Rückfall-Kanten
    assert sc.window_start_ms in times
    assert sc.window_end_ms in times
    assert len(sc.snap_candidates) >= 2


def test_segment_end_and_word_gap_become_snap_candidates():
    seg = TranscriptSegment(
        100000, 104000, "Frage Antwort",
        words=(TranscriptWord(100000, 100500, "Frage"),
               TranscriptWord(102000, 104000, "Antwort")))  # 1500ms Lücke
    sc = build_scaffold(peak_id=3, peak_ms=103000, transcript=_t([seg]),
                        activity_frames=[], config=_CFG,
                        total_duration_ms=600000)
    kinds_at = {(c.time_ms, c.kind) for c in sc.snap_candidates}
    assert (104000, "sentence_end") in kinds_at        # Segmentende
    assert (100500, "word_gap") in kinds_at            # Lücke >= 900ms
    # Peak-Markierung im lesbaren Auszug
    assert "PEAK" in sc.transcript_excerpt


def test_pause_ranges_are_reused_not_reinvented():
    # Pause = zusammenhängende Frames mit smoothed_speaker None
    frames = [
        _Frame(100000, 101000, "A"),
        _Frame(101000, 103000, None),     # Pause 101000..103000
        _Frame(103000, 104000, "B"),
    ]
    sc = build_scaffold(peak_id=4, peak_ms=102000, transcript=_t([]),
                        activity_frames=frames, config=_CFG,
                        total_duration_ms=600000)
    pauses = [c for c in sc.snap_candidates if c.kind == "pause"]
    assert pauses, "Pausen-Mittelpunkt muss als Snap-Kante erscheinen"
    assert any(c.time_ms == 102000 for c in pauses)   # Mittelpunkt


def test_snap_candidates_deduped_and_in_window_sorted():
    seg = TranscriptSegment(0, 90000, "lang",
                            words=(TranscriptWord(0, 500, "a"),))
    frames = [_Frame(89000, 90000, None)]   # Pause-Mitte 89500 in Fenster
    sc = build_scaffold(peak_id=5, peak_ms=60000, transcript=_t([seg]),
                        activity_frames=frames, config=_CFG,
                        total_duration_ms=600000)
    times = [c.time_ms for c in sc.snap_candidates]
    assert times == sorted(times)                      # sortiert
    assert len(times) == len(set(times))               # dedupliziert
    for c in sc.snap_candidates:
        assert sc.window_start_ms <= c.time_ms <= sc.window_end_ms
