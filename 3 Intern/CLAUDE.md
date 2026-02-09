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
├── main_pyqt.py              # PyQt6 Entry Point (Single-Instance Lock via fcntl)
├── config.py                  # JSON Config Management (thread-safe, lazy-loaded)
├── utils.py                   # Path constants + shared helpers (parse_timecode_to_ms)
├── core/
│   ├── project.py             # PeakCutProject - Datei-Abstraktion
│   ├── session.py             # PeakCutSession - State Management + Qt Signals
│   ├── peak.py                # Peak Datenmodell (position_ms, in/out points, bounds)
│   ├── audio.py               # Peak Detection + Audio Playback + State Tracking (pydub + simpleaudio)
│   ├── sync.py                # Video-Audio Sync (Cross-Correlation)
│   ├── analysis_process.py    # Standalone subprocess for analysis (avoids MoviePy/Qt conflicts)
│   └── exporters.py           # MP3/XML/TXT Exporter (ffprobe for runtime media info)
├── gui/
│   ├── main_window.py         # Hauptfenster: 3-Page UI (Welcome → Analysis → Review)
│   ├── apple_style.py         # macOS Dark-Theme Stylesheet (COLORS dict, get_stylesheet())
│   └── video_preview_peak.py  # Video-Player: QMediaPlayer + LUT + Async Screenshots
└── lib/
    └── lut_processor.py       # LUT Trilinear Interpolation + Pre-computed 256³ Lookup (numpy)
```

### Core Classes

```
PeakCutProject (project.py)
  - material_dir, export_dir
  - keyboard_track, mic_tracks, videos
  - set_files(), get_reference_track()

PeakCutSession (session.py) : QObject
  - Signal: status_update
  - State: peaks, current_peak, mode, keyboard_audio, mic_audios, video_offsets
  - Methods: play_current(), switch_mode(), ignore_peak(), set_current_peak()
  - load_analysis_results(dict) — loads peaks + offsets from subprocess
  - load_audio_lazy() — deferred audio loading, sets duration bounds on peaks

Peak (peak.py)
  - position_ms (immutable), in/out_offset_ms, ignored
  - in_point_ms (property, clamped >= 0)
  - out_point_ms (property, clamped <= audio duration)
  - set_in_point(), set_out_point(), reset_offsets()

Exporters (exporters.py)
  - BaseExporter (ABC) → export(session) -> str
  - MP3Exporter: Nummerierte Clips mit TTS
  - XMLExporter: FCP XML für Premiere/FinalCut/DaVinci
  - TXTExporter: Timecode-Textdatei
  - _probe_video_info() / _probe_audio_info() — ffprobe für runtime Resolution/Samplerate

config.py
  - Thread-safe via threading.Lock
  - get(key), set_value(key, value), load(), save()

utils.py
  - Path constants: MATERIAL_DIR, EXPORT_DIR, TEMP_DIR, ASSETS_DIR, LUTS_DIR
  - parse_timecode_to_ms(tc_str, fps) — shared timecode parser
```

### Module Dependencies

```
main_pyqt.py
  └── gui/main_window.py
        ├── gui/apple_style.py        (COLORS dict, get_stylesheet())
        ├── gui/video_preview_peak.py  (PeakVideoPreview — Player + LUT + Screenshots)
        │     └── lib/lut_processor.py
        ├── core/project.py
        ├── core/session.py
        │     ├── core/peak.py
        │     └── core/audio.py
        ├── core/exporters.py
        ├── config.py
        └── utils.py
