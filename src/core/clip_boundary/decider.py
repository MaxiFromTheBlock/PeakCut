"""Roadmap #3 Task 5 — Semantischer Entscheider (Claude) + Bremse.

Claude darf kreativ entscheiden, aber die deterministische
Plausibilitätsbremse fängt jeden strukturellen Defekt ab und fällt
kontrolliert auf ein sicheres Fenster zurück (nie schlechter als
heute). Kein echter API-Call in pytest — call_model ist injizierbar.
"""

import json

from .models import BoundaryDecision, BoundaryError


def _cfg(config, key, default):
    getter = getattr(config, "get", None)
    if getter is None:
        return default
    val = getter(key, default)
    return default if val is None else val


def build_decider_prompt(scaffold):
    """Pure. Rahmt window_edge ausdrücklich als Fallback-Kanten
    (Carl Gate-C: sonst nimmt Claude bequem die Fensterdecke)."""
    snaps = "\n".join(
        f"- {c.time_ms} ms [{c.kind}]"
        + (f" {c.label}" if c.label else "")
        for c in scaffold.snap_candidates)
    return (
        "Du findest den kleinsten zusammenhängenden Sinnabschnitt um "
        "einen markierten Moment ([PEAK]) in einem Podcast-Transkript.\n"
        "Regeln:\n"
        "- Start dort, wo der Gedanke/Anlauf beginnt; Ende dort, wo er "
        "landet (eine Pointe NACH dem [PEAK] gehört dazu).\n"
        "- Schneide NIE hart am [PEAK] ab.\n"
        "- Der [PEAK] muss im Abschnitt liegen.\n"
        "- Start/Ende auf eine der gelieferten Snap-Kanten legen oder "
        "plausibel nah daran.\n"
        "- 'window_edge'-Kanten sind NUR Notfall-/Fallback-Kanten, "
        "NICHT die bevorzugte kreative Wahl.\n"
        "- Keine Fakten erfinden.\n\n"
        f"Transkript-Ausschnitt:\n{scaffold.transcript_excerpt}\n\n"
        f"Snap-Kanten:\n{snaps}\n\n"
        "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:\n"
        '{"start_ms": <int>, "end_ms": <int>, "reason": "<kurz>", '
        '"confidence": <0..1>}'
    )


def _extract_json(raw):
    s = raw.find("{")
    e = raw.rfind("}")
    if s == -1 or e == -1 or e < s:
        raise BoundaryError("Keine JSON-Struktur in der Decider-Antwort")
    return json.loads(raw[s:e + 1])


class ClaudeBoundaryDecider:
    """Implementiert BoundaryDecider (Gate-A-Protocol). call_model:
    str(prompt) -> str(roh). In Tests injiziert; produktiv lazy
    Anthropic-Client (niedrige Temperatur, strukturiertes JSON)."""

    def __init__(self, *, call_model=None, model="claude-opus-4-7",
                 client=None):
        self._call_model = call_model
        self._model = model
        self._client = client

    def _call(self, prompt):
        if self._call_model is not None:
            return self._call_model(prompt)
        client = self._client
        if client is None:
            import anthropic  # lazy: nie in pytest
            client = anthropic.Anthropic()
        msg = client.messages.create(
            model=self._model, max_tokens=300, temperature=0.0,
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text

    def decide(self, scaffold):
        raw = self._call(build_decider_prompt(scaffold))
        try:
            d = _extract_json(raw)
            return BoundaryDecision(
                start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]),
                reason=str(d.get("reason", "")),
                confidence=float(d["confidence"]))
        except BoundaryError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            raise BoundaryError(f"Decider-Antwort unbrauchbar: {e}") from e


def _brake_ok(d, sc, config):
    if not (sc.window_start_ms <= d.start_ms and
            d.end_ms <= sc.window_end_ms):
        return False
    # Peak drin UND Ende strikt nach dem Drücker (kein harter Cut am
    # [PEAK], deckt zugleich 'Ende <= Peak' ab).
    if not (d.start_ms <= sc.peak_ms < d.end_ms):
        return False
    dur = d.end_ms - d.start_ms
    if dur < _cfg(config, "smart_boundary_min_duration_ms", 12000):
        return False
    if dur > _cfg(config, "smart_boundary_max_duration_ms", 180000):
        return False
    if d.confidence < _cfg(config, "smart_boundary_confidence_threshold",
                           0.5):
        return False
    return True


def _nearest_snap(targets, target_ms, lo, hi):
    cands = [t for t in targets if lo <= t <= hi]
    if not cands:
        return None
    return min(cands, key=lambda t: abs(t - target_ms))


def _fallback(sc, config):
    """Deterministisches, sicheres Rückfall-Fenster — auf Fenster und
    Snap-Kanten geklemmt, Peak garantiert drin, als unsicher markiert."""
    fb_b = _cfg(config, "smart_boundary_fallback_before_ms", 45000)
    fb_a = _cfg(config, "smart_boundary_fallback_after_ms", 30000)
    start = max(sc.window_start_ms, sc.peak_ms - fb_b)
    end = min(sc.window_end_ms, sc.peak_ms + fb_a)
    if start >= sc.peak_ms:
        start = sc.window_start_ms
    if end <= sc.peak_ms:
        end = sc.window_end_ms

    snaps = [c.time_ms for c in sc.snap_candidates]
    s_snap = _nearest_snap(snaps, start, sc.window_start_ms, sc.peak_ms)
    if s_snap is not None and s_snap <= sc.peak_ms:
        start = s_snap
    e_snap = _nearest_snap(snaps, end, sc.peak_ms + 1, sc.window_end_ms)
    if e_snap is not None and e_snap > start:
        end = e_snap

    if end <= start:                       # letzte Absicherung
        start, end = sc.window_start_ms, sc.window_end_ms
    return BoundaryDecision(
        start_ms=start, end_ms=end,
        reason="Plausibilitätsbremse: Decider-Vorschlag unbrauchbar/"
               "unsicher — konservatives Rückfall-Fenster (unsicher).",
        confidence=0.0)


def decide_with_brake(scaffold, decider, *, config):
    """Decider aufrufen, Bremse anwenden. Jeder Defekt/Exception ->
    sicherer Rückfall. Gibt IMMER eine valide BoundaryDecision."""
    try:
        d = decider.decide(scaffold)
    except Exception:  # noqa: BLE001 (inkl. BoundaryError -> Rückfall)
        d = None
    if d is None or not isinstance(d, BoundaryDecision) or \
            not _brake_ok(d, scaffold, config):
        return _fallback(scaffold, config)
    return d
