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


# ---------------------------------------------------------------------
# Track-Order: Carl-Algorithmus (Spec Design-Entscheidung 1)
# ---------------------------------------------------------------------


def build_video_track_order(camera_assignments, decisions):
    """Liefert Kameras in XML-Reihenfolge (V1 zuerst).

    Algorithmus:
    1. Aus camera_assignments Kameras filtern: shot_type != "unused".
    2. Totale-Kamera (shot_type == "totale") zuerst, wenn vorhanden.
    3. Person-Kameras in Assignment-Reihenfolge danach.
    4. Nach path deduplizieren (versehentliche Doppelzuweisung).
    5. Decision-Kameras, die nicht in den Assignments stehen, hinten
       anhaengen (Defensiv: kein aktiver Schnitt darf verloren gehen).

    Rueckgabe: Tuple von CameraAssignment-aehnlichen Objekten in
    XML-Reihenfolge. Fuer Decision-Kameras ohne Assignment wird ein
    synthetischer Eintrag mit shot_type="unused" und path-basiertem
    Fallback erzeugt.
    """
    from .folgenschnitt_models import (
        CameraAssignment,
        SHOT_TOTAL,
        SHOT_UNUSED,
    )

    # 1. unused raus
    active = [
        ca for ca in camera_assignments
        if ca.shot_type != SHOT_UNUSED
    ]

    # 2. Totale zuerst (nur erste Totale wird V1; weitere wandern in
    # die normale Reihenfolge — Edge-Case, nicht in Spec definiert)
    totale = next(
        (ca for ca in active if ca.shot_type == SHOT_TOTAL), None,
    )
    rest = [ca for ca in active if ca is not totale]

    ordered = ([totale] + rest) if totale is not None else rest

    # 3. Nach path deduplizieren (erste Zuweisung gewinnt)
    seen_paths = set()
    deduped = []
    for ca in ordered:
        if ca.path in seen_paths:
            continue
        seen_paths.add(ca.path)
        deduped.append(ca)

    # 4. Decision-Kameras anhaengen, die noch fehlen
    for d in decisions:
        if d.camera_path not in seen_paths:
            # Synthetischer Eintrag — shot_type "unused" weil unbekannt,
            # damit name-Logik auf Basename-Fallback geht.
            synth = CameraAssignment(
                path=d.camera_path,
                shot_type=SHOT_UNUSED,
                person=None,
            )
            deduped.append(synth)
            seen_paths.add(d.camera_path)

    return tuple(deduped)


# ---------------------------------------------------------------------
# Name-Konvention fuer Tracks (Carl-Hinweis 2026-06-03)
# ---------------------------------------------------------------------


def _track_name_for_camera(camera):
    """Cutter-lesbarer Name fuer eine Kamera-Spur.

    - Totale (shot_type == "totale"): "Totale".
    - Person-Kamera (person + shot_type): "{person} {shot_type}".
    - Fallback (fehlende Info, missing-decision-Synth): Basename des
      Pfads ohne fuehrenden Slash.
    """
    import os
    from .folgenschnitt_models import SHOT_TOTAL

    if camera.shot_type == SHOT_TOTAL:
        return "Totale"
    if camera.person and camera.shot_type:
        return f"{camera.person} {camera.shot_type}"
    return os.path.basename(camera.path)


# ---------------------------------------------------------------------
# Video-Layout: Remove vs. Disable (Task 2)
# ---------------------------------------------------------------------


