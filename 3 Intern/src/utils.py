# utils.py - shared helpers and path constants

import os

# Directory structure:
# App/
#   1 Material/
#   2 Export/
#   3 Intern/             <- INTERN_DIR
#     src/                <- this file lives here
#     assets/
#     temp/

INTERN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(INTERN_DIR)

# User-facing directories
MATERIAL_DIR = os.path.join(APP_DIR, "1 Material")
EXPORT_DIR = os.path.join(APP_DIR, "2 Export")

# Internal directories
TEMP_DIR = os.path.join(INTERN_DIR, "temp")
ASSETS_DIR = os.path.join(INTERN_DIR, "assets")
LUTS_DIR = os.path.join(INTERN_DIR, "luts")


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
