"""Roadmap #3 Gate A — Clip-Boundary-Verträge (Carl-Finalplan).

Reine Datenmodelle + Decider-Protocol. KEIN Scaffold-/Decider-Logik,
keine Plausibilitätsbremse, keine Pipeline (= spätere Tasks/Gates).
Gate A STOPP: nach Freigabe nicht mehr an diesen Contracts drehen.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class BoundaryError(Exception):
    """Kontrollierter Fehler in der Clip-Boundary-Schicht."""


@dataclass(frozen=True)
class BoundarySnapCandidate:
    """Eine natürliche Schnittkante im Suchfenster (Satzende,
    Sprechpause, Sprecherwechsel)."""
    time_ms: int
    kind: str
    label: str = ""

    def __post_init__(self):
        if self.time_ms < 0:
            raise ValueError(f"time_ms muss >= 0 sein: {self.time_ms}")
        if not self.kind:
            raise ValueError("kind darf nicht leer sein")

    def to_dict(self) -> dict[str, Any]:
        return {"time_ms": self.time_ms, "kind": self.kind,
                "label": self.label}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BoundarySnapCandidate":
        return cls(time_ms=int(d["time_ms"]), kind=str(d["kind"]),
                   label=str(d.get("label", "")))


@dataclass(frozen=True)
class BoundaryScaffold:
    """Deterministischer Vorbau pro Drücker: Suchfenster, markierter
    Drücker, Snap-Kanten, Text-Ausschnitt. Eingabe für den Decider."""
    peak_id: int
    peak_ms: int
    window_start_ms: int
    window_end_ms: int
    transcript_excerpt: str = ""
    snap_candidates: tuple[BoundarySnapCandidate, ...] = ()

    def __post_init__(self):
        if self.window_start_ms < 0:
            raise ValueError(
                f"window_start_ms muss >= 0 sein: {self.window_start_ms}")
        if self.window_end_ms <= self.window_start_ms:
            raise ValueError(
                f"window_end_ms muss > window_start_ms sein: "
                f"{self.window_start_ms} >= {self.window_end_ms}")
        if not (self.window_start_ms <= self.peak_ms <= self.window_end_ms):
            raise ValueError(
                f"Drücker {self.peak_ms} liegt ausserhalb des Fensters "
                f"[{self.window_start_ms}, {self.window_end_ms}]")
        if not isinstance(self.snap_candidates, tuple):
            object.__setattr__(self, "snap_candidates",
                               tuple(self.snap_candidates))

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_id": self.peak_id,
            "peak_ms": self.peak_ms,
            "window_start_ms": self.window_start_ms,
            "window_end_ms": self.window_end_ms,
            "transcript_excerpt": self.transcript_excerpt,
            "snap_candidates": [c.to_dict() for c in self.snap_candidates],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BoundaryScaffold":
        return cls(
            peak_id=int(d["peak_id"]),
            peak_ms=int(d["peak_ms"]),
            window_start_ms=int(d["window_start_ms"]),
            window_end_ms=int(d["window_end_ms"]),
            transcript_excerpt=str(d.get("transcript_excerpt", "")),
            snap_candidates=tuple(
                BoundarySnapCandidate.from_dict(c)
                for c in d.get("snap_candidates", [])))


@dataclass(frozen=True)
class BoundaryDecision:
    """Ergebnis des Deciders (gesnappt) bzw. des Bremsen-Rückfalls."""
    start_ms: int
    end_ms: int
    reason: str
    confidence: float

    def __post_init__(self):
        if self.start_ms < 0:
            raise ValueError(f"start_ms muss >= 0 sein: {self.start_ms}")
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms muss > start_ms sein: {self.start_ms} >= {self.end_ms}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence muss in [0,1] liegen: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms,
                "reason": self.reason, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BoundaryDecision":
        return cls(start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]),
                   reason=str(d["reason"]), confidence=float(d["confidence"]))


@runtime_checkable
class BoundaryDecider(Protocol):
    """Austauschbarer semantischer Entscheider (Claude in v1; Tests
    injizieren einen deterministischen Stub — kein echter API-Call)."""

    def decide(self, scaffold: BoundaryScaffold) -> BoundaryDecision:
        ...
