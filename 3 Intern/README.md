# PeakCut V3

**Automated clip extraction tool for podcast post-production.**

During recording, the host marks good moments with a keyboard (foot pedal). PeakCut detects these peaks and exports numbered audio clips with timecodes.

Used in production for [Hotel Matze](https://mitvergnuegen.com/hotelmatze/) podcast.

---

## Features

- **Peak Detection** - Automatically finds keyboard markers in audio
- **TTS Numbering** - Spoken numbers via macOS TTS (unlimited, no MP3 limit)
- **Video Sync** - Calculates video-to-audio offsets via cross-correlation
- **Combined Export** - MP3 with spoken numbers + TXT with all timecodes
- **Screenshots** - Extract random frames from videos with film LUT (experimental)
- **Portable** - Works from any directory, no hardcoded paths

## Requirements

- macOS (uses native `say` command for TTS)
- Python 3.11
- ~500MB disk space for dependencies

## Installation

```bash
cd ~/Desktop/PeakCut/App
python3.11 -m venv "3 Intern/venv311"
source "3 Intern/venv311/bin/activate"
pip install -r "3 Intern/requirements.txt"
```

## Usage

### 1. Prepare Files
Put your files in `1 Material/`:
- Audio files (`.wav`) - one must contain "keyboard", "keys", or "klavier" in the name
- Reference mix (`.wav`) - must contain "mix" in the name
- Videos (`.mp4`, `.mov`) - optional, for sync & screenshots

### 2. Run PeakCut
```bash
source "3 Intern/venv311/bin/activate"
python "3 Intern/src/main.py"
```

### 3. Workflow
1. Click **Analyze** - detects peaks (and syncs videos if present)
2. Use **Play/Next/Back** - review detected peaks
3. Use **Ignore** - skip false positives
4. Click **Export** - creates MP3 + TXT in `2 Export/`
5. Click **Screenshots** - extracts video frames (optional)

## Output

```
2 Export/
├── Keyboardstellen - [Guest Name].mp3   # Numbered audio clips
├── Keyboardstellen - [Guest Name].txt   # Timecodes + video offsets
└── Screenshots/                          # Video frames (if extracted)
    ├── Kamera 1/
    └── Kamera 2/
```

## Project Structure

```
App/
├── 1 Material/     # Input files (gitignored)
├── 2 Export/       # Output files (gitignored)
├── 3 Intern/       # Source code
│   ├── src/        # Python modules
│   ├── assets/     # Logo, fallback MP3s
│   └── venv311/    # Virtual environment (gitignored)
└── README.txt      # Quick start for users
```

## Development

```bash
# Work with Claude Code
cd ~/Desktop/PeakCut/App && claude

# Branch structure
main    - stable, production-safe
develop - active development
```

## Tech Stack

- **GUI:** Tkinter
- **Audio:** pydub, soundfile, simpleaudio
- **Video:** moviepy
- **Analysis:** numpy, scipy
- **TTS:** macOS `say` command

---

Built with [Claude Code](https://claude.ai/code)
