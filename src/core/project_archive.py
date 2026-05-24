"""HC-4 — .peakcut/-Projektakte (Persistenz).

Reines Core-Fundament: ein Lauf wird gespeichert + wieder geladen statt
erneut analysiert. Andockpunkt = bestehender Vertrag
session.load_analysis_results(dict). KEIN Hub/Projektbrowser/NAS-Worker
(spätere Roadmap-Punkte #2-#6).
"""

import json
import os
import shutil

CURRENT_SCHEMA_VERSION = 2  # v2: + clip_candidates/peak_decisions (additiv)
ARCHIVE_DIR = ".peakcut"
ARCHIVE_FILE = "project.json"
_CSV_NAME = "speaker_activity.csv"
_CSV_REF = f"{ARCHIVE_DIR}/{_CSV_NAME}"

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

    kb = _rel(project.keyboard_track, material_root)
    mics = [_rel(p, material_root) for p in project.mic_tracks]
    vids = [_rel(p, material_root) for p in project.videos]
    external = any(_is_external(p) for p in [kb] + mics + vids if p)

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
            "keyboard_track": kb,
            "mic_tracks": mics,
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


def parse_archive_payload(payload, fallback_config):
    if not isinstance(payload, dict):
        raise ProjectArchiveError("Projektakte ist kein gültiges Objekt")
    missing = [s for s in _REQUIRED_SECTIONS if s not in payload]
    if missing:
        raise ProjectArchiveError(
            f"Projektakte unvollständig — fehlende Sektion(en): "
            f"{', '.join(missing)}")
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
    }


# --- Task 3+4: save / load / find -----------------------------------------

def _media_paths(project):
    paths = list(project.mic_tracks) + list(project.videos)
    if project.keyboard_track:
        paths.append(project.keyboard_track)
    return paths


def save_project_archive(session, root=None):
    project = session.project
    if root is None:
        root = material_root(_media_paths(project), project.keyboard_track)
    archive_dir = os.path.join(root, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)

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
    with open(archive_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return archive_path


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

    kb = _abs(proj.get("keyboard_track"), root)
    mics = [_abs(p, root) for p in proj.get("mic_tracks", [])]
    vids = [_abs(p, root) for p in proj.get("videos", [])]

    missing = [p for p in ([kb] if kb else []) + mics + vids
               if p and not os.path.exists(p)]
    if missing:
        raise ProjectArchiveError(
            "Mediendateien fehlen (Ordner verschoben?): "
            + ", ".join(os.path.basename(m) for m in missing))

    from .project import PeakCutProject
    from .session import PeakCutSession
    from .folgenschnitt_models import MicAssignment, CameraAssignment

    project = PeakCutProject()
    project.set_files(kb, mics, vids)
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
