# CLAUDE.md

Das zentrale Entwickler-Dokument für PeakCut. Enthält alles was Claude Code (und Entwickler) wissen müssen.

---

## Project Overview

PeakCut ist eine Python/PyQt6 Desktop-App für Podcast-Nachbearbeitung. Sie erkennt Keyboard-Peaks (Fußpedal-Marker) in Audioaufnahmen und exportiert nummerierte Clips mit Timecodes.

**Produktiv im Einsatz für:** [Hotel Matze](https://mitvergnuegen.com/hotelmatze/) Podcast

---

## Folder Structure

```
App/
├── 1 Material/          ← User Input (Audio/Video)
├── 2 Export/            ← Output (MP3 + TXT + XML + Screenshots)
├── 3 Intern/            ← Source Code
│   ├── src/
│   │   ├── core/        ← Core Logic (Klassen-basiert)
│   │   ├── gui/         ← PyQt6 GUI Components
│   │   └── lib/         ← External Libraries
│   ├── assets/
│   │   ├── pictures/    ← Icons, Logos
│   │   └── zahlen/      ← TTS Fallback MP3s
│   ├── luts/            ← LUT Library (.cube Dateien)
│   ├── config.json      ← User Settings
│   ├── requirements.txt
│   ├── venv311/         ← Virtual Environment
│   └── CLAUDE.md        ← Diese Datei
└── README.txt           ← User Quick Start
```

---

## Commands

```bash
cd /Users/max/Desktop/PeakCut/App

# App starten
"./3 Intern/venv311/bin/python" "./3 Intern/src/main_pyqt.py"

# Dependencies installieren
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"

# Virtual Environment neu erstellen
rm -rf "./3 Intern/venv311"
~/.pyenv/versions/3.11.*/bin/python3 -m venv "./3 Intern/venv311"
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

---

## Architecture

### Source Files

```
src/
├── main_pyqt.py              # PyQt6 Entry Point
├── core/                      # Core Logic (Class-basiert)
│   ├── project.py             # PeakCutProject - Datei-Abstraktion
│   ├── session.py             # PeakCutSession - State Management + Qt Signals
│   ├── exporters.py           # MP3/XML/TXT Exporter (Pluggable Pipeline)
│   ├── audio.py               # Peak Detection + Audio Playback
│   └── sync.py                # Video-Audio Sync (Cross-Correlation)
├── gui/
│   ├── main_window.py         # Hauptfenster + AnalysisWorker
│   ├── apple_style.py         # macOS Stylesheet
│   ├── video_preview_peak.py  # Video mit QMediaPlayer + LUT
│   └── peak_timeline.py       # Timeline mit Peak-Markern
├── lib/
│   └── lut_processor.py       # LUT für Color Grading
├── config.py                  # JSON Config Management
└── utils.py                   # Pfade, Hilfsfunktionen
```

### Core Classes

```
PeakCutProject (project.py)
  - material_dir, export_dir
  - keyboard_track, mic_tracks, videos
  - scan(), set_files(), get_reference_track()

PeakCutSession (session.py) : QObject
  - Signals: peaks_found, peak_changed, mode_changed, peak_ignored, status_update
  - State: peaks, current_peak, ignored_peaks, mode, keyboard_audio, mic_audios, video_offsets
  - Methods: analyze(), next_peak(), prev_peak(), play_current(), switch_mode(), ignore_peak()

Exporters (exporters.py)
  - BaseExporter (ABC) → export(session) -> str
  - MP3Exporter: Nummerierte Clips mit TTS
  - XMLExporter: FCP XML für Premiere/FinalCut/DaVinci
  - TXTExporter: Timecode-Textdatei
```

### Module Dependencies

```
main_pyqt.py
  └── gui/main_window.py
        ├── gui/apple_style.py
        ├── gui/video_preview_peak.py
        │     ├── gui/peak_timeline.py
        │     └── core/exporters.py (extract_guest_name)
        ├── core/project.py
        ├── core/session.py
        │     ├── core/audio.py
        │     └── core/sync.py
        ├── core/exporters.py
        ├── config.py
        └── utils.py
```

### State Management

Aller State lebt in `PeakCutSession`. Kein globaler State mehr.

| Klasse | State |
|--------|-------|
| `PeakCutSession` | `peaks`, `current_peak`, `ignored_peaks`, `mode`, `keyboard_audio`, `mic_audios`, `video_offsets` |
| `config.py` | `_config` (JSON-basiert, lazy-loaded) |

---

## Data Flow

1. **User wählt Dateien** → `PeakCutProject.set_files(keyboard, mics, videos)`
2. **User klickt "Analyze"** → `PeakCutSession.analyze()` im AnalysisWorker (QThread)
   - Sync: `core.sync.sync_videos()` → video_offsets
   - Peaks: `core.audio.detect_peaks()` → peaks list
   - Audio: Lädt AudioSegments in Session
3. **Navigation**: `session.next_peak()`, `session.prev_peak()`, `session.play_current()`
4. **Export**: `MP3Exporter/XMLExporter/TXTExporter.export(session)`
5. **Screenshot**: `video_preview_peak.capture_screenshot()` (ffmpeg + LUT)

Status-Updates laufen über `session.status_update` Signal (Qt, thread-safe).

---

## Configuration

`config.json`:
```json
{
  "threshold_factor": 0.4,
  "min_gap_ms": 15000,
  "preview_duration_ms": 1000,
  "context_duration_ms": 15000,
  "fps": 25,
  "tts_voice": "Anna",
  "lut_path": ""
}
```

| Key | Default | Beschreibung |
|-----|---------|--------------|
| `threshold_factor` | 0.4 | Peak-Erkennung Schwellwert |
| `min_gap_ms` | 15000 | Minimaler Abstand zwischen Peaks |
| `preview_duration_ms` | 1000 | Keyboard-Mode Preview Länge |
| `context_duration_ms` | 15000 | Mic-Mode Kontext (±15s) |
| `fps` | 25 | Framerate für Timecode-Berechnung |
| `tts_voice` | "Anna" | macOS TTS Stimme |
| `lut_path` | "" | Dateiname des aktiven LUTs (aus `luts/` Library) |

---

## Keyboard Shortcuts

| Taste | Aktion |
|-------|--------|
| `→` | Next Peak |
| `←` | Previous Peak |

Alle anderen Aktionen (Play, Stop, Export, Screenshot, Switch, Ignore) sind nur über Buttons erreichbar.

---

## File Naming Conventions

- **Keyboard Audio**: Dateiname enthält "keyboard", "keys", oder "klavier"
- **Reference Audio**: Dateiname enthält "mix"
- **Videos**: `.mp4` oder `.mov`

---

## Git Workflow

### Branch-Struktur
```
main     ← Stable Releases
develop  ← Aktive Entwicklung (hier arbeiten)
```

### Regeln
- **Kleine Features**: Direkt auf `develop`
- **Große Features** (>1 Tag): Neuer `feature/name` Branch
- **Nach jeder Änderung**: Committen!
- **Commit-Message**: Kurz, prägnant, mit Co-Author

---

## TODO

### Aktuell offen (Priorität)
- [ ] **Multiprocessing für Video-Sync** - Sync ist langsam bei großen Dateien
- [ ] EDL/XML in Premiere testen - Format validieren
- [ ] Performance-Probleme untersuchen (App läuft "unruhig")

### Mittelfristig (V2)
- [ ] Smart Scan: Ordner wählen, leere Spuren erkennen
- [ ] Clip Editor: In/Out Points anpassen
- [ ] Profile System
- [ ] Batch Processing (Session pro Projekt)
- [ ] Undo/Redo (Session-basiert)

### Langfristig (V4)
- [ ] Electron App + Python Engine + Cloud Backend
- [ ] Machine Learning für automatische Clip-Vorhersage
- [ ] Hardware: Physischer Marker-Button

---

## Changelog

### v2.0.0-dev (2026-02-05)
- **Core Refactoring** - Kompletter Umbau von Global State zu Class-basiertem Design
  - `PeakCutProject`: Datei-Abstraktion (keyboard_track, mic_tracks, videos)
  - `PeakCutSession`: State Management mit Qt Signals (peaks, navigation, playback)
  - `Exporters`: Pluggable Export Pipeline (MP3Exporter, XMLExporter, TXTExporter)
  - `core/audio.py`: Standalone Peak Detection + Playback
  - `core/sync.py`: Standalone Video-Audio Sync
- **Alte Module gelöscht** - peaks.py, sync.py, export.py, status.py, gui.py, main.py
- **Kein globaler State mehr** - Aller State in PeakCutSession
- **Status via Qt Signals** - session.status_update statt status.py Callback
- **AnalysisWorker vereinfacht** - Nimmt Session, ruft session.analyze()
- **Bereit für** Clip Editor, Batch Processing, Undo/Redo, Tests

### v1.5.0-dev (2026-02-05)
- **4K Video Preview** - Volle Auflösung ohne LUT, Retina-DPR-Skalierung mit LUT
- **Threading für Analyse** - AnalysisWorker (QThread) statt blockierendem Main-Thread
- **Peak-Controls versteckt** - Erst nach Analyse sichtbar
- **Kamera-Namen für Screenshots** - Counter-basiert ("Matze 1.jpg", "Matze 2.jpg")
- **Screenshots als JPG** - Quality 95
- **Single-Instance Lock** - fcntl

### v1.4.0-dev (2026-02-05)
- **Screenshot mit LUT** - ffmpeg + LUTProcessor
- **LUT Library** - Import-Dialog, Dropdown
- **Keyboard Shortcuts entfernt** - Nur noch Pfeiltasten

### v1.3.0-dev (2025-02-04)
- **FCP XML Export** - Für Premiere Pro/Final Cut/DaVinci
- **PyQt6 GUI** - Komplettes Rewrite von Tkinter
- **Video Preview** - QMediaPlayer mit Peak-Timeline
- **Flexible File Import** - Multi-Select, Auto-Detection

### v1.2.0 (2025-02-02)
- Config System (`config.json`)

### v1.1.0 (2025-02-01)
- Screenshots Feature mit Kodak LUT

### v1.0-stable (2025-01-31)
- TTS für unbegrenzte Peak-Nummern
- Portable Pfade

---

## Known Limitations

- **macOS only** - Nutzt `say` Command für TTS
- **No Tests** - Zero Test Coverage

---

*Zuletzt aktualisiert: 2026-02-05*
