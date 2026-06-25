"""HC-4 — .peakcut/-Projektakte (Persistenz).

Reines Core-Fundament: ein Lauf wird gespeichert + wieder geladen statt
erneut analysiert. Andockpunkt = bestehender Vertrag
session.load_analysis_results(dict). KEIN Hub/Projektbrowser/NAS-Worker
(spätere Roadmap-Punkte #2-#6).
"""

import json
import os
import shutil

from . import atomic_io
from .folgenschnitt_multitrack_layout import (
    normalize_unused_clips_mode as _normalize_clips_mode,
)

CURRENT_SCHEMA_VERSION = 5  # v5 (additiv, Carl-Gate Import Slice 3): confirmed_import_slots + material_sources + analysis_state (pending). v4-Slots bleiben; Mix bleibt in legacy mic_tracks (Pin-1).
ARCHIVE_DIR = ".peakcut"
ARCHIVE_FILE = "project.json"
_CSV_NAME = "speaker_activity.csv"
_CSV_REF = f"{ARCHIVE_DIR}/{_CSV_NAME}"

# analysis_state: eine v5-Akte aus confirmImport ist re-entrant, aber klar noch nicht
# analysiert. Fehlt das Feld (alte/normale Akte) -> als "analyzed" behandeln.
ANALYSIS_STATE_PENDING = "pending"

# Config-Schlüssel, die die Export-Identität beeinflussen (verifiziert).
_CONFIG_SNAPSHOT_KEYS = ("fps", "context_duration_ms")
_REQUIRED_SECTIONS = ("project", "analysis_results", "assignments")


class ProjectArchiveError(Exception):
    """Kontrollierter Fehler beim Lesen/Schreiben der Projektakte."""


# --- Task 1: Materialwurzel-Strategie -------------------------------------

def _broad_dirs():
    home = os.path.expanduser("~")
    return {
        os.path.abspath(os.sep), os.path.abspath(home),
        os.path.join(home, "Desktop"), os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
    }


def material_root(media_paths, keyboard_track=None):
    paths = [os.path.abspath(p) for p in media_paths if p]
    root = None
    if paths:
        try:
            root = os.path.commonpath(paths)
        except ValueError:
            root = None
    if root and not os.path.isdir(root):
        root = os.path.dirname(root)
    if not root or root in _broad_dirs():
        anchor = keyboard_track or (paths[0] if paths else None)
        root = os.path.dirname(os.path.abspath(anchor)) if anchor else os.getcwd()
    return root


def _rel(path, root):
    if not path:
        return path
    return os.path.relpath(os.path.abspath(path), root)


def _abs(rel, root):
    return os.path.normpath(os.path.join(root, rel)) if rel else rel


def _is_external(rel):
    return isinstance(rel, str) and rel.startswith(os.pardir)


# --- Task 2: Peak-Round-Trip exakt ----------------------------------------

def peak_to_dict(peak):
    """Effektive (geclampte) Punkte serialisieren — damit der Export
    nach Reload bit-gleich bleibt (verifiziert gegen
    session.load_analysis_results: in/out_point_ms + ignored werden
    exakt rekonstruiert)."""
    return {
        "index": peak.index,
        "position_ms": peak.position_ms,
        "in_point_ms": peak.in_point_ms,
        "out_point_ms": peak.out_point_ms,
        "context_ms": max(abs(peak.in_offset_ms), abs(peak.out_offset_ms)),
        "ignored": bool(peak.ignored),
    }


def _to_dict_list(items):
    return [it.to_dict() if hasattr(it, "to_dict") else it
            for it in (items or [])]


def _map_assignment_paths(dicts, fn):
    """Pfad-Feld in Assignment-Dicts (Mic/Camera) transformieren —
    damit Assignments genauso verschiebbar sind wie Projektpfade
    (HC-4 P1: sonst zeigen sie nach Ordner-Umzug auf den alten Ort)."""
    out = []
    for d in dicts or []:
        d = dict(d)
        if d.get("path"):
            d["path"] = fn(d["path"])
        out.append(d)
    return out


