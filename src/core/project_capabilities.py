"""Contract-Slice (Carl): capability-driven Modell — welche Outputs sind moeglich?

PeakCut ist nicht EINE Pipeline mit EINER Pflicht, sondern mehrere Faehigkeiten, jede mit
eigenem Minimum. NICHTS ist global Pflicht — der Marker schaltet NUR die Markerstellen
frei; ohne ihn gibt es trotzdem Folgenschnitt + Screenshots. Der Mix ist OPTIONAL (sonst
echte-Mics-Fallback). Diese Logik lebt zentral hier (nicht verstreut), UI + Engine lesen
denselben Vertrag: enabled / missing / warnings / evidence.

Reine Funktion der bestaetigten Rollen (ConfirmedImportSlots). Kein Export, keine UI.
"""
from dataclasses import dataclass, field

from core.import_model import ConfirmedImportSlots

CAP_SCREENSHOTS = "screenshots"
CAP_KEYBOARDSTELLEN = "keyboardstellen"
CAP_FOLGENSCHNITT = "folgenschnitt"
CAP_SINNABSCHNITTE = "sinnabschnitte"

ALL_CAPABILITIES = (CAP_SCREENSHOTS, CAP_KEYBOARDSTELLEN, CAP_FOLGENSCHNITT, CAP_SINNABSCHNITTE)


@dataclass(frozen=True)
class Capability:
    name: str
    enabled: bool
    missing: tuple[str, ...] = ()   # was fehlt, um es zu aktivieren (ehrlich anzeigen)
    warnings: tuple[str, ...] = ()  # aktiv, aber mit Einschraenkung
    evidence: tuple[str, ...] = ()  # warum (Begruendung, fuer die UI)

    def as_dict(self) -> dict:
        return {"enabled": self.enabled, "missing": list(self.missing),
                "warnings": list(self.warnings), "evidence": list(self.evidence)}


@dataclass(frozen=True)
class ProjectCapabilities:
    capabilities: dict = field(default_factory=dict)  # name -> Capability

    def get(self, name: str) -> Capability:
        return self.capabilities[name]

    def enabled(self, name: str) -> bool:
        return self.capabilities[name].enabled

    def as_dict(self) -> dict:
        """Pfadfreier Vertrag fuer die Bruecke (UI liest dasselbe wie die Engine)."""
        return {name: cap.as_dict() for name, cap in self.capabilities.items()}


def compute_capabilities(slots: ConfirmedImportSlots) -> ProjectCapabilities:
    has_video = len(slots.videos) > 0
    has_speech = slots.has_speech()
    has_mix = slots.mix is not None
    has_transcript = slots.transcript is not None

    caps: dict = {}

    # Screenshots: nur ein Video noetig.
    caps[CAP_SCREENSHOTS] = Capability(
        CAP_SCREENSHOTS, enabled=has_video,
        missing=() if has_video else ("Video",),
        evidence=(f"{len(slots.videos)} Video(s)",) if has_video else (),
    )

    # Markerstellen: braucht den Marker (das einzig PeakCut-spezifisch Essenzielle).
    has_marker = slots.marker is not None
    caps[CAP_KEYBOARDSTELLEN] = Capability(
        CAP_KEYBOARDSTELLEN, enabled=has_marker,
        missing=() if has_marker else ("Marker",),
        evidence=("Marker-Spur bestaetigt",) if has_marker else (),
    )

    # Folgenschnitt (Multicam-Rohschnitt): braucht das UMSCHALTEN zwischen Winkeln -> >=2
    # Kameras (Max-Entscheid 25.06.) + eine Sprach-Tonquelle. Kein Mix -> Mics-Fallback.
    has_multicam = len(slots.videos) >= 2
    fs_missing = []
    if not has_multicam:
        fs_missing.append("2 Kameras" if len(slots.videos) == 0 else "weitere Kamera")
    if not has_speech:
        fs_missing.append("Sprecher-Mics oder Mix")
    fs_warnings = []
    if has_multicam and has_speech and not has_mix:
        fs_warnings.append("kein Mix — Ton/Sync ueber echte Mics")
    caps[CAP_FOLGENSCHNITT] = Capability(
        CAP_FOLGENSCHNITT, enabled=(has_multicam and has_speech),
        missing=tuple(fs_missing), warnings=tuple(fs_warnings),
        evidence=(f"{len(slots.videos)} Kameras + Sprach-Ton",) if (has_multicam and has_speech) else (),
    )

    # Sinnabschnitte: Sprach-Ton (Mix oder Mics); Transkript fehlt -> wird erzeugt (kein Blocker).
    sa_warnings = []
    if has_speech and not has_transcript:
        sa_warnings.append("Transkript fehlt — wird beim Lauf erzeugt")
    caps[CAP_SINNABSCHNITTE] = Capability(
        CAP_SINNABSCHNITTE, enabled=has_speech,
        missing=() if has_speech else ("Sprach-Ton",),
        warnings=tuple(sa_warnings),
        evidence=("Mix" if has_mix else "echte Mics",) if has_speech else (),
    )

    return ProjectCapabilities(capabilities=caps)


__all__ = [
    "Capability", "ProjectCapabilities", "compute_capabilities",
    "CAP_SCREENSHOTS", "CAP_KEYBOARDSTELLEN", "CAP_FOLGENSCHNITT", "CAP_SINNABSCHNITTE",
    "ALL_CAPABILITIES",
]
