# utils.py - shared helpers

import os

# Directory structure:
# App/
#   1 Material/
#   2 Export/
#   3 Intern/             ← INTERN_DIR
#     src/                ← this file lives here
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


def format_peak_time(ms, fps=25):
    """Convert milliseconds to timecode HH:MM:SS:FF"""
    total_seconds = ms / 1000
    total_frames = int(total_seconds * fps)
    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