def analysis_results_from_session(session, speaker_activity_csv_ref=None):
    return {
        "peaks": [peak_to_dict(p) for p in getattr(session, "peaks", []) or []],
        "video_offsets": list(getattr(session, "video_offsets", []) or []),
        "speaker_activity_csv": speaker_activity_csv_ref
        if speaker_activity_csv_ref is not None
        else getattr(session, "speaker_activity_csv", None),
        "speaker_activity_mic_assignments": _to_dict_list(
            getattr(session, "speaker_activity_mic_assignments", [])),
    }


# --- Format (Task 0) ------------------------------------------------------

def build_archive_payload(session, material_root, speaker_activity_csv_ref=None):
    project = session.project
    cfg = session.config

    def _cfg(key):
        getter = getattr(cfg, "get", None)
        return getter(key, None) if getter else None

    marker = _rel(project.marker_track, material_root)
    # v4 additiv: mic_tracks bleibt die VOLLE Liste (Mix bleibt drin). Der
    # Keyboardstellen-XML-Audioblock = mic_tracks (exporters.py) — den Mix hier
    # zu entfernen würde die Cutter-XML ändern (Pin-1!). Der Mix bekommt
    # ZUSÄTZLICH einen eigenen Slot; das echte Strippen von mic_tracks zieht
    # Task 5 (Exporter-Umhängung), nicht Task 4.
    mics = [_rel(p, material_root) for p in project.mic_tracks]
    mix = _rel(project.mix_track, material_root) if project.mix_track else None
    transcript = (_rel(project.transcript_path, material_root)
                  if project.transcript_path else None)
    vids = [_rel(p, material_root) for p in project.videos]
    external = any(_is_external(p)
                   for p in [marker, mix, transcript] + mics + vids if p)

    def _rel_p(p):
        return _rel(p, material_root)

    analysis = analysis_results_from_session(session, speaker_activity_csv_ref)
    analysis["speaker_activity_mic_assignments"] = _map_assignment_paths(
        analysis.get("speaker_activity_mic_assignments"), _rel_p)

    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "app": "PeakCut",
        "config": {k: _cfg(k) for k in _CONFIG_SNAPSHOT_KEYS
                   if _cfg(k) is not None},
        "project": {
            "marker_track": marker,
            "mic_tracks": mics,
            "mix_track": mix,
            "transcript_path": transcript,
            "videos": vids,
            "guest_name": project.guest_name,
            "path_root_strategy": "common_parent",
            "has_external_paths": external,
        },
        "analysis_results": analysis,
        "assignments": {
            "folgenschnitt_assignment_applied": bool(getattr(
                session, "folgenschnitt_assignment_applied", False)),
            "folgenschnitt_mic_assignments": _map_assignment_paths(
                _to_dict_list(getattr(
                    session, "folgenschnitt_mic_assignments", [])), _rel_p),
            "folgenschnitt_camera_assignments": _map_assignment_paths(
                _to_dict_list(getattr(
                    session, "folgenschnitt_camera_assignments", [])), _rel_p),
            # Slice B v3 (Carl-Plan 2026-06-03): Toggle "Unused Clips"
            # ueberlebt App-Neustart. normalize_unused_clips_mode beim
            # Loader filtert ungueltige Werte → Default.
            "folgenschnitt_unused_clips_mode": _normalize_clips_mode(
                getattr(session, "folgenschnitt_unused_clips_mode", None)),
        },
        # v2 additiv (Roadmap #2): keine Pfade -> keine Relativierung.
        "clip_candidates": _to_dict_list(
            getattr(session, "clip_candidates", [])),
        "peak_decisions": _to_dict_list(
            getattr(session, "peak_decisions", [])),
        # Roadmap #3 additiv: NUR Referenzblock. transcript.json gehört
        # dem TranscriptWorker (früh/eigenständig); save fasst die Datei
        # NIE an. None = kein Transkript -> alte Akten tolerant.
        "transcript": getattr(session, "transcript_ref", None),
    }


