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
