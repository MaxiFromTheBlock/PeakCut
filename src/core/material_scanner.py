"""Scanner-Slice (Carl): Material -> Kandidaten-REPORT (keine Schreibzugriffe).

Robuster, NAMENS-UNABHAENGIGER Anker = DAUER: Aufnahme-Spuren teilen die Folgenlaenge,
die Bibliothek/SFX/Musik nicht (gemessen: Aufnahme 9695s, Bibliothek 1-6s). Darauf DUENNE
Inhalts-Evidence: Stille-Anteil + Impuls-Pegel. Damit lassen sich drei Faelle unter den
Aufnahme-Spuren unterscheiden, OHNE Namen:
  - leerer/ungenutzter Kanal: viel Stille + KEIN Pegel              -> ignore
  - Marker (Fusspedal): viel Stille + LAUTE Impulse                 -> marker
  - Speech/Mix: kontinuierlich (wenig Stille)                       -> mic/mix (name_hint)
Der Name ist nur ein HINWEIS und wird vom Inhalt geschlagen. Ausgabe = Liste ImportCandidate
mit unverbindlichem suggested_role; die Wahrheit setzt erst der Confirm-Schritt.
"""
import os
import subprocess

from core.import_classifier import is_mix_track, is_marker_track
from core.import_model import (
    ImportCandidate, ImportEvidence, KIND_AUDIO, KIND_VIDEO,
    ROLE_MARKER, ROLE_MIC, ROLE_MIX, ROLE_CAMERA, ROLE_IGNORE,
)

_AUDIO_EXTS = {".wav", ".mp3", ".aif", ".aiff", ".m4a", ".flac", ".ogg"}
_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}

EPISODE_FRACTION = 0.5          # ab diesem Anteil der Maximaldauer = "Folgenlaenge" (Aufnahme)
MARKER_SILENCE_THRESHOLD = 0.85  # Marker: viel Stille ...
MARKER_PEAK_THRESHOLD = 0.2      # ... ABER mit lauten Impulsen
EMPTY_PEAK_THRESHOLD = 0.05      # darunter = leerer/ungenutzter Kanal (kein echter Impuls)


