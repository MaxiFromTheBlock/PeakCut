"""#76 Task 2 — Playback Window Resolver (Carl-Plan 2026-06-15).

Qt-frei, deterministisch. Bestimmt pro Modus das abzuspielende Mix-Zeit-
fenster (start_ms/end_ms) ODER einen Grund, warum nicht abspielbar
(disabled_reason). Smart bleibt immer wählbar — nur das Fenster ist ggf.
disabled, wenn kein gültiger Sinnabschnitt vorliegt.
"""

from dataclasses import dataclass

from .playback_modes import (
    PLAYBACK_MODE_KEY, PLAYBACK_MODE_SPEAK,
    normalize_playback_mode,
)
from .clip_candidates import DISCARDED

_SMART_DISABLED = "Kein Sinnabschnitt für diesen Drücker."


@dataclass(frozen=True)
class PlaybackWindow:
    mode: str
    start_ms: int
    end_ms: int | None       # None = offenes Ende (#76 A: Free-Play bis Medienende)
    disabled_reason: str = ""

    @property
    def disabled(self):
        return bool(self.disabled_reason)


def _resolve_peak(session, peak_index):
    peaks = list(getattr(session, "peaks", []) or [])
    if not peaks:
        return None
    idx = session.current_peak if peak_index is None else peak_index
    if not isinstance(idx, int) or not (0 <= idx < len(peaks)):
        return None
    return peaks[idx]


def build_playback_window(session, mode, peak_index=None):
    mode = normalize_playback_mode(mode)
    peak = _resolve_peak(session, peak_index)
    if peak is None:
        return PlaybackWindow(mode, 0, 0, "Kein Drücker ausgewählt.")

    if mode == PLAYBACK_MODE_KEY:
        start = peak.position_ms
        preview = session.config.get("preview_duration_ms", 1000)
        return PlaybackWindow(mode, start, start + preview)

    if mode == PLAYBACK_MODE_SPEAK:
        start, end = peak.in_point_ms, peak.out_point_ms
        if end <= start:
            return PlaybackWindow(mode, start, start, "Kein gültiges Sprecher-Fenster.")
        return PlaybackWindow(mode, start, end)

    # PLAYBACK_MODE_SMART
    if getattr(peak, "ignored", False):
        return PlaybackWindow(mode, 0, 0, _SMART_DISABLED)
    from .candidate_view import marker_candidate_for_peak
    cand = marker_candidate_for_peak(session, peak.index)
    if (cand is None or cand.status == DISCARDED
            or cand.score is None or cand.score <= 0.0
            or cand.boundary.end_ms <= cand.boundary.start_ms):
        return PlaybackWindow(mode, 0, 0, _SMART_DISABLED)
    return PlaybackWindow(mode, cand.boundary.start_ms, cand.boundary.end_ms)
