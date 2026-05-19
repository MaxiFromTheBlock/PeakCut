"""Roadmap #3 Task 6 — Stufe-B-Pipeline (nach dem Export-Handoff).

Konsumiert NUR das gespeicherte Transkript (Spec-Rework: kein
transcriber-Param — bewusste Abweichung von Carls Ur-Signatur).
Pro nicht-ignoriertem Peak: Scaffold -> Decider -> Bremse -> vorhandene
ClipCandidate aktualisieren (Status bleibt proposed). Fehler pro Peak
isoliert; kein Transkript / Totalfehler -> Skip (Bootstrap bleibt).
"""

from dataclasses import replace

from .scaffold import build_scaffold
from .decider import decide_with_brake
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
    except Exception:
        return None


def prepare_smart_boundaries(session, decider, *, config,
                             should_stop=None):
    """Gibt IMMER session.clip_candidates zurück (in-place
    aktualisiert). Kein Transkript -> unverändert (Bootstrap)."""
    cands = session.clip_candidates
    transcript = _resolve_transcript(session)
    peaks = list(getattr(session, "peaks", []) or [])
    if transcript is None or not peaks:
        return cands

    after = _cfg(config, "smart_boundary_search_after_ms", 60000)
    total = max(p.position_ms for p in peaks) + after + 1000
    activity = getattr(session, "speaker_activity", []) or []
    by_id = {c.peak_id: i for i, c in enumerate(cands)}

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
        try:
            sc = build_scaffold(
                peak_id=p.index, peak_ms=p.position_ms,
                transcript=transcript, activity_frames=activity,
                config=config, total_duration_ms=total)
            d = decide_with_brake(sc, decider, config=config)
            cands[i] = replace(
                c, boundary=ClipBoundary(d.start_ms, d.end_ms),
                transcript_excerpt=sc.transcript_excerpt,
                reason=d.reason, score=d.confidence)
        except Exception:  # noqa: BLE001 — Fehler pro Peak isoliert
            # P1: NICHT stumm überspringen — unsicheren Fallback
            # markieren, andere Peaks laufen weiter.
            try:
                cands[i] = replace(
                    c,
                    boundary=_safe_fallback_boundary(
                        p.position_ms, total, config),
                    reason="Scaffold/Verarbeitung fehlgeschlagen — "
                           "unsicherer Rückfall.",
                    score=0.0)
            except Exception:  # noqa: BLE001 — letzte Absicherung
                continue
    return cands
