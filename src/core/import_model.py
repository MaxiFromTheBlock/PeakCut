"""Contract-Slice (Carl): capability-driven Import — die Daten-Modelle.

Leitsatz: der DATEINAME ist nur noch *Evidence*, nie Wahrheit. Wahrheit sind die vom
Nutzer BESTAETIGTEN Rollen (ConfirmedImportSlots) in der Akte. Der Scanner (eigener Slice)
fuellt ImportCandidate/ImportEvidence (Dauer-Cluster + duenne Inhalts-Signale + Namens-
Hinweis) als VORSCHLAG; der Confirm-Schritt macht daraus ConfirmedImportSlots.

Reine Daten, keine UI, kein Export, keine Schreibzugriffe. Rollen-Namen aus
import_classifier (eine Wahrheit fuer die Rollen-Begriffe).
"""
from dataclasses import dataclass, field

from core.import_classifier import (  # Rollen-Begriffe = eine Wahrheit
    ROLE_MARKER,
    ROLE_MIC,
    ROLE_MIX,
    ROLE_TRANSCRIPT,
    ROLE_CAMERA,
    ROLE_IGNORE,
)

KIND_AUDIO = "audio"
KIND_VIDEO = "video"


@dataclass(frozen=True)
class ImportEvidence:
    """Signale FUER einen Kandidaten — vom Scanner gefuellt, NIE als Wahrheit gesetzt.
    Alles optional: fehlt ein Signal, bleibt es None/False (duenne Auto-Detection)."""
    duration_ms: int | None = None
    episode_length: bool = False        # im Dauer-Cluster (Aufnahme), nicht Bibliothek/SFX
    is_video: bool = False
    impulse_density: float | None = None  # Marker-Signal: viel Stille + harte Impulse
    speech_likeness: float | None = None  # Speech-Signal: kontinuierliches Sprachmuster
    mix_density: float | None = None      # Mix-Signal: summierter, durchgehender Vollpegel
    name_hint: str | None = None          # Namens-Token-Hinweis (ROLE_*), NUR Zusatzsignal


@dataclass(frozen=True)
class ImportCandidate:
    """Eine entdeckte Mediendatei + ihre Evidence + ein (unverbindlicher) Rollen-Vorschlag."""
    path: str
    kind: str                              # KIND_AUDIO | KIND_VIDEO
    evidence: ImportEvidence = field(default_factory=ImportEvidence)
    suggested_role: str | None = None      # Vorschlag (ROLE_*), nie Wahrheit


@dataclass(frozen=True)
class ConfirmedImportSlots:
    """Die WAHRHEIT: vom Nutzer bestaetigte Rollen-Zuordnung. Einzige Quelle fuer
    Analyse, Capabilities und Export. Mix/Marker/Transkript optional (-> None)."""
    marker: str | None = None
    mix: str | None = None
    mics: tuple[str, ...] = ()
    videos: tuple[str, ...] = ()
    transcript: str | None = None

    def has_speech(self) -> bool:
        """Es gibt eine Sprach-Tonquelle (Mix bevorzugt, sonst echte Mics)."""
        return self.mix is not None or len(self.mics) > 0


__all__ = [
    "ImportEvidence", "ImportCandidate", "ConfirmedImportSlots",
    "KIND_AUDIO", "KIND_VIDEO",
    "ROLE_MARKER", "ROLE_MIC", "ROLE_MIX", "ROLE_TRANSCRIPT", "ROLE_CAMERA", "ROLE_IGNORE",
]
