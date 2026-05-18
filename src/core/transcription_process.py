"""Roadmap #3 Task 2 — Transkriptions-Child-Prozess.

Echtes Whisper wird NUR hier (im Child) importiert — nie im
GUI-Prozess, nie in pytest (Tests injizieren einen Fake-Process, der
dieses Target nicht aufruft).
"""

import json
import sys


def _build_engine(req):
    """Engine erst hier instanziieren (lazy Import). v1: mlx-whisper."""
    name = req.get("engine", "mlx-whisper")
    if name == "mlx-whisper":
        import mlx_whisper  # noqa: F401  (nur im Child verfügbar)

        class _MlxEngine:
            def transcribe(self, audio_path, *, language, model):
                from core.transcription import (
                    Transcript, TranscriptSegment, TranscriptWord)
                r = mlx_whisper.transcribe(
                    audio_path, path_or_hf_repo=model, language=language,
                    word_timestamps=True)
                segs = []
                for s in r.get("segments", []):
                    words = tuple(
                        TranscriptWord(int(w["start"] * 1000),
                                       max(int(w["start"] * 1000) + 1,
                                           int(w["end"] * 1000)),
                                       str(w["word"]))
                        for w in s.get("words", []))
                    segs.append(TranscriptSegment(
                        int(s["start"] * 1000),
                        max(int(s["start"] * 1000) + 1,
                            int(s["end"] * 1000)),
                        str(s["text"]).strip(), words=words))
                return Transcript(segments=tuple(segs))

        return _MlxEngine()
    raise ValueError(f"Unbekannte Transkriptions-Engine: {name}")


def run_transcription(req, engine=None):
    """req: {audio_path, engine, model, language}. Gibt
    {"transcript": <dict>} oder {"error": <str>} zurück."""
    try:
        eng = engine if engine is not None else _build_engine(req)
        t = eng.transcribe(req["audio_path"], language=req["language"],
                            model=req["model"])
        return {"transcript": t.to_dict()}
    except Exception as e:  # noqa: BLE001 (kontrolliert ans Parent)
        return {"error": str(e)}


def _transcribe_worker_target(req, result_queue, progress_queue):
    """Top-level für multiprocessing.Process (Pickling)."""
    try:
        result_queue.put(run_transcription(req))
    except Exception as e:  # noqa: BLE001
        result_queue.put({"error": str(e)})


def main():
    req = json.loads(sys.argv[1])
    print(json.dumps(run_transcription(req)))


if __name__ == "__main__":
    main()
