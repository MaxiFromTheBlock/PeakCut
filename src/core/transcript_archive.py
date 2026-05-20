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


def audio_fingerprint(path):
    """Billiger Mix-Fingerprint für den Transkript-Cache (Spec §11 R6):
    size + mtime_ns, KEIN teurer Hash im UI-Pfad. Fehlende Datei ->
    None (tolerant, nie werfen)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def build_transcript_ref(project, *, engine, model, language, audio_path,
                         source="whisper", source_path=None,
                         transcript_span_ms=None, audio_duration_ms=None):
    """#3-Revision Gate A: additiv erweitert (Spec §11 R2/R6).

    `source` + `audio_fingerprint` sind immer dabei (Cache + pluggbare
    Quelle). `source_path`/`transcript_span_ms`/`audio_duration_ms` nur
    wenn bekannt -> alte Akten ohne diese Felder bleiben gültig und
    werden weiter sauber gelesen (read_transcript_sidecar ist tolerant
    und nutzt nur `path`)."""
    root = transcript_root(project)
    ref = {
        "path": TRANSCRIPT_REF,
        "engine": engine,
        "model": model,
        "language": language,
        "audio_path": _rel(audio_path, root),
        "source": source,
        "audio_fingerprint": audio_fingerprint(audio_path),
    }
    if source_path is not None:
        ref["source_path"] = source_path
    if transcript_span_ms is not None:
        ref["transcript_span_ms"] = transcript_span_ms
    if audio_duration_ms is not None:
        ref["audio_duration_ms"] = audio_duration_ms
    return ref


def write_transcript_json(path, transcript):
    """Low-level atomarer Schreiber (tmp + os.replace). Legt den
    Zielordner selbst an. Wird vom Child-Teil des Workers benutzt
    (P1: nicht das volle Transcript durch die Queue schieben)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(transcript.to_dict(), f, ensure_ascii=False)
    os.replace(tmp, path)


def write_transcript_sidecar(project, transcript, *, engine, model,
                             language, audio_path):
    """Parent-seitiger High-Level-Helfer (Gate-A-Tests / Nicht-Prozess).
    Legt .peakcut/ an, schreibt transcript.json atomar, gibt den
    Referenzblock zurück (Persistenz in project.json erst später durch
    save_project_archive — Besitz-Vertrag)."""
    write_transcript_json(transcript_sidecar_path(project), transcript)
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


# ── #3-Revision Task 2 (Teil A) — Cache + Ausricht-Schutz ──────────────


def transcript_span_ms(transcript):
    """Gesamtspanne eines Transkripts (größtes Segment-Ende). Leeres
    Transkript -> 0. Eingabe ist der eingefrorene Gate-A-Vertrag."""
    segs = getattr(transcript, "segments", ()) or ()
    return max((s.end_ms for s in segs), default=0)


def alignment_drift(span_ms, duration_ms, tolerance_ms):
    """True, wenn Text-Gesamtspanne und Audiodauer um mehr als die
    Toleranz auseinanderliegen (symmetrisch, Spec §11 R2). Audiodauer
    unbekannt -> False (kein Fehlalarm; der Worker meldet 'Dauer
    unbekannt' separat)."""
    if duration_ms is None:
        return False
    return abs(int(span_ms) - int(duration_ms)) > int(tolerance_ms)


def import_descript_transcript(project, docx_path, audio_path,
                                *, language="de"):
    """#3-Rev R2 Schluss-Gate: Descript-`.docx` einlesen, Sidecar
    schreiben, vollständigen ref bauen (source='descript', span +
    audio_duration_ms für den Ausricht-Schutz; Drift detektiert
    Stufe B/Statuszeile selbst). Pure Funktion, keine UI."""
    from .descript_docx import parse_descript_docx
    from .media_probe import probe_duration_ms
    transcript = parse_descript_docx(docx_path)
    span = transcript_span_ms(transcript)
    duration = probe_duration_ms(audio_path)
    write_transcript_json(transcript_sidecar_path(project), transcript)
    ref = build_transcript_ref(
        project, engine="descript", model="-", language=language,
        audio_path=audio_path, source="descript", source_path=docx_path,
        transcript_span_ms=span,
        audio_duration_ms=duration if duration is not None else None)
    return ref


def cache_reusable_ref(prev_ref, *, current_fingerprint, engine, model,
                       language, root):
    """Spec §11 R6: ein gespeicherter Transkript-Verweis ist nur dann
    wiederverwendbar (kein Whisper), wenn der Mix-Fingerabdruck und
    Engine/Modell/Sprache passen UND das Sidecar lesbar ist. Sonst None
    (-> neu transkribieren). Rein, kein Qt, voll testbar."""
    if not isinstance(prev_ref, dict):
        return None
    if prev_ref.get("audio_fingerprint") != current_fingerprint:
        return None
    if (prev_ref.get("engine") != engine
            or prev_ref.get("model") != model
            or prev_ref.get("language") != language):
        return None
    if read_transcript_sidecar(root, prev_ref) is None:
        return None
    return prev_ref
