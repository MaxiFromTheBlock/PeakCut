# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PeakCut V3 is a Python desktop application for audio peak detection and extraction. It identifies keyboard peaks in mixed audio/video recordings and creates edited exports with timecode markers. Used in production for "Hotel Matze" podcast.

**Branch structure:**
- `main` - v1.0-stable, production-safe
- `develop` - active development

## Commands

```bash
# Run the application
python src/main.py

# Install dependencies
pip install -r requirements.txt
```

There is no test suite configured.

## Architecture

**Entry Point:** `src/main.py` → calls `start_gui()` from `gui.py`

**Module Structure:**
- `gui.py` - Tkinter UI with button handlers, manages playback state
- `peaks.py` - Peak detection algorithm, audio playback, navigation between peaks
- `sync.py` - Video-to-audio synchronization using cross-correlation (scipy)
- `export.py` - Generates MP3 with spoken numbers (via macOS TTS) + audio segments, creates timecode .txt
- `status.py` - Observer pattern for status updates (GUI + terminal)
- `utils.py` - Currently empty (cleanup candidate)

**State Management:** Global variables in `peaks.py` (`_peaks`, `_current_peak`, `_keyboard_audio`, `_mic_audios`, `_mode`, `_ignored_peaks`) with getter functions for cross-module access.

**Audio Processing Stack:** moviepy (video extraction) → pydub (audio manipulation) → soundfile/numpy (analysis) → simpleaudio (playback)

## File Conventions

- Input files: `material/` directory
- Output files: `export/` directory
- Temp files: `temp/` directory
- Keyboard audio identified by filename keywords: "keyboard", "keys", "klavier"
- Reference audio identified by "mix" in filename

## Timecode Format

`HH:MM:SS:FF` (25 fps) used throughout the application.

## Key Parameters

In `peaks.py`:
- `PREVIEW_DURATION_MS = 1000` (keyboard mode preview)
- `CONTEXT_DURATION_MS = 15000` (mic mode context window)
- Peak detection: `threshold_factor=0.4`, `min_gap_ms=15000`

## TTS (Text-to-Speech)

Numbers are generated via macOS `say -v Anna` (German voice). Fallback to `assets/zahlen/*.mp3` if TTS fails.

## Paths

All paths are relative to the app directory (not CWD). Defined in `utils.py`:
- `APP_DIR` - Root of the application
- `MATERIAL_DIR`, `EXPORT_DIR`, `TEMP_DIR`, `ASSETS_DIR` - Working directories

The app can be started from any location.
