"""Roadmap #2 — ClipCandidate + Rückweg-Modell (Core-Contracts).

Reines Datenmodell + Statusmaschine. KEIN UI, kein Hub, kein smarter
Clip, keine Persistenz (= spätere Tasks). Gate A STOPP: nach
Freigabe nicht mehr an diesen Contracts drehen.
"""

from dataclasses import dataclass, replace
from typing import Any

# Status-Konstanten
PROPOSED = "proposed"
SELECTED = "selected"
PRODUCED = "produced"
PUBLISHED = "published"
DISCARDED = "discarded"

_ALL_STATUS = (PROPOSED, SELECTED, PRODUCED, PUBLISHED, DISCARDED)

# Erlaubte Übergänge (Carl-Entscheidung; published terminal in v1)
_ALLOWED = {
    PROPOSED: {SELECTED, DISCARDED},
    SELECTED: {PROPOSED, PRODUCED, DISCARDED},
    PRODUCED: {SELECTED, PUBLISHED, DISCARDED},
    DISCARDED: {PROPOSED, SELECTED},
    PUBLISHED: set(),  # terminal in v1
}


class ClipCandidateError(Exception):
    """Unbekannter Status oder illegaler Übergang."""


@dataclass(frozen=True)
class ClipBoundary:
    start_ms: int
    end_ms: int

    def __post_init__(self):
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms muss > start_ms sein: {self.start_ms} >= {self.end_ms}")

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ClipBoundary":
        return cls(start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]))


@dataclass(frozen=True)
class ClipCandidate:
    peak_id: int
    boundary: ClipBoundary
    status: str = PROPOSED
    transcript_excerpt: str = ""
    reason: str = ""
    score: float | None = None

    def __post_init__(self):
        if self.status not in _ALL_STATUS:
            raise ClipCandidateError(f"Unbekannter Status: {self.status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_id": self.peak_id,
            "boundary": self.boundary.to_dict(),
            "status": self.status,
            "transcript_excerpt": self.transcript_excerpt,
            "reason": self.reason,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ClipCandidate":
        return cls(
            peak_id=int(d["peak_id"]),
            boundary=ClipBoundary.from_dict(d["boundary"]),
            status=str(d.get("status", PROPOSED)),
            transcript_excerpt=str(d.get("transcript_excerpt", "")),
            reason=str(d.get("reason", "")),
            score=d.get("score"),
        )


@dataclass(frozen=True)
class PeakDecision:
    peak_id: int
    from_status: str
    to_status: str
    decided_at: str
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_id": self.peak_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "decided_at": self.decided_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PeakDecision":
        return cls(
            peak_id=int(d["peak_id"]),
            from_status=str(d["from_status"]),
            to_status=str(d["to_status"]),
            decided_at=str(d["decided_at"]),
            source=str(d.get("source", "manual")),
        )


def transition(candidate: ClipCandidate, to_status: str, *, now: str,
               source: str = "manual"):
    """Legalen Statuswechsel anwenden.

    Returns (new_candidate, decision). No-op bei gleichem Status ->
    (candidate, None). Unbekannter Zielstatus / illegaler Übergang ->
    ClipCandidateError. `now` wird injiziert (deterministisch testbar).
    """
    if to_status not in _ALL_STATUS:
        raise ClipCandidateError(f"Unbekannter Zielstatus: {to_status!r}")
    if to_status == candidate.status:
        return candidate, None
    if to_status not in _ALLOWED.get(candidate.status, set()):
        raise ClipCandidateError(
            f"Illegaler Übergang: {candidate.status} -> {to_status}")
    new = replace(candidate, status=to_status)
    decision = PeakDecision(
        peak_id=candidate.peak_id, from_status=candidate.status,
        to_status=to_status, decided_at=now, source=source)
    return new, decision