def _payload_schema_version(payload):
    """schema_version als int. Fehlt/None -> 1 (alte Akte). Ungültiger
    Wert -> kontrollierter ProjectArchiveError (kein roher ValueError)."""
    raw = payload.get("schema_version", 1)
    if raw is None:
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ProjectArchiveError(
            f"Projektakte hat ungültige schema_version: {raw!r}") from e


def _assert_schema_readable(payload):
    """DATA-2: Eine Akte aus der Zukunft NICHT laden — sonst würde ein
    älterer Client beim nächsten Autosave neuere Felder still wegschneiden."""
    v = _payload_schema_version(payload)
    if v > CURRENT_SCHEMA_VERSION:
        raise ProjectArchiveError(
            f"Projektakte ist neuer (schema_version={v}) als dieser "
            f"PeakCut-Stand (max {CURRENT_SCHEMA_VERSION}). Nicht laden, "
            f"um keine Daten zu verlieren — bitte PeakCut aktualisieren.")


def _assert_archive_write_allowed(archive_path):
    """DATA-2: Nicht über eine vorhandene Zukunfts-Akte schreiben. Sonst
    frisst der Normalflow/Autosave eine v-neuere Akte, nachdem das Laden
    sie bereits abgelehnt hat. Kaputte/unlesbare Akte -> Schreiben darf
    reparieren."""
    if not os.path.isfile(archive_path):
        return
    try:
        with open(archive_path) as f:
            existing = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    try:
        v = _payload_schema_version(existing)
    except ProjectArchiveError:
        return  # ungültige Version in alter Datei -> Schreiben repariert
    if v > CURRENT_SCHEMA_VERSION:
        raise ProjectArchiveError(
            f"Vorhandene Projektakte ist neuer (schema_version={v}) als "
            f"dieser PeakCut-Stand — nicht überschreiben.")


def parse_archive_payload(payload, fallback_config):
    if not isinstance(payload, dict):
        raise ProjectArchiveError("Projektakte ist kein gültiges Objekt")
    missing = [s for s in _REQUIRED_SECTIONS if s not in payload]
    if missing:
        raise ProjectArchiveError(
            f"Projektakte unvollständig — fehlende Sektion(en): "
            f"{', '.join(missing)}")
    _assert_schema_readable(payload)
    cfg = dict(fallback_config or {})
    cfg.update(payload.get("config", {}) or {})
    return {
        "schema_version": payload.get("schema_version"),
        "config": cfg,
        "project": dict(payload["project"]),
        "analysis_results": dict(payload["analysis_results"]),
        "assignments": dict(payload["assignments"]),
        # v2 additiv: None = Sektion fehlt (v1-Akte -> bootstrappen);
        # Liste = exakt laden (auch leere).
        "clip_candidates": payload.get("clip_candidates"),
        "peak_decisions": payload.get("peak_decisions"),
        # Roadmap #3 additiv & optional (NICHT in _REQUIRED_SECTIONS):
        # fehlt -> None -> alte Akten laden unverändert.
        "transcript": payload.get("transcript"),
        # v5 additiv & optional (Import Slice 3): fehlt -> None -> alte/normale
        # Akten unverändert. confirmed_import_slots = saubere Rollen-Wahrheit,
        # material_sources = Provenienz, analysis_state = pending|analyzed.
        "confirmed_import_slots": payload.get("confirmed_import_slots"),
        "material_sources": payload.get("material_sources"),
        "analysis_state": payload.get("analysis_state"),
    }


# --- Task 3+4: save / load / find -----------------------------------------

def _media_paths(project):
    # mic_tracks enthält den Mix noch (v4 additiv) → kein separater mix-Eintrag.
    paths = list(project.mic_tracks) + list(project.videos)
    if project.marker_track:
        paths.append(project.marker_track)
    if project.transcript_path:
        paths.append(project.transcript_path)
    return paths


