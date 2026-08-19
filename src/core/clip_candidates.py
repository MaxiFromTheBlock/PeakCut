"""Roadmap #2/#3 — ClipCandidate + Rückweg-Modell (Core-Contracts).

Reines Datenmodell + Statusmaschine. KEIN UI, kein Hub, kein smarter
Clip, keine Persistenz (= spätere Tasks).

Task 1 (Kandidaten quellenunabhängig, Carl-Gate A 2026-08-19): der
Vertrag ist quellenunabhängig geworden — ein Kandidat trägt eine
stabile Identität (candidate_id), seine Herkunft (origin) und einen
expliziten Anker (anchor_ms, der Sprungpunkt für die Review-
Navigation). peak_id ist nur noch eine optionale Rückreferenz für
markergebundene Kandidaten, keine Identität mehr.
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

# Herkunfts-Konstanten (Task 1: Kandidaten quellenunabhängig)
ORIGIN_MARKER = "marker"          # Fusspedal/Kickdrum — Datenbegriff, NICHT "pedal"
ORIGIN_TRANSCRIPT = "transcript"  # transkriptweiter Finder (eigener spaeterer Slice)
ORIGIN_AUTO = "auto"              # automatische Clip-Findung
ORIGIN_MANUAL = "manual"          # von Hand im Review gesetzt

ALL_ORIGINS = (ORIGIN_MARKER, ORIGIN_TRANSCRIPT, ORIGIN_AUTO, ORIGIN_MANUAL)


def marker_candidate_id(peak_id: int) -> str:
    """Identitaet eines markergebundenen Kandidaten.

    ACHTUNG (Carl): ueber Analyselaeufe hinweg NICHT stabil, sobald Marker
    eingefuegt/entfernt werden. Echte Reanalyse mit veraendertem Marker-Satz
    braucht zeitliches Event-Matching -> eigener spaeterer Slice.
    """
    return f"marker:{peak_id}"


class ClipCandidateError(Exception):
    """Unbekannter Status, unbekannte Herkunft oder illegaler Übergang."""


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
    candidate_id: str
    origin: str
    anchor_ms: int          # Sprungpunkt. NIEMALS aus boundary.start_ms ableiten.
    peak_id: int | None     # nur Rueckreferenz fuer origin == marker
    boundary: ClipBoundary
    status: str = PROPOSED
    transcript_excerpt: str = ""
    reason: str = ""
    score: float | None = None

    def __post_init__(self):
        if self.status not in _ALL_STATUS:
            raise ClipCandidateError(f"Unbekannter Status: {self.status!r}")
        if self.origin not in ALL_ORIGINS:
            raise ClipCandidateError(f"Unbekannte Herkunft: {self.origin!r}")
        if not self.candidate_id:
            raise ClipCandidateError("candidate_id darf nicht leer sein")
        if self.origin == ORIGIN_MARKER and self.peak_id is None:
            raise ClipCandidateError("Marker-Kandidat ohne peak_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "origin": self.origin,
            "anchor_ms": self.anchor_ms,
            "peak_id": self.peak_id,
            "boundary": self.boundary.to_dict(),
            "status": self.status,
            "transcript_excerpt": self.transcript_excerpt,
            "reason": self.reason,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ClipCandidate":
        """STRIKT: v6-Pflichtfelder muessen da sein. v1-v5 werden NICHT hier
        migriert — das passiert beim Hydrieren, wo session.peaks vorliegt
        (anchor_ms == peak.position_ms ist hier nicht ableitbar)."""
        missing = [k for k in ("candidate_id", "origin", "anchor_ms") if k not in d]
        if missing:
            raise ClipCandidateError(
                f"v6-Kandidat unvollstaendig, fehlt: {', '.join(missing)}")
        peak_id = d.get("peak_id")
        return cls(
            candidate_id=str(d["candidate_id"]),
            origin=str(d["origin"]),
            anchor_ms=int(d["anchor_ms"]),
            peak_id=None if peak_id is None else int(peak_id),
            boundary=ClipBoundary.from_dict(d["boundary"]),
            status=str(d.get("status", PROPOSED)),
            transcript_excerpt=str(d.get("transcript_excerpt", "")),
            reason=str(d.get("reason", "")),
            score=d.get("score"),
        )


@dataclass(frozen=True)
class CandidateDecision:
    candidate_id: str
    from_status: str
    to_status: str
    decided_at: str
    source: str = "manual"   # WER hat entschieden (nicht: woher kam die Stelle)

    def __post_init__(self):
        # Log-Contract selbst-konsistent: eine geladene Decision muss legal sein.
        for s in (self.from_status, self.to_status):
            if s not in _ALL_STATUS:
                raise ClipCandidateError(f"Unbekannter Status: {s!r}")
        if self.to_status not in _ALLOWED.get(self.from_status, set()):
            raise ClipCandidateError(
                f"Illegaler Uebergang im Log: "
                f"{self.from_status} -> {self.to_status}")

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "from_status": self.from_status,
                "to_status": self.to_status, "decided_at": self.decided_at,
                "source": self.source}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandidateDecision":
        """Nimmt v6 (candidate_id) UND v1-v5 (peak_id) entgegen. Anders als beim
        Kandidaten ist das hier eine reine String-Abbildung — kein Peak noetig."""
        cid = d.get("candidate_id")
        if cid is None:
            if "peak_id" not in d:
                raise ClipCandidateError("Decision ohne candidate_id/peak_id")
            cid = marker_candidate_id(int(d["peak_id"]))
        return cls(candidate_id=str(cid), from_status=str(d["from_status"]),
                   to_status=str(d["to_status"]), decided_at=str(d["decided_at"]),
                   source=str(d.get("source", "manual")))


PeakDecision = CandidateDecision   # Alias: bestehende Importe im Repo bleiben heil


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
    decision = CandidateDecision(
        candidate_id=candidate.candidate_id, from_status=candidate.status,
        to_status=to_status, decided_at=now, source=source)
    return new, decision