def build_video_track_layout(camera_assignments, decisions, mode):
    """Baut die Video-Tracks fuer Multi-Track-XML.

    mode = UNUSED_CLIPS_REMOVE:
      - Totale-Track (shot_type == "totale") bekommt einen Clip pro
        Decision (durchgehende Fallback-Schicht).
      - Person-Tracks bekommen nur Clips fuer ihre aktiven Decisions.
      - Alle Clips enabled = True.

    mode = UNUSED_CLIPS_DISABLE:
      - JEDER Track bekommt einen Clip pro Decision.
      - Totale-Track: alle enabled = True.
      - Person-Tracks: nur Clip fuer aktive Decision enabled = True,
        sonst enabled = False.

    Plan-Vertrag (Spec): in_ms = start_ms, out_ms = end_ms. Die
    Offset-Logik (HM-Sync) wird im Exporter angewandt — der Plan
    bleibt FCP7-frei.
    """
    from .folgenschnitt_models import SHOT_TOTAL

    mode = normalize_unused_clips_mode(mode)
    order = build_video_track_order(camera_assignments, decisions)
    decisions_list = list(decisions)

    # Carl-P2-Fix 2026-06-03: Nur die ERSTE Totale in der Track-Order
    # ist Fallback-Schicht. Weitere Totale-Kameras (versehentliche
    # Mehrfachzuweisung) verhalten sich wie normale Person-Kameras —
    # Remove = nur aktive Clips, Disable = disabled bei nicht-aktiven.
    # Sonst koennte eine zweite Totale ueber den Person-Spuren alles
    # verdecken.
    fallback_totale_path = (
        order[0].path
        if order and order[0].shot_type == SHOT_TOTAL
        else None
    )

    tracks = []
    for camera in order:
        is_fallback_totale = camera.path == fallback_totale_path
        clips = []
        for d in decisions_list:
            active = d.camera_path == camera.path
            if mode == UNUSED_CLIPS_REMOVE:
                # Fallback-Totale durchgaengig; sonst nur aktive Clips.
                if is_fallback_totale or active:
                    clips.append(VideoClipPlan(
                        start_ms=d.start_ms,
                        end_ms=d.end_ms,
                        in_ms=d.start_ms,
                        out_ms=d.end_ms,
                        enabled=True,
                    ))
            else:  # UNUSED_CLIPS_DISABLE
                # Jeder Track bekommt jede Decision; Fallback-Totale
                # immer enabled, sonst nur bei aktiver Decision.
                clips.append(VideoClipPlan(
                    start_ms=d.start_ms,
                    end_ms=d.end_ms,
                    in_ms=d.start_ms,
                    out_ms=d.end_ms,
                    enabled=is_fallback_totale or active,
                ))
        tracks.append(VideoTrackPlan(
            file_path=camera.path,
            name=_track_name_for_camera(camera),
            clips=tuple(clips),
        ))
    return tuple(tracks)


# ---------------------------------------------------------------------
# Audio-Quellenwahl (Task 3)
# ---------------------------------------------------------------------


def build_audio_track_plan(project, sequence_duration_ms):
    """Liefert Audio-Tracks und uses_mix-Flag.

    Mix vorhanden in project.mic_tracks → genau eine Audio-Spur mit
    dem Mix als durchgehender Clip (0 bis sequence_duration_ms).
    uses_mix=True.

    Kein Mix → Fallback auf echte Mics (alle non-mix-Eintraege in
    mic_tracks), jeweils als durchgehender Clip. uses_mix=False
    → UI/Statusbar zeigt Phasing-Hinweis.

    Leere mic_tracks → ((), False), Exporter kann darauf reagieren.

    Nutzt audio_routing-Helper aus #71a (Pin-3) — keine eigene
    Mix-Heuristik.
    """
    import os
    from .audio_routing import get_mix_track, get_source_mic_tracks

    mix_path = get_mix_track(project)
    if mix_path:
        clip = AudioClipPlan(
            start_ms=0,
            end_ms=sequence_duration_ms,
            in_ms=0,
            out_ms=sequence_duration_ms,
        )
        return (
            (AudioTrackPlan(
                file_path=mix_path,
                name="Mix",
                clips=(clip,),
            ),),
            True,
        )

    mic_paths = get_source_mic_tracks(project)
    if not mic_paths:
        return ((), False)

    tracks = []
    for path in mic_paths:
        clip = AudioClipPlan(
            start_ms=0,
            end_ms=sequence_duration_ms,
            in_ms=0,
            out_ms=sequence_duration_ms,
        )
        tracks.append(AudioTrackPlan(
            file_path=path,
            name=os.path.splitext(os.path.basename(path))[0],
            clips=(clip,),
        ))
    return (tuple(tracks), False)


# ---------------------------------------------------------------------
# build_multitrack_layout — Integration (Task 2 + 3)
# ---------------------------------------------------------------------


def build_multitrack_layout(decisions, camera_assignments, project, mode):
    """Baut den vollstaendigen MultitrackLayoutPlan.

    Sequence-Dauer wird aus den Decisions abgeleitet (max end_ms).
    Bei leeren Decisions = 0, kein Audio.
    """
    mode = normalize_unused_clips_mode(mode)
    video_tracks = build_video_track_layout(
        camera_assignments, decisions, mode,
    )
    decisions_list = list(decisions)
    sequence_duration_ms = (
        max(d.end_ms for d in decisions_list) if decisions_list else 0
    )
    audio_tracks, uses_mix = build_audio_track_plan(
        project, sequence_duration_ms,
    )
    return MultitrackLayoutPlan(
        video_tracks=video_tracks,
        audio_tracks=audio_tracks,
        uses_mix=uses_mix,
        mode=mode,
    )
