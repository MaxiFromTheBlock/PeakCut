"""Multi-Track-Folgenschnitt: pure Layout-Planung.

Trennt die Plan-Datenform (was kommt auf welche Spur, welcher Clip ist
enabled, welche Audio-Quelle wird genutzt) vom XML-Schreiben. Der
FolgenschnittXMLExporter konsumiert MultitrackLayoutPlan und uebersetzt
es in FCP7-XML.

Diese Datei ist absichtlich frei von FCP7-/XML-Spezifika.

Spec: docs/specs/2026-06-03-multitrack-folgenschnitt-xml-design.md
Plan: Slice B Task 1 (Carl 2026-06-03)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------
# Konstanten — single source of truth fuer Toggle-Werte.
# ---------------------------------------------------------------------

UNUSED_CLIPS_REMOVE = "remove"
UNUSED_CLIPS_DISABLE = "disable"

VALID_UNUSED_CLIPS_MODES = frozenset({
    UNUSED_CLIPS_REMOVE,
    UNUSED_CLIPS_DISABLE,
})

DEFAULT_UNUSED_CLIPS_MODE = UNUSED_CLIPS_DISABLE


def normalize_unused_clips_mode(value: Any) -> str:
    """Gibt einen gueltigen Mode zurueck.

    Gueltige Werte (exakt, case-sensitive): "disable" oder "remove".
    Alles andere → DEFAULT_UNUSED_CLIPS_MODE. Kein Crash, keine
    Exceptions — der Toggle ist UI-getrieben, ungueltige Werte
    bedeuten meist Migration-Schaden oder Tippfehler und sollen
    silent auf Default fallen.
    """
    if isinstance(value, str) and value in VALID_UNUSED_CLIPS_MODES:
        return value
    return DEFAULT_UNUSED_CLIPS_MODE


# ---------------------------------------------------------------------
# Plan-Datenform (Pure Dataclasses, frozen).
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class VideoClipPlan:
    """Ein Clip auf einer Video-Spur.

    Alle Zeitangaben in Millisekunden (Decision-Eingangsformat).
    Der Exporter rechnet ms → Frames mit der Sequence-fps um.

    - start_ms/end_ms: Position auf der Sequence-Timeline.
    - in_ms/out_ms: Quell-Position im Video-File (Source-Range).
    - enabled: False → wird im XML als <enabled>FALSE</enabled>
      ausgegeben (Disable-Modus). True → kein <enabled>-Element
      (FCP7-Default).
    """

    start_ms: int
    end_ms: int
    in_ms: int
    out_ms: int
    enabled: bool


@dataclass(frozen=True)
class VideoTrackPlan:
    """Eine Video-Spur im XML.

    file_path: Pfad zur Kamera-Datei (eine pro Spur).
    name: Anzeige-Name fuer den <name>-Tag im XML (z.B. 'Jan', 'Totale').
    clips: Tuple von VideoClipPlan in Timeline-Reihenfolge.
    """

    file_path: str
    name: str
    clips: tuple[VideoClipPlan, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AudioClipPlan:
    """Ein Audio-Clip. Keine enabled-Logik — Audio ist immer aktiv."""

    start_ms: int
    end_ms: int
    in_ms: int
    out_ms: int


@dataclass(frozen=True)
class AudioTrackPlan:
    """Eine Audio-Spur (typischerweise ein durchgehender Mix-Clip).

    file_path: Pfad zur Audio-Datei.
    name: Anzeige-Name fuer den <name>-Tag im XML.
    clips: Tuple von AudioClipPlan in Timeline-Reihenfolge.
    """

    file_path: str
    name: str
    clips: tuple[AudioClipPlan, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MultitrackLayoutPlan:
    """Gesamtergebnis der Layout-Planung.

    video_tracks: Tuple in XML-Reihenfolge (erste = V1 = unten in Premiere).
    audio_tracks: Tuple. Typischerweise eine Mix-Spur; bei Fallback auf
      echte Mics mehrere Tracks.
    uses_mix: True wenn die Audio-Tracks aus dem Mix gespeist sind.
      False bei Fallback auf echte Mics — UI/Statusbar kann dann
      Phasing-Hinweis zeigen.
    mode: UNUSED_CLIPS_REMOVE oder UNUSED_CLIPS_DISABLE (fuer
      Diagnostik/Debug, der Plan selbst sollte schon den
      passenden Clip-Set tragen).
    """

    video_tracks: tuple[VideoTrackPlan, ...]
    audio_tracks: tuple[AudioTrackPlan, ...]
    uses_mix: bool
    mode: str
