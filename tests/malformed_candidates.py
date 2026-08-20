"""ABSICHTLICH VERTRAGSWIDRIGE ClipCandidate-Objekte — nur fuer Tests.

Warum es das gibt (Carl-Gate B, A3): seit die Invarianten im `__post_init__`
von `ClipCandidate` sitzen (origin != marker ⇒ peak_id is None; origin ==
marker ⇒ candidate_id == marker_candidate_id(peak_id); reservierter
Namensraum "marker:" nur fuer Marker), laesst sich ein kollidierender
Kandidat nicht mehr normal bauen. Die Kollisionsklasse ist damit an der
Wurzel geschlossen.

Carl woertlich dazu: „Die zentrale Marker-Sicht bleibt trotzdem als
Defense-in-Depth bestehen. Die Kollisionspruefungen koennen mit absichtlich
malformed Testobjekten weiter beweisen, dass die Verbraucher robust bleiben."

Genau das ist der Zweck hier: die zweite Verteidigungslinie (candidate_view,
Reconciliation, Playback, Export, Ignorieren) muss auch gegen Daten robust
bleiben, die NIE durch diesen Konstruktor gelaufen sind — z.B. eine von Hand
editierte/beschaedigte .peakcut-Akte, ein aelterer Schreiber oder ein anderes
Repo (PeakCut-web).

Wie sauber ist das? `ClipCandidate` ist ein frozen dataclass; frozen heisst
"kein normales Setzen von Attributen", nicht "unveraenderlich im Speicher".
`object.__setattr__` ist der von der Standardbibliothek selbst benutzte Weg
(dataclasses.__init__ setzt frozen-Felder intern genauso). Wir bauen deshalb
ZUERST ein gueltiges Objekt — d.h. alle anderen Vertragspruefungen (Status,
Herkunft, Boundary, nicht-leere ID) laufen wirklich — und drehen erst danach
gezielt die beiden Identitaets-Felder auf den kaputten Wert. Kein Monkeypatch
am Produktivcode, keine Attrappen-Klasse, die vom echten Vertrag abdriften
kann: das Objekt ist in jeder anderen Hinsicht ein echter ClipCandidate.
"""

from core.clip_candidates import (
    ClipCandidate, ClipCandidateError, ORIGIN_MARKER, marker_candidate_id)

# Platzhalter-ID fuer das Saat-Objekt einer Nicht-Marker-Herkunft. Wird sofort
# ueberschrieben; darf den reservierten Namensraum nicht verwenden.
_SEED_ID = "seed:malformed"


def malformed_candidate(*, candidate_id, origin, anchor_ms, peak_id,
                        boundary, **kw):
    """Baut einen ClipCandidate, der die A3-Invarianten VERLETZT.

    Nur fuer Tests der zweiten Verteidigungslinie. Produktivcode darf so
    etwas nicht erzeugen koennen — genau das beweist die Selbstkontrolle
    unten: haelt das Ergebnis den Vertrag doch ein, ist der Test wertlos
    geworden und muss laut scheitern statt still gruen zu bleiben.
    """
    if origin == ORIGIN_MARKER:
        seed_peak = peak_id if peak_id is not None else 0
        seed = ClipCandidate(
            candidate_id=marker_candidate_id(seed_peak), origin=origin,
            anchor_ms=anchor_ms, peak_id=seed_peak, boundary=boundary, **kw)
    else:
        seed = ClipCandidate(
            candidate_id=_SEED_ID, origin=origin, anchor_ms=anchor_ms,
            peak_id=None, boundary=boundary, **kw)

    # Nur die Identitaets-Felder werden verbogen — Status/Herkunft/Boundary
    # sind oben regulaer geprueft worden.
    object.__setattr__(seed, "candidate_id", candidate_id)
    object.__setattr__(seed, "peak_id", peak_id)

    try:
        seed.__post_init__()
    except ClipCandidateError:
        return seed
    raise AssertionError(
        f"malformed_candidate() hat ein GUELTIGES Objekt gebaut "
        f"(candidate_id={candidate_id!r}, origin={origin!r}, "
        f"peak_id={peak_id!r}) — der Test wuerde nichts mehr beweisen. "
        f"Entweder die Invarianten sind weg oder der Testfall ist gar "
        f"keine Verletzung mehr.")


__all__ = ["malformed_candidate"]
