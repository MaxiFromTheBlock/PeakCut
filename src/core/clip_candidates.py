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


# Reservierter Namensraum: NUR markergebundene Kandidaten duerfen so heissen
# (Gate B / A3). Sonst kann eine Fremdquelle die Identitaet eines Markers
# annehmen, ohne dass es beim Bauen auffaellt.
MARKER_ID_PREFIX = "marker:"


def marker_candidate_id(peak_id: int) -> str:
    """Identitaet eines markergebundenen Kandidaten.

    ACHTUNG (Carl): ueber Analyselaeufe hinweg NICHT stabil, sobald Marker
    eingefuegt/entfernt werden. Echte Reanalyse mit veraendertem Marker-Satz
    braucht zeitliches Event-Matching -> eigener spaeterer Slice.
    """
    return f"{MARKER_ID_PREFIX}{peak_id}"


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
        """Gate B / A3 (Carl-Entscheidung 2026-08-21): die Kollisionsklasse
        wird an der WURZEL geschlossen statt an fuenf Verbraucher-Stellen
        bewacht. Ein Kandidat, dessen Herkunft und dessen peak_id/Identitaet
        nicht zusammenpassen, laesst sich gar nicht erst bauen.

        Die zentrale Marker-Sicht (core/candidate_view.py) bleibt trotzdem
        als zweite Verteidigungslinie bestehen — sie schuetzt gegen Daten,
        die nie durch diesen Konstruktor gelaufen sind.
        """
        if self.status not in _ALL_STATUS:
            raise ClipCandidateError(f"Unbekannter Status: {self.status!r}")
        if self.origin not in ALL_ORIGINS:
            raise ClipCandidateError(f"Unbekannte Herkunft: {self.origin!r}")
        if not self.candidate_id:
            raise ClipCandidateError("candidate_id darf nicht leer sein")
        if self.origin == ORIGIN_MARKER:
            if self.peak_id is None:
                raise ClipCandidateError("Marker-Kandidat ohne peak_id")
            erwartet = marker_candidate_id(self.peak_id)
            if self.candidate_id != erwartet:
                raise ClipCandidateError(
                    f"Marker-Kandidat {self.candidate_id!r} passt nicht zu "
                    f"peak_id={self.peak_id} — erwartet {erwartet!r}")
        else:
            if self.peak_id is not None:
                # peak_id darf NICHT doppeldeutig werden: sie bedeutet
                # ausschliesslich "dieser Kandidat IST der Marker <peak_id>".
                # Eine spaetere Naehe-/Herkunftsbeziehung bekommt ein eigenes
                # Feld (related_candidate_id) — hier bewusst nicht gebaut.
                raise ClipCandidateError(
                    f"Kandidat {self.candidate_id!r} mit origin={self.origin!r} "
                    f"darf kein peak_id tragen (peak_id={self.peak_id}); "
                    f"peak_id ist allein die Marker-Rueckreferenz")
            if self.candidate_id.startswith(MARKER_ID_PREFIX):
                raise ClipCandidateError(
                    f"Reservierter Namensraum {MARKER_ID_PREFIX!r}: "
                    f"{self.candidate_id!r} mit origin={self.origin!r} "
                    f"ist nicht erlaubt")

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
        # Gate B Restpunkt P1: dieselbe Identitaets-Pruefung wie bei
        # ClipCandidate (siehe dort) -- eine leere candidate_id wurde dort
        # schon abgelehnt, hier fehlte die Entsprechung. Ohne Kennung ist
        # eine Decision in einem identitaetszentrierten Vertrag keine
        # gueltige Decision.
        if not self.candidate_id:
            raise ClipCandidateError("candidate_id darf nicht leer sein")

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "from_status": self.from_status,
                "to_status": self.to_status, "decided_at": self.decided_at,
                "source": self.source}

    @classmethod
    def from_dict(cls, d: dict[str, Any], *,
                  require_candidate_id: bool = False) -> "CandidateDecision":
        """Nimmt v6 (candidate_id) UND v1-v5 (peak_id) entgegen. Anders als beim
        Kandidaten ist das hier eine reine String-Abbildung — kein Peak noetig.

        Gate B / A1: `require_candidate_id=True` schaltet die v6-Strenge ein.
        Der Aufrufer entscheidet das an der SCHEMA-VERSION der Akte, nicht an
        der Anwesenheit eines Feldes — sonst tarnt sich eine beschaedigte
        v6-Decision (candidate_id fehlt, altes peak_id noch da) als Legacy und
        rutscht still als `marker:<peak_id>` durch.
        """
        cid = d.get("candidate_id")
        if cid is None:
            if require_candidate_id:
                raise ClipCandidateError(
                    "v6-Decision ohne candidate_id — ein altes peak_id wird "
                    "in einer Schema-6-Akte NICHT mehr als Ersatz akzeptiert")
            if "peak_id" not in d:
                raise ClipCandidateError("Decision ohne candidate_id/peak_id")
            cid = marker_candidate_id(int(d["peak_id"]))
        return cls(candidate_id=str(cid), from_status=str(d["from_status"]),
                   to_status=str(d["to_status"]), decided_at=str(d["decided_at"]),
                   source=str(d.get("source", "manual")))


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
