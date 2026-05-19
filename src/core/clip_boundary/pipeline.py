"""Roadmap #3 Task 5/6 — Stufe-B-Pipeline.

#3-Revision Task 5 + Spec §11 R4: prepare_smart_boundaries gibt jetzt
ein SmartBoundaryRunResult zurück (Pin 3: einzige semantische
Vertragsänderung). Nutzt im Smart-Pfad NUR decide_with_brake_result —
der alte decide_with_brake-Wrapper bleibt für Legacy-Aufrufer, ist hier
aber ausgemustert (Carl Task-4-Caveat).

Konsumiert NUR das gespeicherte Transkript. Drei Run-Ausgänge:
- INFRA_FEHLT  -> Lauf abbrechen, KEINE Pseudo-Candidates.
- DECIDER_VERWORFEN pro Peak -> Candidate bekommt sicheren Fallback
  (score=0.0, echtes Signal); Lauf insgesamt bleibt OK.
- OK pro Peak -> Candidate mit Score; Lauf insgesamt OK.

Status der Candidates bleibt proposed; Ignorierte/DISCARDED unangetastet.
"""

from dataclasses import replace

from .scaffold import build_scaffold
from .decider import decide_with_brake_result
from .models import BoundaryOutcome, SmartBoundaryRunResult
from ..clip_candidates import ClipBoundary, DISCARDED


def _cfg(config, key, default):
    getter = getattr(config, "get", None)
    if getter is None:
        return default
    val = getter(key, default)
    return default if val is None else val


def _safe_fallback_boundary(peak_ms, total, config):
    """Carl Gate-E P1: Scaffold-/Verarbeitungs-Fehler -> NICHT stilles
    Skip, sondern ein unsicherer, deterministischer Rückfall (Peak
    garantiert drin, in [0,total])."""
    fb_b = _cfg(config, "smart_boundary_fallback_before_ms", 45000)
    fb_a = _cfg(config, "smart_boundary_fallback_after_ms", 30000)
    start = max(0, peak_ms - fb_b)
    end = min(total, peak_ms + fb_a)
    if start >= peak_ms:
        start = max(0, peak_ms - 1)
    if end <= peak_ms:
        end = peak_ms + 1
    if end <= start:
        start, end = max(0, peak_ms - 1), peak_ms + 1
    return ClipBoundary(start, end)


def _resolve_transcript(session):
    t = getattr(session, "transcript", None)
    if t is not None:
        return t
    ref = getattr(session, "transcript_ref", None)
    if not ref:
        return None
    try:
        from ..transcript_archive import read_transcript_sidecar
        from ..project_archive import material_root, _media_paths
        root = material_root(_media_paths(session.project),
                              session.project.keyboard_track)
        return read_transcript_sidecar(root, ref)
    except Exception:  # noqa: BLE001
        return None


def prepare_smart_boundaries(session, decider, *, config,
                              should_stop=None):
    """Aktualisiert session.clip_candidates IN PLACE und gibt
    SmartBoundaryRunResult zurück (Spec §11 R4)."""
    cands = session.clip_candidates
    transcript = _resolve_transcript(session)
    peaks = list(getattr(session, "peaks", []) or [])

    if transcript is None:
        return SmartBoundaryRunResult(
            tuple(cands), BoundaryOutcome.INFRA_FEHLT,
            "Sinnabschnitte nicht berechnet: Transkript fehlt.", 0, 0)

    if not peaks:
        return SmartBoundaryRunResult(tuple(cands), BoundaryOutcome.OK,
                                       "", 0, 0)

    after = _cfg(config, "smart_boundary_search_after_ms", 60000)
    total = max(p.position_ms for p in peaks) + after + 1000
    activity = getattr(session, "speaker_activity", []) or []
    by_id = {c.peak_id: i for i, c in enumerate(cands)}

    # Carl-Gegenreview [P2] (Task 5): all-or-nothing — Updates erst
    # nach erfolgreichem Lauf in session.clip_candidates spiegeln; bei
    # INFRA_FEHLT mid-run werden sie verworfen, damit Autosave keine
    # Teil-Ergebnisse heimlich persistiert.
    pending = {}
    ready = 0
    fallback = 0

    for p in peaks:
        if should_stop is not None and should_stop():
            break
        if getattr(p, "ignored", False):
            continue
        i = by_id.get(p.index)
        if i is None:
            continue
        c = cands[i]
        if c.status == DISCARDED:
            continue

        # Scaffold-Bau ist KEIN Decider-Aufruf — Fehler hier sind kein
        # Infra-Signal (Carl Gate-E P1): unsicherer Fallback, weiter.
        try:
            sc = build_scaffold(
                peak_id=p.index, peak_ms=p.position_ms,
                transcript=transcript, activity_frames=activity,
                config=config, total_duration_ms=total)
        except Exception:  # noqa: BLE001
            try:
                pending[p.index] = replace(
                    c,
                    boundary=_safe_fallback_boundary(
                        p.position_ms, total, config),
                    reason="Scaffold/Verarbeitung fehlgeschlagen — "
                           "unsicherer Rückfall.",
                    score=0.0)
                fallback += 1
            except Exception:  # noqa: BLE001 — letzte Absicherung
                pass
            continue

        # #3-Rev Task 5: Result-Variante, keine Legacy-Wrapper im
        # Smart-Pfad (Carl Task-4-Caveat).
        res = decide_with_brake_result(sc, decider, config=config)

        if res.category is BoundaryOutcome.INFRA_FEHLT:
            # All-or-Nothing: pending verwerfen, Originale unverändert,
            # keine Pseudo-Candidates (Spec §11 R4 + Carl-Gegenreview).
            return SmartBoundaryRunResult(
                tuple(cands), BoundaryOutcome.INFRA_FEHLT,
                res.message or
                "Sinnabschnitte nicht berechnet: Infrastruktur fehlt.",
                0, 0)

        # OK oder DECIDER_VERWORFEN tragen beide eine gültige Decision.
        d = res.decision
        pending[p.index] = replace(
            c, boundary=ClipBoundary(d.start_ms, d.end_ms),
            transcript_excerpt=sc.transcript_excerpt,
            reason=d.reason, score=d.confidence)
        if res.category is BoundaryOutcome.OK:
            ready += 1
        else:
            fallback += 1

    # Lauf erfolgreich (kein Infra-Abbruch) -> jetzt erst committen.
    for pid, new_c in pending.items():
        idx = by_id.get(pid)
        if idx is not None:
            cands[idx] = new_c

    return SmartBoundaryRunResult(
        tuple(cands), BoundaryOutcome.OK, "", ready, fallback)
