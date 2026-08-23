"""Die EINE Stelle, die Kandidaten ueber peak_id joint (Carl-Gate A 2026-08-19).

Vorher taten das fuenf Stellen blind — XML-Export, Smart-Playback, Ignorieren,
Grenzen-Pipeline und der Web-Serialisierer. Ein Kandidat aus einer anderen
Quelle mit kollidierender Legacy-peak_id konnte dort den Marker-Kandidaten
verdraengen; im Web-Serialisierer sogar still ueberschreiben.

Qt-frei: wird auch aus PeakCut-web importiert.
"""
from .clip_candidates import ClipCandidateError, ORIGIN_MARKER


def marker_candidates_by_peak_id(session) -> dict:
    """peak_id -> Marker-Kandidat. Schlaegt bei Doppelzuordnung FEHL statt
    stillschweigend einen Treffer zu waehlen."""
    out = {}
    for c in (getattr(session, "clip_candidates", None) or []):
        if c.origin != ORIGIN_MARKER or c.peak_id is None:
            continue
        if c.peak_id in out:
            raise ClipCandidateError(
                f"Zwei Marker-Kandidaten fuer Peak {c.peak_id}: "
                f"{out[c.peak_id].candidate_id!r} und {c.candidate_id!r}")
        out[c.peak_id] = c
    return out


def marker_candidate_for_peak(session, peak_id: int):
    """Marker-Kandidat zu einem Peak, oder None."""
    return marker_candidates_by_peak_id(session).get(peak_id)


__all__ = ["marker_candidates_by_peak_id", "marker_candidate_for_peak"]
