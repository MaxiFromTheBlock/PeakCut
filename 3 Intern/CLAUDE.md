# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PeakCut is a Python/PyQt6 desktop app for podcast post-production. It detects keyboard peaks (foot pedal markers) in audio recordings and exports numbered audio clips with timecodes. Used in production for "Hotel Matze" podcast.

## Folder Structure

```
App/
├── 1 Material/     ← User input (audio/video files)
├── 2 Export/       ← Output (MP3 + TXT + Screenshots)
├── 3 Intern/       ← Source code & dependencies
│   ├── src/
│   ├── assets/
│   ├── venv311/
│   └── requirements.txt
└── README.txt      ← User instructions
```

## Commands

```bash
# Run PeakCut
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"

# Install dependencies
python3.11 -m venv "3 Intern/venv311"
source "3 Intern/venv311/bin/activate"
pip install -r "3 Intern/requirements.txt"
```

## Architecture

**Entry Point:** `3 Intern/src/main.py` → `gui.py:start_gui()`

**Modules:**
- `gui.py` - Tkinter UI, scrollable status display, button handlers
- `peaks.py` - Peak detection, audio playback, navigation
- `sync.py` - Video-to-audio sync via cross-correlation (optional)
- `export.py` - MP3 export with TTS numbers + timecode TXT
- `screenshots.py` - Extract frames from videos with LUT (experimental)
- `status.py` - Observer pattern for UI updates
- `utils.py` - Shared paths (APP_DIR, MATERIAL_DIR, etc.) and helpers

**State:** Global variables in `peaks.py` with getter functions for cross-module access.

## Key Features

1. **TTS Numbers** - macOS `say -v Anna` generates spoken numbers (no 49-limit)
2. **Auto Sync** - Detects video offsets via audio correlation
3. **Combined Export** - Single TXT with video offsets + peak timecodes
4. **Screenshots** - 100 random frames per video with Kodak LUT (experimental)

## File Naming Conventions

- Keyboard audio: filename contains "keyboard", "keys", or "klavier"
- Reference audio: filename contains "mix"
- Videos: `.mp4` or `.mov` files

## Branch Structure

- `main` - v1.0-stable, production-safe
- `develop` - active development (current)

## Known Limitations

- Screenshots LUT differs from Adobe Premiere (needs refinement)
- macOS only (uses `say` command for TTS)
