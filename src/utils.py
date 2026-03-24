# utils.py - shared helpers and path constants

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Detect PyInstaller bundle
FROZEN = getattr(sys, 'frozen', False)

if FROZEN:
    # Running as .app bundle — assets are in sys._MEIPASS
    _BUNDLE_DIR = sys._MEIPASS
    ASSETS_DIR = os.path.join(_BUNDLE_DIR, "assets")
    LUTS_DIR = os.path.join(_BUNDLE_DIR, "luts")
    # Writable data goes to ~/Library/Application Support/PeakCut/
    DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "PeakCut")
else:
    # Development mode — everything relative to App/
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS_DIR = os.path.join(APP_ROOT, "assets")
    LUTS_DIR = os.path.join(APP_ROOT, "luts")
    DATA_DIR = APP_ROOT

TEMP_DIR = os.path.join(DATA_DIR, "temp")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# Bundled ffmpeg/ffprobe paths
if FROZEN:
    _FFMPEG_DIR = os.path.join(_BUNDLE_DIR, "ffmpeg_bin", "bin")
    FFMPEG_BIN = os.path.join(_FFMPEG_DIR, "ffmpeg")
    FFPROBE_BIN = os.path.join(_FFMPEG_DIR, "ffprobe")
else:
    FFMPEG_BIN = "ffmpeg"
    FFPROBE_BIN = "ffprobe"


def get_logger(name: str = "peakcut") -> logging.Logger:
    """Get a configured logger that writes to logs/peakcut.log.

    Uses RotatingFileHandler: max 5 MB per file, 2 backups.
    Also logs to stderr for development visibility.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)

    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, "peakcut.log")

    # File handler — detailed, rotated
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    # Stderr handler — warnings and above only
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stderr_handler)

    return logger


def validate_media_file(filepath: str) -> str | None:
    """Validate a media file using ffprobe.

    Returns None if valid, or an error message string if invalid.
    Checks: file exists, ffprobe can read it, has at least one audio stream.
    """
    import subprocess

    if not os.path.exists(filepath):
        return f"Datei nicht gefunden: {os.path.basename(filepath)}"

    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", filepath],
            capture_output=True, text=True, timeout=10
        )
    except subprocess.TimeoutExpired:
        return f"Timeout beim Lesen: {os.path.basename(filepath)}"
    except FileNotFoundError:
        return "ffprobe nicht gefunden — ist ffmpeg installiert?"

    if result.returncode != 0:
        return f"Datei nicht lesbar: {os.path.basename(filepath)}"

    streams = result.stdout.strip().splitlines()
    has_audio = any("audio" in s for s in streams)

    if not has_audio:
        return f"Kein Audio-Stream gefunden: {os.path.basename(filepath)}"

    return None


def parse_timecode_to_ms(tc_str: str, fps: int) -> int:
    """Parse SMPTE timecode (HH:MM:SS:FF) to milliseconds."""
    negative = tc_str.startswith("-")
    tc_str = tc_str.lstrip("-")
    parts = tc_str.split(":")
    if len(parts) != 4:
        return 0
    hours, minutes, seconds, frames = map(int, parts)
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + int(frames * 1000 / fps)
    return -total_ms if negative else total_ms


def ms_to_timecode(ms: int, fps: int) -> str:
    """Convert milliseconds to SMPTE timecode (HH:MM:SS:FF)."""
    total_frames = int(ms / 1000 * fps)
    frames = total_frames % fps
    total_seconds = total_frames // fps
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def ms_to_frames(ms: int, fps: int) -> int:
    """Convert milliseconds to frame count."""
    return int(ms / 1000 * fps)


def ms_to_mmss(ms: int) -> str:
    """Convert milliseconds to M:SS display string."""
    total_s = max(0, ms) // 1000
    m = total_s // 60
    s = total_s % 60
    return f"{m}:{s:02d}"
