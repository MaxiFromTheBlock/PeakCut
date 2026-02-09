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
    """Parse timecode string (HH:MM:SS:FF) to milliseconds."""
    negative = tc_str.startswith("-")
    tc_str = tc_str.lstrip("-")
    parts = tc_str.split(":")
    if len(parts) != 4:
        return 0
    hours, minutes, seconds, frames = map(int, parts)
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + int(frames * 1000 / fps)
    return -total_ms if negative else total_ms
