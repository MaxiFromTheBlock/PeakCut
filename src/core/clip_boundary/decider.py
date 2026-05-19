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

    def __init__(self, *, call_model=None, model=None, client=None,
                 credential_provider=None, client_factory=None):
        self._call_model = call_model
        self._model = model
        self._client = client
        # Carl-Gegenreview [P2]: Provider IMMER setzen — die alte
        # Back-compat (anthropic.Anthropic() ohne unsere Validierung)
        # war umgehbar. Default ist der Keychain-BYOK-Provider; der
        # Constructor löst keine Systemaufrufe aus, der erste
        # tatsächliche Aufruf passiert erst beim Bauen des Clients
        # (Tests mit call_model/client/Modell-None erreichen das nie).
        if credential_provider is None:
            from core.credentials import default_credential_provider
            credential_provider = default_credential_provider()
        self._credential_provider = credential_provider
        self._client_factory = client_factory

    def _build_client(self):
        # #3-Rev Task 3: Key kommt über den Credential-Provider
        # (Keychain primär, Env nur Dev) — nie aus config.json/Log.
        # Kein Back-compat-Pfad mehr — Provider ist garantiert gesetzt.
        key = self._credential_provider.get_api_key()
        if not key:
            raise BoundaryError(
                "Kein gültiger Claude-Key hinterlegt "
                "(Schlüsselbund/ANTHROPIC_API_KEY)")
        if self._client_factory is not None:
            return self._client_factory(api_key=key)
        import anthropic  # lazy: nie in pytest
        return anthropic.Anthropic(api_key=key)

    def _call(self, prompt):
        if self._call_model is not None:
            return self._call_model(prompt)
        # P2 (Carl): kein verstecktes Default-Modell — der Realpfad
        # MUSS ein explizites Modell bekommen (aus
        # config['smart_boundary_claude_model']), sonst lauter Fehler
        # statt stiller Falschannahme.
        if not self._model:
            raise BoundaryError(
                "Kein Claude-Modell konfiguriert "
                "(smart_boundary_claude_model)")
        client = self._client
        if client is None:
            client = self._build_client()
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


def _snap_decision(d, sc, config):
    """P1 (Carl): Decider-Output deterministisch auf Snap-Kanten
    normalisieren BEVOR die Bremse läuft (Spec: Start/Ende auf
    gelieferte natürliche Kanten gesnappt). Start = nächster Snap
    <= peak nahe start; Ende = nächster Snap > peak nahe end. Kein
    Snap innerhalb Toleranz -> None (Rückfall)."""
    tol = _cfg(config, "smart_boundary_snap_tolerance_ms", 1500)
    snaps = [c.time_ms for c in sc.snap_candidates]
    s = _nearest_snap(snaps, d.start_ms, sc.window_start_ms, sc.peak_ms)
    e = _nearest_snap(snaps, d.end_ms, sc.peak_ms + 1, sc.window_end_ms)
    if s is None or e is None:
        return None
    if abs(s - d.start_ms) > tol or abs(e - d.end_ms) > tol:
        return None
    try:
        return BoundaryDecision(start_ms=s, end_ms=e, reason=d.reason,
                                confidence=d.confidence)
    except ValueError:
        return None


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
    if d is None or not isinstance(d, BoundaryDecision):
        return _fallback(scaffold, config)
    # P1: erst auf Snap-Kanten normalisieren, dann Bremse auf der
    # gesnappten Decision (Spec: Start/Ende auf natürliche Kanten).
    snapped = _snap_decision(d, scaffold, config)
    if snapped is None or not _brake_ok(snapped, scaffold, config):
        return _fallback(scaffold, config)
    return snapped
