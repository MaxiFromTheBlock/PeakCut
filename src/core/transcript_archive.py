"""Roadmap #3 Gate A — Transcript-Sidecar + Archive-Reference.

Besitz-Vertrag (Carl-Gate-A-Zusatz, Claude-verifiziert):
- `transcript.json` ist **Worker-Besitz**: früh & eigenständig vom
  TranscriptWorker geschrieben (parallel zur Analyse), bevor je ein
  save_project_archive lief. Der Worker nutzt **dieselbe** Root-/
  ARCHIVE_DIR-Auflösung wie save_project_archive und legt `.peakcut/`
  selbst an.
- `project.json["transcript"]` ist nur ein **Referenzblock**, erst beim
  späteren _autosave()/save_project_archive() geschrieben.
- save_project_archive erzeugt/überschreibt `transcript.json` **NIE**
  (bewusste Asymmetrie zu `speaker_activity.csv`, das beim Archivieren
  entstehen darf, weil es Analyse-Ergebnis ist).
"""

import json
import os

from .project_archive import ARCHIVE_DIR, material_root, _media_paths, _rel
from .transcription import Transcript

TRANSCRIPT_NAME = "transcript.json"
TRANSCRIPT_REF = f"{ARCHIVE_DIR}/{TRANSCRIPT_NAME}"


def transcript_root(project):
    """Exakt dieselbe Wurzel-Auflösung wie save_project_archive
    (sonst divergierender .peakcut/-Ordner / toter Verweis)."""
    return material_root(_media_paths(project), project.keyboard_track)


def transcript_sidecar_path(project):
    return os.path.join(transcript_root(project), ARCHIVE_DIR,
                        TRANSCRIPT_NAME)


def build_transcript_ref(project, *, engine, model, language, audio_path):
    root = transcript_root(project)
    return {
        "path": TRANSCRIPT_REF,
        "engine": engine,
        "model": model,
        "language": language,
        "audio_path": _rel(audio_path, root),
    }


def write_transcript_sidecar(project, transcript, *, engine, model,
                             language, audio_path):
    """Früh vom Worker aufgerufen. Legt .peakcut/ selbst an, schreibt
    transcript.json atomar, gibt den Referenzblock zurück (den der
    Worker auf session.transcript_ref legt — persistiert wird er erst
    später durch save_project_archive)."""
    root = transcript_root(project)
    archive_dir = os.path.join(root, ARCHIVE_DIR)
    os.makedirs(archive_dir, exist_ok=True)
    path = os.path.join(archive_dir, TRANSCRIPT_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(transcript.to_dict(), f, ensure_ascii=False)
    os.replace(tmp, path)
    return build_transcript_ref(project, engine=engine, model=model,
                                language=language, audio_path=audio_path)


def read_transcript_sidecar(root, ref):
    """Tolerant: fehlt/kaputt -> None (nie werfen). Smart wird dann
    später als unavailable markiert, Normalflow bleibt unberührt."""
    if not ref or not isinstance(ref, dict):
        return None
    rel = ref.get("path")
    if not rel:
        return None
    path = os.path.normpath(os.path.join(root, rel))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Transcript.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
