# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PeakCut is a Python/PyQt6 desktop app for podcast post-production. It detects keyboard peaks (foot pedal markers) in audio recordings and exports numbered audio clips with timecodes. Used in production for "Hotel Matze" podcast.

## Folder Structure

```
App/
├── 1 Material/     ← User input (audio/video files)
├── 2 Export/       ← Output (MP3 + TXT + EDL)
├── 3 Intern/       ← Source code & dependencies
│   ├── src/
│   │   ├── gui/           ← PyQt6 GUI components
│   │   └── lib/           ← External libraries (LUT processor)
│   ├── docs/              ← Documentation
│   ├── assets/
│   ├── venv311/
│   └── requirements.txt
└── README.txt      ← User instructions
```

## Commands

```bash
# Run PeakCut (PyQt6 - aktiv)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main_pyqt.py"

# Run PeakCut (Tkinter - Legacy)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"

# Install dependencies
python3.11 -m venv "3 Intern/venv311"
source "3 Intern/venv311/bin/activate"
pip install -r "3 Intern/requirements.txt"
```

## Architecture

**Entry Points:**
- `main_pyqt.py` → PyQt6 GUI (aktiv)
- `main.py` → Tkinter GUI (Legacy)

**GUI Modules (src/gui/):**
- `main_window.py` - Hauptfenster mit allen Controls
- `apple_style.py` - macOS-inspired stylesheet
- `video_preview_peak.py` - Video Preview mit QMediaPlayer
- `peak_timeline.py` - Custom Timeline mit Peak-Markern

**Core Modules:**
- `peaks.py` - Peak detection, audio playback, navigation
- `sync.py` - Video-to-audio sync via cross-correlation
- `export.py` - MP3/TXT/EDL export with TTS numbers
- `config.py` - JSON configuration management
- `screenshots.py` - Extract frames from videos with LUT
- `status.py` - Observer pattern for UI updates
- `utils.py` - Shared paths and helpers

**State:** Global variables in `peaks.py` with getter functions for cross-module access.

## Key Features

1. **TTS Numbers** - macOS `say -v Anna` generates spoken numbers (no 49-limit)
2. **Auto Sync** - Detects video offsets via audio correlation
3. **Combined Export** - MP3 + TXT + EDL with all timecodes
4. **Video Preview** - QMediaPlayer with peak timeline markers
5. **Screenshots** - Random frames per video with Kodak LUT (experimental)

## File Naming Conventions

- Keyboard audio: filename contains "keyboard", "keys", or "klavier"
- Reference audio: filename contains "mix"
- Videos: `.mp4` or `.mov` files

## Git Workflow

**WICHTIG: Vor jeder Session prüfen:**
```bash
git branch      # Welcher Branch?
git status      # Alles committed?
```

**Branch-Struktur:**
- `main` - Stable releases, production-safe
- `develop` - Aktive Entwicklung (hier arbeiten)

**Regeln:**
- Kleine Features: direkt auf `develop`
- Große Features (>1 Tag): neuer `feature/name` Branch
- Nach jeder Änderung: committen
- Details: siehe `docs/WORKFLOW.md`

## Keyboard Shortcuts (PyQt6)

| Taste | Aktion |
|-------|--------|
| Space | Play/Stop |
| → | Next Peak |
| ← | Previous Peak |
| S | Switch Mode |
| I/Delete | Ignore Peak |
| E | Export (MP3+TXT) |
| D | EDL Export |

## Known Limitations

- Screenshots LUT differs from Adobe Premiere (needs refinement)
- macOS only (uses `say` command for TTS)
