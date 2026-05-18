"""Roadmap #3 Task 4 — Deterministischer Vorbau (Scaffold).

Spannt das Suchfenster um den Drücker, sammelt natürliche
Schnittkanten und baut einen lesbaren Text-Ausschnitt mit
Drücker-Markierung. Voll deterministisch (ohne Modell testbar).
KEINE neue Pause-Erkennung — `build_pause_ranges` aus Stufe 2 wird
wiederverwendet.
"""

from .models import BoundarySnapCandidate, BoundaryScaffold
from ..folgenschnitt_loosening import build_pause_ranges


def _cfg(config, key, default):
    getter = getattr(config, "get", None)
    if getter is None:
        return default
    val = getter(key, default)
    return default if val is None else val


def _mmss(ms):
    s = max(0, ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


def _excerpt(transcript, window_start, window_end, peak_ms):
    lines = []
    inserted = False
    for seg in transcript.segments:
        if seg.end_ms < window_start or seg.start_ms > window_end:
            continue
        if not inserted and seg.start_ms >= peak_ms:
            lines.append(f"[PEAK @ {_mmss(peak_ms)}]")
            inserted = True
        lines.append(f"[{_mmss(seg.start_ms)}] {seg.text}")
    if not inserted:
        lines.append(f"[PEAK @ {_mmss(peak_ms)}]")
    return "\n".join(lines)


def build_scaffold(*, peak_id, peak_ms, transcript, activity_frames,
                   config, total_duration_ms):
    """peak_ms/total_duration_ms in ms. Gibt einen BoundaryScaffold
    (frozen, Gate-A-Vertrag) zurück."""
    before = _cfg(config, "smart_boundary_search_before_ms", 180000)
    after = _cfg(config, "smart_boundary_search_after_ms", 60000)
    gap = _cfg(config, "smart_boundary_sentence_gap_ms", 900)

    window_start = max(0, peak_ms - before)
    window_end = min(total_duration_ms, peak_ms + after)
    if window_end <= window_start:
        window_end = min(total_duration_ms, window_start + 1)

    # Reihenfolge = Dedupe-Priorität: Fensterkanten zuerst (gewinnen bei
    # ms-Kollision -> Decider hat IMMER Rückfall-Kanten).
    raw = [(window_start, "window_edge"), (window_end, "window_edge")]

    for seg in transcript.segments:
        raw.append((seg.end_ms, "sentence_end"))
        words = list(seg.words)
        for prev, nxt in zip(words, words[1:]):
            if nxt.start_ms - prev.end_ms >= gap:
                raw.append((prev.end_ms, "word_gap"))

    for pr in build_pause_ranges(activity_frames):
        raw.append(((pr.start_ms + pr.end_ms) // 2, "pause"))

    seen = set()
    snaps = []
    for t, kind in raw:
        if t < window_start or t > window_end or t in seen:
            continue
        seen.add(t)
        snaps.append(BoundarySnapCandidate(time_ms=t, kind=kind))
    snaps.sort(key=lambda c: c.time_ms)

    return BoundaryScaffold(
        peak_id=peak_id, peak_ms=peak_ms,
        window_start_ms=window_start, window_end_ms=window_end,
        transcript_excerpt=_excerpt(transcript, window_start, window_end,
                                    peak_ms),
        snap_candidates=tuple(snaps))