def save_project_archive(session, root=None):
    project = session.project
    if root is None:
        root = material_root(_media_paths(project), project.keyboard_track)
    archive_dir = os.path.join(root, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)
    _assert_archive_write_allowed(os.path.join(archive_dir, ARCHIVE_FILE))

    csv_ref = None
    src_csv = getattr(session, "speaker_activity_csv", None)
    dst_csv = os.path.join(archive_dir, _CSV_NAME)
    if src_csv and os.path.isfile(src_csv):
        if os.path.abspath(src_csv) != os.path.abspath(dst_csv):
            shutil.copy2(src_csv, dst_csv)
        csv_ref = _CSV_REF
    elif getattr(session, "speaker_activity", None):
        from .speaker_activity import write_speaker_activity_csv
        write_speaker_activity_csv(list(session.speaker_activity), dst_csv)
        csv_ref = _CSV_REF

    # v2: sicherstellen, dass Candidates existieren (Carl: falls nicht
    # und Peaks da -> bootstrap), bevor das Payload gebaut wird.
    if (not getattr(session, "clip_candidates", None)
            and getattr(session, "peaks", None)
            and hasattr(session, "_bootstrap_clip_candidates")):
        session._bootstrap_clip_candidates()

    payload = build_archive_payload(session, root, csv_ref)
    archive_path = os.path.join(archive_dir, ARCHIVE_FILE)
    atomic_io.write_json_atomic(archive_path, payload, indent=2,
                                ensure_ascii=False)
    return archive_path


# --- Import Slice 3 / Brocken B (i): v5 PENDING-Import-Akte ----------------
# confirmImport laeuft VOR der Analyse. Die Akte traegt die saubere Rollen-Wahrheit
# (confirmed_import_slots, Mics OHNE Mix) + Provenienz (material_sources) + den Zustand
# (analysis_state="pending"). Die legacy project-Sektion bleibt v4-foermig (Mix IN
# mic_tracks) -> der bestehende Loader/Export bleibt Pin-1-sicher (Carl-Adapter Opt. 2).

def _slots_rel(slots, root):
    return {
        "marker": _rel(slots.marker, root) if slots.marker else None,
        "mix": _rel(slots.mix, root) if slots.mix else None,
        "mics": [_rel(p, root) for p in slots.mics],
        "videos": [_rel(p, root) for p in slots.videos],
        "transcript": _rel(slots.transcript, root) if slots.transcript else None,
    }


def build_pending_import_payload(root, slots, material_sources=None, *,
                                 config=None, guest_name=None):
    """Reines v5-Pending-Payload aus bestaetigten Rollen (testbar, kein IO)."""
    sources = material_sources if material_sources is not None else [root]
    # legacy project-Sektion = v4-Form: Mix steckt MIT in mic_tracks (Pin-1-sicher).
    legacy_mics = list(slots.mics) + ([slots.mix] if slots.mix else [])
    proj_marker = _rel(slots.marker, root) if slots.marker else None
    proj_mics = [_rel(p, root) for p in legacy_mics]
    proj_mix = _rel(slots.mix, root) if slots.mix else None
    proj_transcript = _rel(slots.transcript, root) if slots.transcript else None
    proj_videos = [_rel(p, root) for p in slots.videos]
    external = any(_is_external(p) for p in
                   [proj_marker, proj_mix, proj_transcript] + proj_mics + proj_videos if p)
    cfg = config or {}
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "app": "PeakCut",
        "analysis_state": ANALYSIS_STATE_PENDING,
        "config": {k: cfg.get(k) for k in _CONFIG_SNAPSHOT_KEYS if cfg.get(k) is not None},
        "material_sources": [_rel(s, root) for s in sources],
        "confirmed_import_slots": _slots_rel(slots, root),
        "project": {
            "marker_track": proj_marker,
            "mic_tracks": proj_mics,
            "mix_track": proj_mix,
            "transcript_path": proj_transcript,
            "videos": proj_videos,
            "guest_name": guest_name,
            "path_root_strategy": "common_parent",
            "has_external_paths": external,
        },
        "analysis_results": {
            "peaks": [], "video_offsets": [],
            "speaker_activity_csv": None,
            "speaker_activity_mic_assignments": [],
        },
        "assignments": {
            "folgenschnitt_assignment_applied": False,
            "folgenschnitt_mic_assignments": [],
            "folgenschnitt_camera_assignments": [],
            "folgenschnitt_unused_clips_mode": _normalize_clips_mode(None),
        },
    }