```

Analysis runs in a **separate subprocess** (`core/analysis_process.py`), spawned by `AnalysisWorker` in `main_window.py`. This avoids MoviePy/Qt conflicts and keeps the GUI responsive.

### State Management

Aller State lebt in `PeakCutSession`. Kein globaler State.

| Klasse | State |
|--------|-------|
| `PeakCutSession` | `peaks`, `current_peak`, `mode`, `keyboard_audio`, `mic_audios`, `video_offsets` |
| `config.py` | `_config` (JSON-basiert, lazy-loaded, thread-safe via `_lock`) |

---

## Data Flow

1. **User klickt "Import Files"** → Datei-Dialog, Dateien kategorisiert (keyboard/mics/videos)
2. **Falls Keyboard nicht auto-erkannt** → Dialog zur Auswahl
3. **Dateien nach `1 Material/` kopiert** (falls nötig)
4. **Analyse startet** → `AnalysisWorker` (QThread) spawnt `analysis_process.py` als Subprocess
   - Subprocess: `sync.sync_videos()` → video_offsets
   - Subprocess: `audio.detect_peaks()` → peaks list
   - Ergebnis als JSON über stdout zurück
5. **Ergebnisse geladen** → `session.load_analysis_results(dict)` → Peaks + Offsets
6. **Audio wird lazy geladen** bei erstem Playback → `session.load_audio_lazy()`
7. **Navigation**: `navigate_to_peak(index)` → Session + Video + UI aktualisiert
8. **Export**: `MP3Exporter/XMLExporter/TXTExporter.export(session)`

Status-Updates laufen über `session.status_update` Signal + stderr vom Subprocess.

---

## UI Design (3-Page Flow)

### Pages (QStackedWidget)

| Page | Index | Inhalt |
|------|-------|--------|
| **Welcome** | 0 | Zentrierter "PeakCut" Titel + "Import Files" Button |
| **Analysis** | 1 | Analyse-Status + Fortschritt (wartet auf Subprocess) |
| **Review** | 2 | Video-Player + Controls + Navigation + Export |

### Review Page Layout (von oben nach unten)

```
┌──────────────────────────────────────────────────────┐
│ Kamera:[▼ name]  LUT:[▼]                            │ ← Top-Bar
│ ┌──────────────────────────────────────────────────┐ │
│ │                                                  │ │
│ │              VIDEO PLAYER                        │ │
│ │                                                  │ │
│ └──────────────────────────────────────────────────┘ │
│ [◀][Play/Stop][▶] | [Ignore] [Mode] Peak 3/47 [Screenshot] [Export] │
│                Statusbar                             │ ← Statusbar
└──────────────────────────────────────────────────────┘
```

### Video-Player (video_preview_peak.py)

- **QMediaPlayer** + **QVideoSink** für Frame-Interception
- **LUTWorker** (QThread): Verarbeitet Frames off-main-thread mit LUT
- **ScreenshotWorker** (QThread): Async Screenshots via ffmpeg + PIL + LUT
- **Deferred Play**: `play_from(in_ms, out_ms)` — wartet auf Video-Load
- **Clip-Playback**: Stoppt automatisch am Out-Point
- Kein eigenes UI — nur `QLabel` für Video-Display

### Kamera-Namen

- `camera_combo` — Kamera-Wähler (Dropdown)
- Default-Name: Dateiname ohne Extension (z.B. "MV_20260126_7798" für "MV_20260126_7798.MP4")
- Screenshots nutzen den Kamera-Namen: "{name} 1.jpg", "{name} 2.jpg"

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

| Taste | Aktion | Kontext |
|-------|--------|---------|
| `→` | Next Peak | Review-Page |
| `←` | Previous Peak | Review-Page |
| `Space` | Play / Stop | Review-Page |
| `I` | Ignore Peak | Review-Page |
| `S` | Screenshot | Review-Page |

Shortcuts sind nur auf der Review-Page aktiv (Page Index 2).

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

### V3 Vision — Modulare Production Suite

PeakCut entwickelt sich von einem Peak-Detection-Tool zu einer modularen Production Suite.
Die Welcome-Page wird zum **Hub**, von dem aus einzelne Module gestartet werden.
Alle Module teilen sich ein gemeinsames Projekt (Dateien, Offsets, Config).

```
┌─────────────────────────────────────┐
│           PEAKCUT HUB               │
│                                     │
│  [Smart Scan]  → Projekt erstellen  │
│  [Create Mix]  → Mix aus Spuren     │
│  [Peaks]       → Peak Detection     │
│  [Screenshots] → Frame Export       │
└─────────────────────────────────────┘
         ↑ alle teilen sich ↑
      ein gemeinsames Projekt
      (Dateien, Offsets, Config)
