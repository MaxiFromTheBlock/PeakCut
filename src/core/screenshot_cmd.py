"""Qt-freier ffmpeg-Argument-Builder fuer den gegradeten Screenshot.

EINE Wahrheit fuer Desktop (gui/video_preview_peak.py::ScreenshotWorker) UND
Web-Engine (PeakCut-web engine/screenshot.py). Nur Argumente + Grade-Reihenfolge,
kein Subprozess, kein Qt — damit beide Seiten byte-identische JPEGs erzeugen,
ohne das Kommando zu duplizieren.

Grade-Reihenfolge ist paritaet-kritisch: Helligkeit (lutrgb, factor=2**(b/100),
lineare RGB-Multiplikation wie Premiere) VOR der LUT (lut3d). -ss vor -i fuer
schnellen Seek, genau ein Frame, JPEG q2. Eine nicht existente LUT-Datei wird
stillschweigend uebersprungen.
"""
import os


def build_screenshot_cmd(video_path, position_s, lut_path, brightness, out_path, *, ffmpeg):
    """ffmpeg-argv fuer EIN gegradetes Standbild. `ffmpeg` = Binary-Pfad (Desktop:
    utils.FFMPEG_BIN; Web: engine-eigene Aufloesung). `lut_path` leer/None oder nicht
    existent -> keine LUT."""
    cmd = [ffmpeg, "-y", "-ss", str(position_s), "-i", video_path, "-frames:v", "1"]
    filters = []
    if brightness != 0:
        factor = 2 ** (brightness / 100.0)  # -100→0.5x, 0→1.0x, +100→2.0x
        expr = f"clip(val*{factor:.4f},0,255)"
        filters.append(f"lutrgb=r='{expr}':g='{expr}':b='{expr}'")
    if lut_path and os.path.exists(lut_path):
        filters.append(f"lut3d='{lut_path}'")
    if filters:
        cmd.extend(["-vf", ",".join(filters)])
    cmd.extend(["-q:v", "2", out_path])
    return cmd
