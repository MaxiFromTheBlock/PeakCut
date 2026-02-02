# Architecture

## File Overview

| File | Purpose |
|------|---------|
| `main.py` | Entry point, launches GUI |
| `gui.py` | Tkinter UI, button handlers, status display |
| `peaks.py` | Peak detection, audio playback, navigation state |
| `sync.py` | Video-to-audio sync via cross-correlation |
| `export.py` | MP3 export with TTS numbers, timecode TXT generation |
| `screenshots.py` | Extract random frames from videos with optional LUT |
| `status.py` | Observer pattern for UI status updates |
| `utils.py` | Shared paths (APP_DIR, MATERIAL_DIR, etc.) and helpers |

## Dependencies (Imports)

```
main.py
  └── gui.py
        ├── utils.py (ASSETS_DIR)
        ├── sync.py (run_sync)
        ├── peaks.py (run_peak_analysis, play functions, getters)
        ├── export.py (run_export)
        ├── screenshots.py (extract_screenshots)
        └── status.py (set_callback)

peaks.py
  ├── status.py (update)
  └── utils.py (MATERIAL_DIR, EXPORT_DIR)

sync.py
  ├── status.py (update)
  └── utils.py (MATERIAL_DIR, EXPORT_DIR, TEMP_DIR)

export.py
  ├── status.py (update)
  ├── utils.py (format_peak_time, MATERIAL_DIR, EXPORT_DIR, TEMP_DIR, ASSETS_DIR)
  ├── peaks.py (get_peaks, get_mode, get_keyboard_audio, get_mic_audios, get_ignored_peaks)
  └── sync.py (get_video_offsets)

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
   - Detects peaks above threshold (40% of max amplitude)
   - Filters peaks with minimum 15s gap
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

## Technical Debt

1. **Global state everywhere** - peaks.py, sync.py, gui.py all use module-level globals instead of classes
2. **No error recovery** - If peak analysis fails midway, state is partially set
3. **Hardcoded LUT path** - screenshots.py has absolute path to Adobe Premiere LUT
4. **No config file** - Parameters (threshold, gap, preview duration) are hardcoded
5. **Mixed language** - Some status messages are German, some English
6. **No tests** - Zero test coverage
7. **Sync always runs** - Even when no videos present (silent skip, but still called)
8. **Screenshots LUT differs from Premiere** - Uses nearest-neighbor instead of trilinear interpolation
