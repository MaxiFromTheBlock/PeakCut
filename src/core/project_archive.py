"""HC-4 — .peakcut/-Projektakte (Persistenz).

Reines Core-Fundament: ein Lauf kann gespeichert + wieder geladen
werden statt erneut analysiert. Andockpunkt ist der bestehende
Vertrag session.load_analysis_results(dict). KEIN Hub, kein
Projektbrowser, kein NAS-Worker (= spätere Roadmap-Punkte).

Task 0: Format + Versions-/Unbekannt-Feld-Toleranz (Gate A).
Tasks 1-7 (relative Pfade, Peak-Round-Trip exakt, CSV-Referenz,
Session save/load, Export-Identität, GUI) folgen.
"""

CURRENT_SCHEMA_VERSION = 1
ARCHIVE_DIR = ".peakcut"
ARCHIVE_FILE = "project.json"

# Nur die Config-Schlüssel, die die Export-Identität beeinflussen
# (verifiziert: fps steuert video_offset-Parsing in load_analysis_results;
# context_duration_ms ist Peak-Default). Snapshot statt Laufumgebung.
_CONFIG_SNAPSHOT_KEYS = ("fps", "context_duration_ms")

_REQUIRED_SECTIONS = ("project", "analysis_results", "assignments")


class ProjectArchiveError(Exception):
    """Kontrollierter Fehler beim Lesen/Schreiben der Projektakte."""


def _to_dict_list(items):
    out = []
    for it in items or []:
        out.append(it.to_dict() if hasattr(it, "to_dict") else it)
    return out


def build_archive_payload(session, material_root):
    """Serialisierbares Payload-Dict (noch ohne Datei-IO / ohne die
    exakte Peak-/Pfad-Logik der Tasks 1-3 — die docken hier additiv an)."""
    project = session.project
    cfg = session.config

    def _cfg(key, default=None):
        getter = getattr(cfg, "get", None)
        return getter(key, default) if getter else default

    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "app": "PeakCut",
        "config": {k: _cfg(k) for k in _CONFIG_SNAPSHOT_KEYS
                   if _cfg(k) is not None},
        "project": {
            "keyboard_track": project.keyboard_track,
            "mic_tracks": list(project.mic_tracks),
            "videos": list(project.videos),
            "guest_name": project.guest_name,
            "path_root_strategy": "common_parent",
            "has_external_paths": False,
        },
        "analysis_results": {
            "peaks": [],  # Task 2: exakte Peak-Serialisierung
            "video_offsets": list(getattr(session, "video_offsets", []) or []),
            "speaker_activity_csv": getattr(
                session, "speaker_activity_csv", None),
            "speaker_activity_mic_assignments": _to_dict_list(
                getattr(session, "speaker_activity_mic_assignments", [])),
        },
        "assignments": {
            "folgenschnitt_assignment_applied": bool(getattr(
                session, "folgenschnitt_assignment_applied", False)),
            "folgenschnitt_mic_assignments": _to_dict_list(
                getattr(session, "folgenschnitt_mic_assignments", [])),
            "folgenschnitt_camera_assignments": _to_dict_list(
                getattr(session, "folgenschnitt_camera_assignments", [])),
        },
    }


def parse_archive_payload(payload, fallback_config):
    """Liest nur bekannte Sektionen (unbekannte/zukünftige Felder werden
    ignoriert, nicht gecrasht). Schema-Version wird best-effort
    toleriert (vor- und rückwärts). Fehlende Pflichtsektion ->
    ProjectArchiveError."""
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
    }