```

#### Module

| Modul | Beschreibung | Status |
|-------|-------------|--------|
| **Smart Scan** | Ordner analysieren, Dateien automatisch erkennen/zuordnen (Keyboard, Mics, Videos, Reference/Mix). Unabhängig von Namenskonventionen. Ersetzt den aktuellen manuellen Import-Flow. | Konzept |
| **Create Mix** | Mix aus erkannten Spuren erstellen. Details noch offen: Einfaches Zusammenlegen? Lautstärke-Anpassung? Stereo-Mix? | Konzept |
| **Peaks** | Peak Detection + Review + Export. Existiert bereits als Kern-Feature. | Vorhanden |
| **Screenshots** | Eigene Page mit Video-Scrubbing (Timeline/Slider), Kamera-Benennung (editierbar), Frame-Export mit LUT. Unabhängig von Peaks navigierbar. | Teilweise (Button vorhanden, eigene Page fehlt) |

#### Offene Architektur-Fragen

1. **Smart Scan als Einstiegspunkt?** — Muss man immer erst scannen, bevor andere Module verfügbar sind? Oder kann man auch direkt Dateien reinwerfen (wie jetzt)?
2. **Create Mix — Was genau?** — Alle Mic-Spuren + Keyboard zu einem Stereo-Mix? Mit Lautstärke-Kontrolle? Oder simples Zusammenlegen?
3. **Modul-Abhängigkeiten** — Welche Module brauchen welche Vorbedingungen? (z.B. Screenshots brauchen Video-Sync, Peaks brauchen Audio-Analyse)
4. **Shared State** — Wie teilen sich Module den Projekt-State? Erweiterte `PeakCutSession`? Oder neues `Project`-Objekt als zentrale Datenschicht?

#### Umsetzungsreihenfolge (Vorschlag)

1. Smart Scan (Fundament für alles)
2. Create Mix
3. Peaks (Refactor: eigene Page statt linearer Flow)
4. Screenshots (eigene Page mit Video-Scrubbing)

### Offen (aktuelles Release)
- [ ] **Multiprocessing für Video-Sync** — Sync ist langsam bei großen Dateien
- [ ] EDL/XML in Premiere testen — Format validieren
- [ ] Undo/Redo für Clip-Editing
- [ ] Kamera-Namen editierbar — Camera-Combo editierbar machen
- [ ] Test Coverage aufbauen

### Langfristig (V4)
- [ ] Electron App + Python Engine + Cloud Backend
- [ ] Machine Learning für automatische Clip-Vorhersage
- [ ] Hardware: Physischer Marker-Button

---

## Changelog

### v2.3.0 (2026-02-09) — Play/Stop Toggle, Screenshot Button, Toolbar Redesign

- **Play/Stop Toggle**: Play-Button wechselt zu "■ Stop" während Playback, automatisch zurück bei Ende
- **Playback State Tracking**: `audio.py` trackt `_current_playback`, neue `is_playing()` Funktion
- **QTimer Polling** (200ms): Erkennt wenn Playback natürlich endet, resettet Button-State
- **Screenshot Button**: Async Screenshots via ffmpeg + LUT direkt aus der Review-Page
- **Keyboard Shortcut `S`**: Screenshot auf der Review-Page
- **Toolbar Redesign**: `[◀][Play/Stop][▶] | [Ignorieren] [Mode] Peak X/Y [Screenshot] [Export]`
- **Mode-Button**: Zeigt "Mode" statt "KB"/"MIC", aktueller Modus in Statusbar

### v2.2.0-dev (2026-02-09) — Health Check & Stabilisierung

**Gelöschte Dateien:**
- `gui/video_preview.py` (broken imports, nie benutzt)
- `gui/peak_timeline.py` (513 Zeilen, nie importiert)
- `test_pyqt.py` (leftover Test)

**Kritische Bugfixes:**
- Lock-File: `fcntl` File-Handle wird jetzt in Module-Level `_lock_fp` gespeichert (verhindert GC)
- Config: Thread-Safety via `threading.Lock`, `set()` → `set_value()` (kein Built-in Shadowing)
- Peak Bounds: `out_point_ms` wird jetzt auf Audio-Dauer geclamped (`_duration_ms`)

**Dead Code Entfernt:**
- session.py: `analyze()`, `next_peak()`, `prev_peak()`, `adjust_clip()`, `reset_clip()`, `get_mix_audio()`, 5 unused Signals
- project.py: `scan()` Methode
- apple_style.py: `get_video_preview_style()`, `get_frame_thumbnail_style()`
- lut_processor.py: `apply_to_pil_image()`, `get_lut_name()`, `clear()`, PIL Import
- main_window.py: Unused Imports (QProgressBar, get_stylesheet)

**Code-Konsolidierung:**
- `parse_timecode_to_ms()` aus session.py + exporters.py → shared in `utils.py`
- Inline Path-Berechnungen → `TEMP_DIR`, `ASSETS_DIR` Konstanten aus `utils.py`
- exporters.py: `_probe_video_info()` + `_probe_audio_info()` via ffprobe (statt hardcoded 3840x2160 / 48000)
- Magic Number 50ms → benannte Konstante `_FIRST_FRAME_DELAY_MS = 100`

### v2.1.0-dev (2026-02-06) — Radikale Vereinfachung

- **3-Page UI** — Welcome → Analysis → Review (statt 2-Phasen Workspace)
- **Analyse als Subprocess** — `analysis_process.py` statt `session.analyze()` im QThread
- **Clip-Info Panel** — In/Out/Duration Labels
- **Keyboard Shortcuts** — →, ←, Space, I
- Siehe `DEV_NOTES_2026-02-06.md` für Debug-Session Details

### v2.0.0-dev (2026-02-05) — Core Refactoring

- Kompletter Umbau von Global State zu Class-basiertem Design
- `PeakCutProject`, `PeakCutSession`, `Exporters`, `core/audio.py`, `core/sync.py`
- Kein globaler State mehr — aller State in PeakCutSession
- Status via Qt Signals

### v1.5.0-dev (2026-02-05)
- 4K Video Preview, Threading für Analyse, Single-Instance Lock

### v1.4.0-dev (2026-02-05)
- Screenshot mit LUT (ffmpeg + LUTProcessor), LUT Library

### v1.3.0-dev (2025-02-04)
- FCP XML Export, PyQt6 GUI (Rewrite von Tkinter), Video Preview

### v1.2.0 (2025-02-02)
- Config System (`config.json`)

### v1.1.0 (2025-02-01)
- Screenshots Feature mit Kodak LUT

### v1.0-stable (2025-01-31)
- TTS für unbegrenzte Peak-Nummern, Portable Pfade

---

## Known Limitations

- **macOS only** — Nutzt `say` Command für TTS, `fcntl` für Single-Instance Lock
- **No Tests** — Zero Test Coverage
- **Analyse-Zeitschätzung ungenau** — Basiert auf Dateigrößen, nicht auf echtem Profiling
- **Kein Undo** — Clip-Änderungen (In/Out) und Ignore sind nicht rückgängig machbar

---

*Zuletzt aktualisiert: 2026-02-09 (v2.3.0)*
