# utils.py - shared helpers

import os

# App root directory (one level up from src/)
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Standard directories
MATERIAL_DIR = os.path.join(APP_DIR, "material")
EXPORT_DIR = os.path.join(APP_DIR, "export")
TEMP_DIR = os.path.join(APP_DIR, "temp")
ASSETS_DIR = os.path.join(APP_DIR, "assets")


def format_peak_time(ms, fps=25):
    """Convert milliseconds to timecode HH:MM:SS:FF"""
    total_seconds = ms / 1000
    total_frames = int(total_seconds * fps)
    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