def _assert_pending_write_allowed(archive_path):
    """Carl-P1b: confirm darf nur schreiben, wenn es KEINE Akte gibt ODER bereits eine
    PENDING-Akte (zweites Confirm = Update). Eine normale/analysierte Akte NIE auf leere
    Pending-Sektionen zuruecksetzen -> ALREADY_ANALYZED."""
    if not os.path.isfile(archive_path):
        return
    try:
        with open(archive_path) as f:
            existing = json.load(f)
    except (OSError, json.JSONDecodeError):
        return  # kaputte Akte -> Schreiben darf reparieren (wie _assert_archive_write_allowed)
    if isinstance(existing, dict) and existing.get("analysis_state") == ANALYSIS_STATE_PENDING:
        return  # Pending-Update erlaubt
    raise ProjectArchiveError(
        "ALREADY_ANALYZED: vorhandene Akte ist bereits analysiert/normal — Confirm wuerde "
        "sie auf leere Pending-Sektionen zuruecksetzen")


def save_pending_import_archive(root, slots, material_sources=None, *,
                                config=None, guest_name=None):
    """Schreibt die v5-Pending-Akte atomar nach root/.peakcut/project.json. Schreibt NIE
    ueber eine Zukunfts-Akte (DATA-2) und NIE ueber eine analysierte Akte (Carl-P1b);
    eine vorhandene Pending-Akte darf aktualisiert werden. Carl-P2: root realpath-
    normalisiert, bevor _rel()/archive_dir gerechnet werden."""
    root = os.path.realpath(root)
    archive_dir = os.path.join(root, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, ARCHIVE_FILE)
    _assert_archive_write_allowed(archive_path)
    _assert_pending_write_allowed(archive_path)
    payload = build_pending_import_payload(
        root, slots, material_sources, config=config, guest_name=guest_name)
    atomic_io.write_json_atomic(archive_path, payload, indent=2, ensure_ascii=False)
    return archive_path


def _require_str_or_none(value, label):
    if value is not None and not isinstance(value, str):
        raise ProjectArchiveError(f"Pending-Akte: {label} ungueltig (kein Pfad-String)")
    return value


def _require_str_list(value, label):
    if not isinstance(value, list):
        raise ProjectArchiveError(f"Pending-Akte: {label} muss eine Liste sein")
    if any(not isinstance(p, str) for p in value):
        raise ProjectArchiveError(f"Pending-Akte: {label} enthaelt Nicht-Strings")
    return value