def _kind(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext in _VIDEO_EXTS:
        return KIND_VIDEO
    if ext in _AUDIO_EXTS:
        return KIND_AUDIO
    return None


def _name_hint(path: str):
    if is_mix_track(path):      # Name NUR als Hinweis (B1-Muster fuer "P8Mix" steckt drin)
        return ROLE_MIX
    if is_marker_track(path):
        return ROLE_MARKER
    return None


def _suggest(kind, episode, audio_sig, name_hint):
    if kind == KIND_VIDEO:
        return ROLE_CAMERA if episode else ROLE_IGNORE      # kurze Social-Clips raus
    if not episode:
        return ROLE_IGNORE                                   # Bibliothek/SFX/Musik
    if audio_sig is not None:
        silence, peak = audio_sig
        if peak is not None and peak < EMPTY_PEAK_THRESHOLD:
            return ROLE_IGNORE                               # leerer/ungenutzter Kanal
        if (silence is not None and peak is not None
                and silence >= MARKER_SILENCE_THRESHOLD and peak >= MARKER_PEAK_THRESHOLD):
            return ROLE_MARKER                               # Stille + laute Impulse (Inhalt > Name)
    if name_hint == ROLE_MIX:
        return ROLE_MIX                                      # Mix bleibt namens-gestuetzt
    if name_hint == ROLE_MARKER:
        return ROLE_MARKER                                   # Name nur als Backup
    return ROLE_MIC


def scan_material(paths, *, probe_duration=None, audio_signal=None,
                  episode_fraction: float = EPISODE_FRACTION):
    """paths -> [ImportCandidate]. probe_duration(path)->ms|None und audio_signal(path)->
    (stille_anteil, peak_pegel)|None sind injizierbar (Test); Defaults = echte ffprobe/
    soundfile-Impls. NUR Report, keine Schreibzugriffe."""
    probe_duration = probe_duration or ffprobe_duration_ms
    audio_signal = audio_signal or audio_silence_peak

    media = [(p, k) for p, k in ((p, _kind(p)) for p in paths) if k is not None]
    durations = {p: probe_duration(p) for p, _ in media}
    known = [d for d in durations.values() if d]
    max_dur = max(known) if known else 0

    out = []
    for p, kind in media:
        dur = durations.get(p)
        episode = bool(dur) and max_dur > 0 and dur >= episode_fraction * max_dur
        name_hint = _name_hint(p)
        # Inhalts-Signal nur fuer Aufnahme-Audio (Marker/leer/Speech stecken unter den langen Spuren).
        sig = audio_signal(p) if (kind == KIND_AUDIO and episode) else None
        silence, peak = sig if sig else (None, None)
        ev = ImportEvidence(
            duration_ms=dur, episode_length=episode, is_video=(kind == KIND_VIDEO),
            silence_ratio=silence, peak_level=peak, name_hint=name_hint,
        )
        out.append(ImportCandidate(
            path=p, kind=kind, evidence=ev,
            suggested_role=_suggest(kind, episode, sig, name_hint),
        ))
    return out


# ── Echte Default-Impls (in Tests injiziert, daher hier defensiv) ─────────────
def ffprobe_duration_ms(path: str):
    """Dauer in ms via ffprobe, oder None bei Fehler."""
    try:
        from utils import FFPROBE_BIN
    except Exception:
        FFPROBE_BIN = "ffprobe"
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return int(float(out.stdout.strip()) * 1000) if out.stdout.strip() else None
    except Exception:
        return None


def audio_silence_peak(path: str, *, windows: int = 8, window_s: int = 15):
    """Duenne Inhalts-Evidence (Stille-Anteil, Impuls-Pegel) — HYBRID (Spec 2026-06-28):
    verstreute Fenster ueber die GANZE Datei (silence = Mittel, peak = max). Ist ein langer
    Kandidat sehr still, zeigt aber noch keinen Impuls, ein bounded Voll-Peak-Pass NUR fuer
    diese — so werden spaerliche Fusspedal-Klicks (z.B. erst nach 120s) gefangen, ohne kurze
    SFX teuer zu scannen (die sind nicht Episoden-Laenge -> diese Funktion wird fuer sie gar
    nicht gerufen). Marker = hohe Stille + hoher Pegel; leerer Kanal = hohe Stille + ~0;
    Speech/Mix = niedrige Stille. None bei Fehler."""
    try:
        import soundfile as sf
        import numpy as np
        with sf.SoundFile(path) as f:
            sr = f.samplerate
            total = len(f)
            wn = int(window_s * sr)
            if total <= 0 or sr <= 0:
                return None
            # Kurze Datei: einmal alles (kein Seek-Aufwand).
            if wn <= 0 or total <= windows * wn:
                data = f.read(total, dtype="float32")
                if getattr(data, "ndim", 1) > 1:
                    data = data.mean(axis=1)
                if len(data) == 0:
                    return None
                a = np.abs(data)
                return float((a < 0.01).mean()), float(a.max())
            # Verstreute Fenster ueber die ganze Datei.
            step = (total - wn) / (windows - 1)
            silences: list = []
            peak = 0.0
            for k in range(windows):
                f.seek(int(k * step))
                data = f.read(wn, dtype="float32")
                if getattr(data, "ndim", 1) > 1:
                    data = data.mean(axis=1)
                if len(data) == 0:
                    continue
                a = np.abs(data)
                silences.append(float((a < 0.01).mean()))
                peak = max(peak, float(a.max()))
            if not silences:
                return None
            silence = float(np.mean(silences))
            # Hybrid: sehr still, aber noch kein Impuls -> bounded Voll-Pass nur fuer das
            # Maximum (faengt einen einzelnen, spaerlichen Klick irgendwo in der Folge).
            if silence >= MARKER_SILENCE_THRESHOLD and peak < MARKER_PEAK_THRESHOLD:
                f.seek(0)
                block = max(1, sr * 30)
                while True:
                    chunk = f.read(block, dtype="float32")
                    if len(chunk) == 0:
                        break
                    if getattr(chunk, "ndim", 1) > 1:
                        chunk = chunk.mean(axis=1)
                    peak = max(peak, float(np.abs(chunk).max()))
            return silence, peak
    except Exception:
        return None


__all__ = ["scan_material", "ffprobe_duration_ms", "audio_silence_peak",
           "EPISODE_FRACTION", "MARKER_SILENCE_THRESHOLD", "MARKER_PEAK_THRESHOLD",
           "EMPTY_PEAK_THRESHOLD"]
