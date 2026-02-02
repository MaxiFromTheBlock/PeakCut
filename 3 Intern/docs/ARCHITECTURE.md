# Architecture

## File Structure

```
3 Intern/src/
├── main.py              # Tkinter Entry Point (Legacy)
├── main_pyqt.py         # PyQt6 Entry Point (New)
│
├── gui/                 # PyQt6 GUI Components
│   ├── __init__.py
│   ├── main_window.py   # Main application window
│   ├── apple_style.py   # macOS-inspired stylesheet
│   └── video_preview.py # Video preview widget (not yet integrated)
│
├── lib/                 # External Libraries
│   ├── __init__.py
│   └── lut_processor.py # LUT processing for color grading
│
├── peaks.py             # Peak detection, audio playback, navigation
├── sync.py              # Video-to-audio sync via cross-correlation
├── export.py            # MP3 + TXT export (always uses mic audio)
├── screenshots.py       # Frame extraction with optional LUT
├── status.py            # Observer pattern for UI updates
├── utils.py             # Shared paths and helpers
├── config.py            # JSON configuration management
└── gui.py               # Tkinter UI (Legacy)
```

## Entry Points

| File | Framework | Status |
|------|-----------|--------|
| `main_pyqt.py` | PyQt6 | **Active development** |
| `main.py` | Tkinter | Legacy (backup) |

## Core Modules

| File | Purpose |
|------|---------|
| `peaks.py` | Peak detection, audio playback, navigation state |
| `sync.py` | Video-to-audio sync via cross-correlation |
| `export.py` | MP3 export with TTS numbers, timecode TXT (always uses mic audio) |
| `screenshots.py` | Extract random frames from videos with optional LUT |
| `status.py` | Observer pattern for UI status updates |
| `utils.py` | Shared paths (APP_DIR, MATERIAL_DIR, etc.) and helpers |
| `config.py` | Configuration management, loads/saves config.json |

## Dependencies (Imports)

### PyQt6 Version (main_pyqt.py)
```
main_pyqt.py
  └── gui/main_window.py
        ├── gui/apple_style.py (stylesheet, colors)
        ├── utils.py (MATERIAL_DIR, EXPORT_DIR)
        ├── sync.py (run_sync)
        ├── peaks.py (run_peak_analysis, playback functions, getters)
        ├── export.py (run_export)
        └── status.py (set_callback)
```

### Tkinter Version (main.py) - Legacy
```
main.py
  └── gui.py
        ├── utils.py (ASSETS_DIR)
        ├── sync.py (run_sync)
        ├── peaks.py (run_peak_analysis, play functions, getters)
        ├── export.py (run_export)
        ├── screenshots.py (extract_screenshots)
        └── status.py (set_callback)
```

### Core Modules
```
config.py
  └── (no internal dependencies, uses json and os)

peaks.py
  ├── config (threshold_factor, min_gap_ms, preview_duration_ms, context_duration_ms)
  ├── status.py (update)
  └── utils.py (MATERIAL_DIR, EXPORT_DIR)

sync.py
  ├── status.py (update)
  └── utils.py (MATERIAL_DIR, EXPORT_DIR, TEMP_DIR)

export.py
  ├── config (tts_voice, context_duration_ms)
  ├── status.py (update)
  ├── utils.py (format_peak_time, MATERIAL_DIR, EXPORT_DIR, TEMP_DIR, ASSETS_DIR)
  ├── peaks.py (get_peaks, get_mic_audios, get_ignored_peaks)
  └── sync.py (get_video_offsets)

utils.py
  └── config (fps)

screenshots.py
  ├── status.py (update)
  └── utils.py (MATERIAL_DIR, EXPORT_DIR)
```

## Data Flow: Peak Analysis

1. **User clicks "Analyze"** (`gui.py:on_analyze`)
2. **Sync runs first** (`sync.py:run_sync`)
   - Finds video files (.mp4, .mov) in MATERIAL_DIR
   - Extracts audio from each video to TEMP_DIR
   - Loads reference audio (file with "mix" in name)
   - Calculates offset via scipy cross-correlation
   - Stores offsets in `_video_offsets` global
   - Cleans up temp files
3. **Peak analysis runs** (`peaks.py:run_peak_analysis`)
   - Finds keyboard audio (file with "keyboard", "keys", or "klavier" in name)
   - Loads as AudioSegment via pydub
   - Converts to numpy array
   - Detects peaks above threshold (config: `threshold_factor`)
   - Filters peaks with minimum gap (config: `min_gap_ms`)
   - Stores in `_peaks` global list
   - Loads mic audios for alternative playback mode
4. **User navigates peaks** (Play/Next/Back buttons)
   - `play_current_peak()` extracts segment around peak time
   - Keyboard mode: 1s preview from peak
   - Mic mode: 15s context before and after peak
   - Plays via simpleaudio

## Global State

### peaks.py
- `_peaks: list[int]` - Peak times in milliseconds
- `_current_peak: int` - Current navigation index
- `_keyboard_audio: AudioSegment` - Loaded keyboard audio
- `_mic_audios: list[AudioSegment]` - Loaded mic tracks
- `_mode: str` - "keyboard" or "mic"
- `_ignored_peaks: set[int]` - Peak indices marked as ignored

### sync.py
- `_video_offsets: list[tuple]` - (filename, timecode) pairs

### gui.py
- `status_text: ScrolledText` - Status display widget
- `is_playing: bool` - Playback state
- `play_button: Button` - Reference for text toggle

### status.py
- `_callback: function` - UI update callback (default: print)

### config.py
- `_config: dict` - Loaded configuration values

## Configuration

Settings are stored in `3 Intern/config.json` and loaded via `config.py`:

| Key | Default | Used in |
|-----|---------|---------|
| `threshold_factor` | 0.4 | peaks.py |
| `min_gap_ms` | 15000 | peaks.py |
| `preview_duration_ms` | 1000 | peaks.py |
| `context_duration_ms` | 15000 | peaks.py, export.py |
| `fps` | 25 | utils.py |
| `tts_voice` | "Anna" | export.py |

## Export Behavior

**Important:** Export always uses mic audio tracks, regardless of the UI playback mode.

- Keyboard mode in UI = quick preview of peak position only
- Export = always mic tracks with context (±15s around peak)

This separation ensures the final export contains the actual interview audio, not the keyboard trigger sounds.

## Technical Debt

1. **Global state everywhere** - peaks.py, sync.py, gui.py all use module-level globals instead of classes
2. **No error recovery** - If peak analysis fails midway, state is partially set
3. **Hardcoded LUT path** - screenshots.py has absolute path to Adobe Premiere LUT
4. **Mixed language** - Some status messages are German, some English
5. **No tests** - Zero test coverage
6. **Sync always runs** - Even when no videos present (silent skip, but still called)
7. **Screenshots LUT differs from Premiere** - Uses nearest-neighbor instead of trilinear interpolation
