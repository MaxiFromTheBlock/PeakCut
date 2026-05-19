"""#3-Revision Gate A — Credential-Zugang als Steckplatz (Spec §11 R3).

Ein einziger Claude-Zugang-Steckplatz (analog zu den Engine-Protocols).
Hier NUR die eingefrorenen Shapes: Status-Objekt + Provider-Protocol.

- v1-Implementierung = sicherer macOS-Keychain-BYOK (Task 3).
- Späterer Austausch ohne Neubau: Managed/Proxy-Modell (PeakCut-Backend
  hält den Key, Kosten im Abo) ist eine andere Implementierung
  desselben Steckplatzes — eigener Roadmap-Punkt (V4-Cloud-Tier),
  NICHT #3.

STOPP-Gate: nach Freigabe nicht mehr beiläufig an diesen Verträgen
drehen.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class CredentialStatus:
    """Anzeigbarer Zustand des Claude-Zugangs — nie der Key-Wert selbst.

    `reason` ist ein stabiler Maschinen-Code (z. B. "missing",
    "invalid", "ok"); `message` ist der menschenlesbare Hinweis fürs
    Review-UI."""
    ok: bool
    reason: str = ""
    message: str = ""


@runtime_checkable
class ClaudeCredentialProvider(Protocol):
    """Austauschbarer Zugang zum Claude-Key. v1 = macOS-Keychain-BYOK;
    Env-Var bleibt Dev-/CLI-Notnagel. Der Key wird NIE geloggt, nie in
    Repo/config.json geschrieben."""

    def get_api_key(self) -> Optional[str]:
        ...

    def status(self) -> CredentialStatus:
        ...


# ── #3-Revision Task 3 — konkrete Implementierung (Spec §11 R3) ────────
#
# Sicherheitskritisch: der Key landet NIE in Git/config.json/Log. Fehler-
# meldungen und CredentialStatus enthalten NIE den Key-Wert.

KEYCHAIN_SERVICE = "PeakCut Anthropic"
KEYCHAIN_ACCOUNT = "default"
_ENV_KEY = "ANTHROPIC_API_KEY"


class CredentialError(Exception):
    """Kontrollierter Fehler in der Credential-Schicht. Meldungen
    enthalten NIE den Key-Wert."""


def validate_api_key(raw: str) -> str:
    """Trimmt und prüft (Carl Task 3): nicht leer, druckbares ASCII,
    keine Steuerzeichen, KEIN Whitespace im Key. Gibt den bereinigten
    Key zurück oder wirft ValueError mit einer Meldung, die den
    Key-Inhalt NIE enthält."""
    if raw is None:
        raise ValueError("Kein Claude-Key angegeben")
    key = raw.strip()
    if not key:
        raise ValueError("Kein Claude-Key angegeben")
    for ch in key:
        if ch.isspace():
            raise ValueError("Claude-Key darf keinen Whitespace enthalten")
        if not (0x20 <= ord(ch) < 0x7F):
            raise ValueError(
                "Claude-Key enthält ungültige Zeichen "
                "(nur druckbares ASCII erlaubt)")
    return key


def _security_runner(args):
    """Default-Runner: ruft das macOS `security`-CLI. Gibt
    (returncode, stdout) zurück; wirft nie. Loggt NICHTS (der Key
    fließt als Argument/Ausgabe durch — nie in einen Logger)."""
    try:
        r = subprocess.run(["security", *args],
                            capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 (Binary fehlt / Timeout)
        return (1, "")
    return (r.returncode, r.stdout or "")


class KeychainCredentialProvider:
    """v1-Implementierung des eingefrorenen ClaudeCredentialProvider-
    Vertrags: macOS-Keychain primär, `ANTHROPIC_API_KEY` nur als
    Dev-/CLI-Notnagel. Kein Key in config.json, kein Logging des Keys.
    `runner`/`env` injizierbar -> Tests gehen nie an die echte Keychain.
    """

    def __init__(self, *, runner=None, env=None):
        import os
        self._runner = runner if runner is not None else _security_runner
        self._env = env if env is not None else os.environ

    def _read_keychain(self) -> Optional[str]:
        rc, out = self._runner(
            ["find-generic-password", "-s", KEYCHAIN_SERVICE,
             "-a", KEYCHAIN_ACCOUNT, "-w"])
        if rc != 0:
            return None
        out = out.strip()
        return out or None

    def get_api_key(self) -> Optional[str]:
        kc = self._read_keychain()
        if kc is not None:
            try:
                return validate_api_key(kc)
            except ValueError:
                return None            # konfiguriert aber kaputt -> nicht liefern
        env = self._env.get(_ENV_KEY)
        if env:
            try:
                return validate_api_key(env)
            except ValueError:
                return None
        return None

    def status(self) -> CredentialStatus:
        kc = self._read_keychain()
        if kc is not None:
            try:
                validate_api_key(kc)
                return CredentialStatus(
                    True, "ok", "Claude-Key aus dem Schlüsselbund ist gültig.")
            except ValueError:
                return CredentialStatus(
                    False, "invalid",
                    "Claude-Key im Schlüsselbund ist ungültig — bitte neu "
                    "hinterlegen.")
        env = self._env.get(_ENV_KEY)
        if env:
            try:
                validate_api_key(env)
                return CredentialStatus(
                    True, "env",
                    "Dev-Fallback: Key aus ANTHROPIC_API_KEY (nicht für "
                    "Produktion).")
            except ValueError:
                return CredentialStatus(
                    False, "invalid",
                    "ANTHROPIC_API_KEY ist ungültig.")
        return CredentialStatus(
            False, "missing",
            "Kein Claude-Key hinterlegt (Schlüsselbund/ANTHROPIC_API_KEY).")

    def store(self, raw: str) -> None:
        """Validiert ZUERST (ungültig -> ValueError, nichts gespeichert),
        dann in die Keychain (`-U` = vorhandenen Eintrag aktualisieren).
        Der Key geht nie nach config.json/Log. Carl-Gegenreview [P2]:
        security-Returncode prüfen — bei Fehler (gesperrt, fehlt,
        Berechtigungen) sanitizte CredentialError werfen, KEINE
        Key-/CLI-Details im Text."""
        key = validate_api_key(raw)
        rc, _ = self._runner(
            ["add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
             "-a", KEYCHAIN_ACCOUNT, "-w", key])
        if rc != 0:
            raise CredentialError(
                "Konnte Claude-Key nicht im Schlüsselbund speichern "
                "(security lieferte einen Fehlercode zurück — Schlüssel-"
                "bund gesperrt, Berechtigung fehlt oder `security` ist "
                "nicht verfügbar).")


def default_credential_provider() -> "KeychainCredentialProvider":
    """Einziger Einstieg für Produktion/UI/Decider (ein Steckplatz —
    späterer Managed/Proxy-Tausch = andere Implementierung, kein
    Neubau; eigener V4-Roadmap-Punkt, NICHT #3)."""
    return KeychainCredentialProvider()
