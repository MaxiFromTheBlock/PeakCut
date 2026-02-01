# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PeakCut V3 is a Python desktop application for audio peak detection and extraction. It identifies keyboard peaks in mixed audio/video recordings and creates edited exports with timecode markers. The UI and documentation are in German.

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
- `export.py` - Generates MP3 with spoken numbers + audio segments, creates timecode .txt
- `status.py` - Observer pattern for status updates (GUI + terminal)

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
