"""#3-Revision Task 2 (Teil A) — EIN gemeinsamer ffprobe-Helfer.

Pin 1: kein bare `ffprobe`. Genau EINE Variante über `utils.FFPROBE_BIN`
(FROZEN-aware, gebundeltes Binary in der .app). Die vorhandenen
Exporter-Proben (`_probe_video_info`/`_probe_audio_info`) werden hier
durchgeleitet statt eine dritte ffprobe-Variante zu bauen — Verhalten
unverändert (Argumente/Fallbacks bleiben in den Aufrufern).
"""

import subprocess

from utils import FFPROBE_BIN


def run_ffprobe(args, *, timeout=10):
    """Gemeinsamer ffprobe-Aufruf. stdout (str) bei Erfolg, sonst None.
    Tolerant: wirft nie (fehlendes Binary/Timeout/Returncode -> None)."""
    try:
        r = subprocess.run([FFPROBE_BIN, *args],
                            capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001 (Binary fehlt / Timeout / OSError)
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def probe_duration_ms(path):
    """Mediendauer in ms für den Ausricht-Schutz. Nicht ermittelbar
    -> None (nie werfen; der Worker meldet 'Dauer unbekannt' separat)."""
    out = run_ffprobe(["-v", "error", "-show_entries", "format=duration",
                       "-of", "default=nokey=1:noprint_wrappers=1", path])
    if not out:
        return None
    try:
        return int(round(float(out.strip()) * 1000))
    except (TypeError, ValueError):
        return None
