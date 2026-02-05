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

# App starten (PyQt6)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main_pyqt.py"

# App starten (Tkinter Legacy)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"

# Dependencies installieren
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"

# Virtual Environment neu erstellen
rm -rf "./3 Intern/venv311"
~/.pyenv/versions/3.11.*/bin/python3 -m venv "./3 Intern/venv311"
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

---

## Architecture

### Entry Points

| File | Framework | Status |
|------|-----------|--------|
| `main_pyqt.py` | PyQt6 | **Aktiv** |
| `main.py` | Tkinter | Legacy |

### Source Files

```
src/
├── main_pyqt.py         # PyQt6 Entry Point
├── main.py              # Tkinter Entry Point (Legacy)
├── gui/
│   ├── main_window.py   # Hauptfenster
│   ├── apple_style.py   # macOS Stylesheet
│   ├── video_preview_peak.py  # Video mit QMediaPlayer
│   └── peak_timeline.py # Timeline mit Peak-Markern
├── lib/
│   └── lut_processor.py # LUT für Color Grading
├── peaks.py             # Peak Detection, Playback, Navigation
├── sync.py              # Video-Audio Sync (Cross-Correlation)
├── export.py            # MP3 + TXT + XML Export
├── config.py            # JSON Config Management
├── status.py            # Observer Pattern für UI
├── utils.py             # Pfade, Hilfsfunktionen
└── gui.py               # Tkinter UI (Legacy)
```

### Module Dependencies

```
main_pyqt.py
  └── gui/main_window.py
        ├── gui/apple_style.py
        ├── gui/video_preview_peak.py
        │     └── gui/peak_timeline.py
        ├── peaks.py
        ├── sync.py
        ├── export.py
        ├── status.py
        └── utils.py
```

### Global State

| Module | Variables |
|--------|-----------|
| `peaks.py` | `_peaks`, `_current_peak`, `_keyboard_audio`, `_mic_audios`, `_mode`, `_ignored_peaks` |
| `sync.py` | `_video_offsets` |
| `config.py` | `_config` |
| `status.py` | `_callback` |

---

## Data Flow

1. **User klickt "Analyze"**
2. **Sync** (`sync.py`): Extrahiert Audio aus Videos, berechnet Offsets via Cross-Correlation
3. **Peak Analysis** (`peaks.py`): Findet Peaks über Threshold, filtert mit min_gap
4. **Navigation**: User navigiert durch Peaks (Play/Next/Back)
5. **Export**: MP3 mit TTS-Nummern + TXT mit Timecodes + FCP XML für Premiere
6. **Screenshot**: Frame aus Video + LUT Color Grading → PNG in Export/Screenshots/

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

### Vor jeder Session
```bash
git branch      # Welcher Branch?
git status      # Alles committed?
```

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

```bash
git commit -m "$(cat <<'EOF'
Add feature X

- Detail 1
- Detail 2

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## TODO

### Aktuell offen (Priorität)
- [ ] **Threading für UI** - Analyse blockiert UI, Rainbow Wheel erscheint
- [ ] **Multiprocessing für Video-Sync** - Sync ist langsam bei großen Dateien
- [ ] EDL in Premiere testen - Format validieren
- [ ] Performance-Probleme untersuchen (App läuft "unruhig")

### Später
- [ ] Progress Indicator mit Animation

### Mittelfristig (V2)
- [ ] Smart Scan: Ordner wählen, leere Spuren erkennen
- [ ] Clip Editor: In/Out Points anpassen
- [ ] Profile System

### Langfristig (V4)
- [ ] Electron App + Python Engine + Cloud Backend
- [ ] Machine Learning für automatische Clip-Vorhersage
- [ ] Hardware: Physischer Marker-Button

---

## Changelog

### v1.4.0-dev (2026-02-05)
- **Screenshot mit LUT** - Frame-Capture aus Video-Preview mit Color Grading
  - ffmpeg für Frame-Extraktion, LUTProcessor für trilineare Interpolation
  - Speichert nach Export/Screenshots/ mit Timecode im Dateinamen
- **LUT Library** - PeakCut kopiert importierte LUTs nach `3 Intern/luts/`
  - Dropdown zeigt alle LUTs aus der Library
  - Original-Datei kann nach Import gelöscht werden
- **Screenshot Button** - Sichtbarer Button in der Controls-Leiste
- **Keyboard Shortcuts entfernt** - Nur noch Pfeiltasten (←/→) für Peak-Navigation
- **XML Sequence Name** - Heißt jetzt einfach "PeakCut" statt "PeakCut - Gastname"
- **screenshots.py gelöscht** - Alte Logik mit nearest-neighbor LUT und MoviePy entfernt

### v1.3.0-dev (2025-02-04)
- **FCP XML Export** - Für Premiere Pro/Final Cut/DaVinci
  - Echte 30s Clips (±15s context_duration um jeden Peak)
  - Source IN/OUT = Position im Original-Material
  - Record IN/OUT = Position in der generierten Sequence
  - Wird automatisch bei Export erstellt (kein separater Button)
- **PyQt6 GUI** - Komplettes Rewrite von Tkinter
- **Video Preview** - QMediaPlayer mit Peak-Timeline
- **Flexible File Import** - Multi-Select, Auto-Detection
- **Docs Cleanup** - 10 MD-Dateien → 2 (CLAUDE.md + README.txt)

### v1.2.0 (2025-02-02)
- Config System (`config.json`)
- Export Bug Fix (verwendet immer Mic Audio)

### v1.1.0 (2025-02-01)
- Screenshots Feature mit Kodak LUT
- Folder Structure Reorganisation

### v1.0-stable (2025-01-31)
- TTS für unbegrenzte Peak-Nummern
- Portable Pfade

---

## Known Limitations

- **macOS only** - Nutzt `say` Command für TTS
- **Global State** - Kein Class-basiertes Design
- **No Tests** - Zero Test Coverage

---

---

## Session Notes (2026-02-05)

### Was wurde gemacht
1. ✅ Screenshot-Feature mit LUT (ffmpeg + LUTProcessor)
2. ✅ LUT Library - eigener `luts/` Ordner, Import-Dialog kopiert Dateien
3. ✅ LUT Dropdown zeigt alle LUTs aus Library
4. ✅ Screenshot-Button in Controls-Leiste
5. ✅ Keyboard Shortcuts entfernt (nur noch Pfeiltasten)
6. ✅ XML Sequence Name → "PeakCut"
7. ✅ screenshots.py gelöscht (alte Logik)
8. ✅ Doku aktualisiert

### Was noch offen ist
1. **Threading für UI** - Analyse blockiert UI, Rainbow Wheel
2. **Multiprocessing für Video-Sync** - Performance bei großen Dateien
3. **XML in Premiere testen** - Import prüfen

### Git Status
- Branch: `develop`

---

*Zuletzt aktualisiert: 2026-02-05*