def read_pending_import(archive_path_or_root):
    """Liest eine v5-Pending-Import-Akte -> {slots, material_sources, analysis_state}
    mit ABSOLUTEN Pfaden. Reiner Reader fuer den Analyse-Schnitt (iii); baut KEINE Session.

    Carl-P1: Datei fehlt / analysis_state != "pending" (alt/normal/analysiert/unbekannt)
    -> None. Aber sobald die Akte sich ALS pending deklariert, wird kaputter/Zukunfts-
    Inhalt NIE still ignoriert (sonst faellt der Analysepfad auf die Namensheuristik
    zurueck) -> kontrollierter ProjectArchiveError. DATA-2 bleibt damit auch hier intakt."""
    archive_path = _resolve_archive_path(archive_path_or_root)
    if not os.path.isfile(archive_path):
        return None
    try:
        with open(archive_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectArchiveError(f"Projektakte unlesbar: {e}") from e
    if not isinstance(data, dict) or data.get("analysis_state") != ANALYSIS_STATE_PENDING:
        return None
    # Ab hier ALS pending deklariert -> strikt validieren, nie still auf None.
    _assert_schema_readable(data)  # DATA-2: Zukunfts-Akte -> ProjectArchiveError
    cis = data.get("confirmed_import_slots")
    if not isinstance(cis, dict):
        raise ProjectArchiveError(
            "Pending-Akte ohne gueltige confirmed_import_slots")
    marker = _require_str_or_none(cis.get("marker"), "marker")
    mix = _require_str_or_none(cis.get("mix"), "mix")
    transcript = _require_str_or_none(cis.get("transcript"), "transcript")
    mics = _require_str_list(cis.get("mics", []), "mics")
    videos = _require_str_list(cis.get("videos", []), "videos")
    sources_raw = data.get("material_sources")
    if sources_raw is not None:
        _require_str_list(sources_raw, "material_sources")

    root = os.path.dirname(os.path.dirname(archive_path))
    from .import_model import ConfirmedImportSlots
    slots = ConfirmedImportSlots(
        marker=_abs(marker, root) if marker else None,
        mix=_abs(mix, root) if mix else None,
        mics=tuple(_abs(p, root) for p in mics),
        videos=tuple(_abs(p, root) for p in videos),
        transcript=_abs(transcript, root) if transcript else None,
    )
    sources = [_abs(s, root) for s in (sources_raw or [])]
    return {"slots": slots, "material_sources": sources,
            "analysis_state": data.get("analysis_state")}


def _resolve_archive_path(archive_path_or_root):
    p = archive_path_or_root
    if os.path.isfile(p):
        return p
    if os.path.isdir(p):
        if os.path.basename(os.path.normpath(p)) == ARCHIVE_DIR:
            return os.path.join(p, ARCHIVE_FILE)
        return os.path.join(p, ARCHIVE_DIR, ARCHIVE_FILE)
    return p


def find_project_archive_for_files(paths):
    root = material_root(list(paths or []))
    cand = os.path.join(root, ARCHIVE_DIR, ARCHIVE_FILE)
    return cand if os.path.isfile(cand) else None


def load_project_archive(archive_path_or_root, fallback_config):
    archive_path = _resolve_archive_path(archive_path_or_root)
    if not os.path.isfile(archive_path):
        raise ProjectArchiveError(
            f"Keine Projektakte gefunden: {archive_path}")
    root = os.path.dirname(os.path.dirname(archive_path))  # parent of .peakcut

    try:
        with open(archive_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ProjectArchiveError(f"Projektakte unlesbar: {e}") from e

    parsed = parse_archive_payload(data, fallback_config)
    proj = parsed["project"]
    schema_v = _payload_schema_version(data)

    if schema_v >= 4:
        marker_rel = proj.get("marker_track")
        mix_rel = proj.get("mix_track")
        transcript_rel = proj.get("transcript_path")
    else:
        # v1-v3: Marker hieß keyboard_track; Mix steckt in mic_tracks und wird
        # von set_files() automatisch in mix_track gehoben (legacy_mix).
        marker_rel = proj.get("keyboard_track")
        mix_rel = None
        transcript_rel = None

    marker = _abs(marker_rel, root)
    # mic_tracks bleibt die volle Liste (Mix bleibt drin — Pin-1, s. save).
    mics = [_abs(p, root) for p in proj.get("mic_tracks", [])]
    mix = _abs(mix_rel, root) if mix_rel else None
    transcript = _abs(transcript_rel, root) if transcript_rel else None
    vids = [_abs(p, root) for p in proj.get("videos", [])]

    # transcript_path ist nur ein Quell-Zeiger (Inhalt lebt in transcript.json)
    # → NICHT in die Fehlt-Prüfung. Marker/Mics (inkl. Mix)/Videos müssen da sein.
    missing = [p for p in ([marker] if marker else []) + mics + vids
               if p and not os.path.exists(p)]
    if missing:
        raise ProjectArchiveError(
            "Mediendateien fehlen (Ordner verschoben?): "
            + ", ".join(os.path.basename(m) for m in missing))

    from .project import PeakCutProject
    from .session import PeakCutSession
    from .folgenschnitt_models import MicAssignment, CameraAssignment

    project = PeakCutProject()
    project.set_files(marker, mics, vids, mix=mix, transcript=transcript)
    project.guest_name = proj.get("guest_name")  # NACH set_files (reset!)

    session = PeakCutSession(project, parsed["config"])

    def _abs_p(p):
        return _abs(p, root)

    results = dict(parsed["analysis_results"])
    # JSON macht aus Tupeln Listen — exakt zurück (Round-Trip-Treue:
    # Exporter entpacken zwar beides, aber strikte Gleichheit zählt).
    results["video_offsets"] = [
        tuple(vo) for vo in results.get("video_offsets", [])]
    # P1: Assignment-Pfade gegen den (evtl. neuen) Root absolut machen.
    results["speaker_activity_mic_assignments"] = _map_assignment_paths(
        results.get("speaker_activity_mic_assignments"), _abs_p)
    csv_ref = results.get("speaker_activity_csv")
    if csv_ref:
        csv_abs = _abs(csv_ref, root)
        if not os.path.isfile(csv_abs):
            raise ProjectArchiveError(
                f"Referenzierte speaker_activity.csv fehlt: {csv_ref}")
        from .speaker_activity import read_speaker_activity_csv
        frames = read_speaker_activity_csv(csv_abs)
        results["speaker_activity"] = [fr.to_dict() for fr in frames]
        results["speaker_activity_csv"] = csv_abs

    session.load_analysis_results(results)

    asg = parsed["assignments"]
    session.folgenschnitt_assignment_applied = bool(
        asg.get("folgenschnitt_assignment_applied", False))
    session.folgenschnitt_mic_assignments = [
        MicAssignment.from_dict(d)
        for d in _map_assignment_paths(
            asg.get("folgenschnitt_mic_assignments", []), _abs_p)]
    session.folgenschnitt_camera_assignments = [
        CameraAssignment.from_dict(d)
        for d in _map_assignment_paths(
            asg.get("folgenschnitt_camera_assignments", []), _abs_p)]
    # Slice B v3 (Carl-Plan 2026-06-03): Toggle-Wert hydratisieren.
    # Fehlt (v1/v2) ODER ungueltig (Tippfehler/Migration-Schaden) →
    # Default. normalize_unused_clips_mode wirft nicht.
    session.folgenschnitt_unused_clips_mode = _normalize_clips_mode(
        asg.get("folgenschnitt_unused_clips_mode"))

    # v2: clip_candidates/peak_decisions — fehlt (v1-Akte/None) ->
    # load_analysis_results hat schon aus Peaks gebootstrappt, bleibt.
    # Vorhanden (auch leere Liste) -> exakt aus JSON laden.
    cc = parsed.get("clip_candidates")
    pd = parsed.get("peak_decisions")
    # P2 (Carl): semantisch kaputte v2-Daten (unbekannter Status /
    # illegaler Übergang) werfen ClipCandidateError — als
    # ProjectArchiveError wrappen, damit die HC-4-Robustheit greift
    # (kaputte Akte -> kontrollierter Hinweis + Normalflow, kein Crash).
    from .clip_candidates import (
        ClipCandidate, PeakDecision, ClipCandidateError)
    try:
        if cc is not None:
            session.clip_candidates = [
                ClipCandidate.from_dict(d) for d in cc]
        if pd is not None:
            session.peak_decisions = [
                PeakDecision.from_dict(d) for d in pd]
    except (ClipCandidateError, KeyError, TypeError, ValueError) as e:
        raise ProjectArchiveError(
            f"ClipCandidate-Daten unlesbar: {e}") from e

    # Roadmap #3: Transkript-Referenz tolerant hydratisieren. transcript
    # .json gehört dem Worker; hier NUR lesen, nie schreiben. Fehlt/
    # kaputt -> transcript None + transcript_error, KEIN
    # ProjectArchiveError (Normalflow bleibt, Smart später unavailable).
    session.transcript_ref = parsed.get("transcript")
    session.transcript = None
    session.transcript_error = None
    if session.transcript_ref:
        from .transcript_archive import read_transcript_sidecar
        session.transcript = read_transcript_sidecar(
            root, session.transcript_ref)
        if session.transcript is None:
            session.transcript_error = (
                "Transkript fehlt/unlesbar — Smart-Grenzen nicht verfügbar")
    return session
