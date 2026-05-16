# CLAUDE.md

Das zentrale Entwickler-Dokument für PeakCut. Enthält alles was Claude Code (und Entwickler) wissen müssen.

---

## Zusammenarbeit mit Claude

Claude ist **technischer Partner**, nicht nur Ausführer.

- **Mitdenken** — Bedenken äußern, bessere Wege vorschlagen
- **Qualitätsanspruch** — Zaha-Hadid-Niveau, kein Baumhaus
- **Max' Rücken sein** — Architektur-Entscheidungen hinterfragen, Risiken aufzeigen

Wenn Claude eine Idee von Max bekommt:
1. Ist das ein etabliertes Pattern? → sagen
2. Gibt es einen besseren Weg? → vorschlagen
3. Gibt es Risiken? → warnen
4. Overengineered? → simpler vorschlagen

**Kein Quickfix wenn die richtige Lösung genauso machbar ist.** Wenn ein Bug auftritt (z.B. Race Condition, Crash), nicht einfach einen Guard davor setzen und das Problem umgehen — sondern die Architektur so bauen, dass das Problem gar nicht entstehen kann. Beispiel: Statt "Screenshot-Button disablen während Worker läuft" → parallele Worker-Queue, damit der User ohne Warten weiterarbeiten kann.

---

## Project Overview

PeakCut ist eine Python/PyQt6 Desktop-App für Podcast-Nachbearbeitung. Sie erkennt Keyboard-Peaks (Fußpedal-Marker) in Audioaufnahmen und exportiert nummerierte Clips mit Timecodes.

**Produktiv im Einsatz für:** Postproduction des [Hotel Matze](https://mitvergnuegen.com/hotelmatze/) Podcasts (Max ist aktuell einziger User)

---

## Folder Structure

```
PeakCut/                       ← Container-Ordner (KEIN Git-Repo)
├── Design/                   ← Design-Assets, Inspiration
├── Release/                  ← Versandfertiges Paket (geparkt seit Mai 2026, siehe Distribution)
│   └── INSTALLATION.md       ← (DMG entfernt; Build-Skripte erzeugen sie bei Bedarf wieder)
├── Dokumentation_Archiv.zip  ← Archivierte alte Doku/Videos
└── App/                      ← Git Repo Root
    ├── CLAUDE.md              ← Diese Datei (seit 2026-05-15 IM Repo, Distribution-Pivot machte das Verstecken obsolet)
    ├── docs/
    │   ├── CONTEXT.md         ← Kurzfassung für den PO
    │   └── specs/             ← Design-Dokumente (Brainstorming-Ergebnisse)
    ├── src/
    │   ├── core/              ← Core Logic (Klassen-basiert)
    │   ├── gui/               ← PyQt6 GUI Components
    │   └── lib/               ← External Libraries
    ├── tests/                 ← pytest Tests (94 Tests)
    ├── assets/
    │   ├── pictures/          ← Icons, Logos
    │   └── zahlen/            ← TTS Fallback MP3s
    ├── luts/                  ← LUT Library (.cube Dateien)
    ├── config.json            ← User Settings
    ├── pytest.ini             ← pytest Config
    ├── requirements.txt
    ├── venv311/               ← Virtual Environment
    ├── build.sh               ← Build-Script: ffmpeg bundlen → Tests → .app → DMG → Release
    ├── bundle_ffmpeg.sh       ← Bundled ffmpeg/ffprobe mit allen dylibs
    ├── smoke_test.sh          ← Smoke Test für gebundelte .app
    ├── PeakCut.spec           ← PyInstaller Build-Config (in .gitignore)
    └── PeakCut.icns           ← App Icon (in .gitignore)

# Export Output (nicht im Repo)
~/Downloads/{Gastname} - PeakCut Export/
├── Keyboardstellen - {Gastname}.mp3
├── Keyboardstellen - {Gastname}.txt
├── Keyboardstellen - {Gastname}.xml
└── {Gastname} - Screenshots/

# User Data (gebundelte App)
~/Library/Application Support/PeakCut/
├── config.json
├── temp/
└── logs/
```

### Distribution

**Status (Mai 2026): Launcher-App, kein PyInstaller-Bundle.**

Max nutzt PeakCut ueber einen kleinen AppleScript-Launcher in `/Applications/PeakCut.app` (~2.6 MB), der nichts anderes macht als den Repo-Python aufzurufen:

```
/Applications/PeakCut.app
  ↓ (Doppelklick / Dock / Spotlight)
do shell script "<repo>/App/venv311/bin/python <repo>/App/src/main_pyqt.py"
  ↓
PeakCut GUI startet aus dem Repo-Code
```

Damit gibt es **eine Codebasis** (das Repo). Aenderungen sind sofort live — kein Rebuild noetig.

CheckIn ruft PeakCut auf demselben Weg auf (`spawn(PEAKCUT_PYTHON, ...)` in `CheckIn/App/main.js`), nutzt also denselben Repo-Code wie der Launcher.

**Launcher-Bau (zur Referenz):**
- `osacompile -o /Applications/PeakCut.app starter.applescript`
- Icon: `PeakCut.icns` als `Contents/Resources/applet.icns` einkopieren
- `Assets.car` aus `Contents/Resources/` entfernen (sonst ueberschreibt sie das Icon)
- Info.plist editieren (Name, Bundle-ID, Display-Version)
- **Wichtig: Nach jeder Bundle-Aenderung neu signieren:** `codesign --force --deep --sign - /Applications/PeakCut.app` — sonst blockt macOS Sequoia den Start silent.

### ffmpeg-Bundling (geparkt)

Wird aktuell nicht genutzt, weil keine DMG mehr verteilt wird. Infrastruktur bleibt fuer den Fall, dass PeakCut wieder als eigenstaendige App gepackt werden soll (extern verteilen, andere User).

- `bundle_ffmpeg.sh` erstellt `bundled_ffmpeg/` mit ffmpeg, ffprobe + 90 dylibs (~77 MB)
- `build.sh` ruft `bundle_ffmpeg.sh` automatisch auf wenn nötig
- Im Code: `FFMPEG_BIN` und `FFPROBE_BIN` aus `utils.py` verwenden (FROZEN-aware)
- **Nie** hardcoded `"ffmpeg"` oder `"ffprobe"` in subprocess-Aufrufen verwenden

---

## Commands

```bash
cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App

# App starten (Development)
"./venv311/bin/python" src/main_pyqt.py

# App starten mit CheckIn-Integration
"./venv311/bin/python" src/main_pyqt.py --guest "Gastname" --export-dir "/pfad/zu/3_PeakCut Export/"

# Tests ausführen
"./venv311/bin/python" -m pytest tests/ -v

# Build: .app + DMG
./build.sh

# Dependencies installieren
"./venv311/bin/pip" install -r requirements.txt

# Virtual Environment neu erstellen
rm -rf venv311
~/.pyenv/versions/3.11.*/bin/python3 -m venv venv311
"./venv311/bin/pip" install -r requirements.txt
```

---

## Architecture

### Source Files

```
src/
├── main_pyqt.py               # PyQt6 Entry Point (Single-Instance Lock via fcntl)
├── config.py                   # JSON Config Management (thread-safe, lazy-loaded)
├── utils.py                    # Path constants, time helpers, logging setup, media file validation
├── core/
│   ├── project.py              # PeakCutProject — Datei-Abstraktion
│   ├── session.py              # PeakCutSession — State Management (Qt-frei, Callback-basiert)
│   ├── peak.py                 # Peak Datenmodell (position_ms, in/out points, bounds)
│   ├── detection.py            # Peak Detection (np.abs, threshold, gap filtering)
│   ├── playback.py             # Audio Playback + State Tracking (simpleaudio)
│   ├── sync.py                 # Video-Audio Sync (ffmpeg + FFT, 10-min window + fallback, ThreadPoolExecutor)
│   ├── analysis_process.py     # Standalone subprocess for analysis (avoids Qt conflicts)
│   ├── guest_name.py           # Gastname aus 'mix'-Dateinamen extrahieren (eigenes Modul seit v2.9.0)
│   └── exporters.py            # MP3/XML/TXT Exporter (ffprobe for resolution, samplerate, depth, channels)
├── gui/
│   ├── main_window.py          # Hauptfenster: Import, Gastname-Dialog, Analyse-Orchestrierung, Flow Welcome→Analyse→Zuordnung→Review
│   ├── assignment_page.py      # Folgenschnitt-Zuordnung (gekapselt): build_assignment_state (pure) + AssignmentPage Widget
│   ├── thumbnail_worker.py     # Async Kamera-Thumbnails (QThread, sequenziell, ffmpeg fast-seek)
│   ├── review_page.py          # ReviewPage Widget: Video + Controls + Navigation + Export (~420 Zeilen)
│   ├── workers.py              # AnalysisWorker + ExportWorker (QThread); ExportWorker kapselt guarded Folgenschnitt-Pipeline
│   ├── apple_style.py          # macOS Apple-Style Stylesheet, hell/weiss (15 Sections, COLORS dict, get_stylesheet())
│   └── video_preview_peak.py   # Video-Player: QMediaPlayer + LUT + Async Screenshots
└── lib/
    └── lut_processor.py        # LUT Trilinear Interpolation + Pre-computed 256³ Lookup (numpy)
```

### Core Classes

```
PeakCutProject (project.py)
  - export_dir (settable property: default ~/Downloads/{guest_name} - PeakCut Export/)
  - keyboard_track, mic_tracks, videos
  - set_files(), get_all_file_paths(), get_reference_track()
  - guest_name (settable property: user-set oder auto-detected aus Mix-Dateiname)

PeakCutSession (session.py)
  - status_update: StatusUpdate (callback-basiert, Qt-frei)
  - State: peaks, current_peak, mode, keyboard_audio, mic_audios, video_offsets
  - Methods: play_current(), switch_mode(), ignore_peak(), set_current_peak()
  - load_analysis_results(dict) — loads peaks + offsets from subprocess
  - load_audio_lazy() — deferred parallel audio loading (ThreadPoolExecutor), sets duration bounds on peaks

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
  - _probe_video_info() — ffprobe für Resolution
  - _probe_audio_info() — ffprobe für Samplerate, Bit-Depth, Channels

config.py
  - Thread-safe via threading.Lock
  - get(key), set_value(key, value), load(), save()

utils.py
  - FROZEN: bool — True wenn als .app Bundle ausgeführt
  - Path constants: DATA_DIR, TEMP_DIR, ASSETS_DIR, LUTS_DIR (FROZEN-aware)
  - ms_to_timecode(ms, fps) — ms → SMPTE Timecode (HH:MM:SS:FF)
  - ms_to_frames(ms, fps) — ms → Frame-Anzahl
  - ms_to_mmss(ms) — ms → "M:SS" Display-Format
  - parse_timecode_to_ms(tc_str, fps) — SMPTE Timecode → ms
```

### Module Dependencies

```
main_pyqt.py
  └── gui/main_window.py
        ├── gui/apple_style.py          (COLORS dict, get_stylesheet())
        ├── gui/workers.py              (AnalysisWorker, ExportWorker)
        │     └── core/exporters.py
        ├── gui/review_page.py          (ReviewPage — Controls, Navigation, Export)
        │     ├── gui/video_preview_peak.py   (PeakVideoPreview — Player + LUT + Screenshots)
        │     │     └── lib/lut_processor.py
        │     └── gui/workers.py        (ExportWorker)
        ├── core/project.py
        ├── core/session.py
        │     ├── core/peak.py
        │     └── core/audio.py
        ├── config.py
        └── utils.py                    (logging, validation, time helpers)
```

**Review-Quellen:** 5 Review-Perspektiven als Qualitätscheck: IT-Student, Professor, Chief Developer, Tontechniker, Video-Postproduction (Session 22.03.2026).

Analysis runs in a **separate process** (`core/analysis_process.py`), spawned by `AnalysisWorker` in `workers.py`. In Development: subprocess.Popen. In .app Bundle: multiprocessing.Process. Pre-flight file validation + 10-Minuten-Timeout-Watchdog. Export läuft in eigenem `ExportWorker` QThread.

### CheckIn-Integration (CLI)

PeakCut akzeptiert CLI-Argumente fuer die Integration mit CheckIn:

- `--guest "Gastname"` — Pre-fills den Gastname-Dialog (auto-detected aus Mix-Dateiname wird ueberschrieben)
- `--export-dir "/pfad/"` — Export geht direkt in dieses Verzeichnis statt `~/Downloads/`

Nach dem Export schreibt `ExportWorker` eine Signal-Datei `.peakcut_done` in das Export-Verzeichnis (Zeitstempel als Inhalt). CheckIn watched per `fs.watch()` darauf und bringt sich automatisch in den Vordergrund.

Implementierung:
- CLI-Parsing: `main_pyqt.py` (argparse)
- Guest-Name: `MainWindow.__init__` → `self._guest_name = cli_guest`
- Export-Dir: `MainWindow._start_analysis` → `project.export_dir = self._cli_export_dir`
- Signal-Datei: `workers.py` → `ExportWorker.run()` → `.peakcut_done` nach allen Exports

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
3. **Pre-flight Validation** → Alle Dateien existenzgeprüft
4. **Gastname-Dialog** → Auto-detected aus Mix-Dateiname, User kann editieren/bestätigen
5. **Analyse startet** → `AnalysisWorker` (QThread) spawnt `analysis_process.py` als Subprocess (10-Min-Timeout)
   - Subprocess: `sync.sync_videos()` → video_offsets (ffmpeg + fftconvolve, parallel via ThreadPoolExecutor)
   - Subprocess: `detection.detect_peaks()` → peaks list
   - Ergebnis als JSON über stdout zurück
5. **Ergebnisse geladen** → `session.load_analysis_results(dict)` → Peaks + Offsets
6. **Audio wird lazy geladen** bei erstem Playback → `session.load_audio_lazy()`
7. **Navigation**: `navigate_to_peak(index)` → Session + Video + UI aktualisiert
8. **Export**: `ExportWorker` (QThread) → `MP3Exporter/XMLExporter/TXTExporter.export(session)`

Status-Updates laufen über `session.status_update` Callbacks + stderr vom Subprocess.

---

## UI Design (4-Page Flow)

### Pages (QStackedWidget)

| Page | Index | Inhalt |
|------|-------|--------|
| **Welcome** | 0 | Zentrierter "PeakCut" Titel + "Import Files" Button |
| **Analysis** | 1 | Analyse-Status + Fortschritt (wartet auf Subprocess) |
| **Zuordnung** | 2 | Folgenschnitt: Kamera→Shot-Typ/Person + Mic→Person (gekapselt, eigenes Widget). 0-Peaks-Guard greift davor. |
| **Review** | 3 | Video-Player + Controls + Navigation + Export |

### Review Page Layout (von oben nach unten)

```
┌──────────────────────────────────────────────────────┐
│ Kamera:[▼ name (editierbar)]   LUT:[▼]  Helligkeit:[══●══] +20 │ ← Top-Bar
│ ┌──────────────────────────────────────────────────┐ │
│ │                                                  │ │
│ │                VIDEO PLAYER                      │ │
│ │                                                  │ │
│ └──────────────────────────────────────────────────┘ │
│ [═══════════════ Timeline Slider ═══════════] 1:23 / 4:56 │
│ [◀][Play/Stop][▶] | [Ignore] [Mode] Peak 3/47 [Screenshot] [Export] │
│                     Statusbar                        │ ← Statusbar
└──────────────────────────────────────────────────────┘
```

### Video-Player (video_preview_peak.py)

- **QMediaPlayer** + **QVideoSink** für Frame-Interception
- **LUTWorker** (QThread): Verarbeitet Frames off-main-thread mit LUT + Brightness
- **ScreenshotWorker** (QThread): Async Screenshots via ffmpeg + LUT + Brightness (parallel Queue, kein Warten)
- **Deferred Play**: `play_from(in_ms, out_ms)` — wartet auf Video-Load
- **Clip-Playback**: Stoppt automatisch am Out-Point
- Kein eigenes UI — nur `QLabel` für Video-Display

### Kamera-Namen

- `camera_combo` — Kamera-Wähler (Dropdown, **nicht editierbar**, nur durchklicken)
- Label kommt aus der Zuordnung: `camera_display_label()` → `"{Person} {Shot}"`
  (z.B. „Matze weit", „Hartmut Close"), Fallback Shot-Label bzw. Dateiname
- Umbenennen passiert nur im Zuordnungs-Schritt davor, nicht hier
- Screenshots erben das Label: "Matze weit 1.jpg", "Hartmut Close 2.jpg"

---

## Configuration

`config.json`:
```json
{
  "threshold_factor": 0.3,
  "min_gap_ms": 12000,
  "preview_duration_ms": 1000,
  "context_duration_ms": 15000,
  "fps": 25,
  "tts_voice": "Anna",
  "lut_path": ""
}
```

| Key | Default | Beschreibung |
|-----|---------|--------------|
| `threshold_factor` | 0.3 | Peak-Erkennung Schwellwert (% vom Max-Sample) |
| `min_gap_ms` | 12000 | Minimaler Abstand zwischen Peaks (ms) |
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

Shortcuts sind nur auf der Review-Page aktiv (Page Index 3).

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

## V3 Vision — Modulare Production Suite

### Architektur-Prinzip

Module kommunizieren über **Dateien**, nicht über Code. Jedes Modul ist einzeln testbar und änderbar. Keine Race Conditions, keine geteilten RAM-Daten zwischen Modulen.

```
┌─────────────────────────────────────────────────────────┐
│                      PEAKCUT HUB                        │
│                                                         │
│  [Smart Scan] → [Create Mix] → [Peaks] → [Screenshots] │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                   Material-Ordner/
                     .peakcut/         ← Versteckter Ordner für PeakCut-Daten
                       scan.json       ← Smart Scan Ergebnis
                       peaks.json      ← Peak-Positionen
                     MIC1.wav          ← Original-Dateien (unberührt)
                     MIC2.wav
                     mix.mp3           ← Generierter Mix
                     CAM_A.mp4
```

### Module

| Modul | Input | Output | Status |
|-------|-------|--------|--------|
| **Smart Scan** | Material-Ordner | scan.json (Spuren kategorisiert: leer/keyboard/sprache/video) | Neu |
| **Create Mix** | Sprach-Spuren aus Scan | mix.mp3 (ffmpeg: zusammenmischen + Limiter) | Neu |
| **Peaks** | Keyboard-Spur + Mix | peaks.json + XML + MP3 + TXT | Existiert |
| **Screenshots** | Videos + Mix | JPGs mit LUT | Teilweise (Button existiert, eigene Page fehlt) |

### Smart Scan — Erkennung ohne Dateinamen

Statt auf Dateinamen zu vertrauen, analysiert Smart Scan das Audio:

| Spur-Typ | Erkennungsmerkmal |
|----------|-------------------|
| **Leer** | RMS < Threshold (Stille) → automatisch ignorieren |
| **Keyboard** | Kurze laute Impulse, viel Stille dazwischen |
| **Sprache** | Kontinuierliches Signal, Speech-Pattern |

User bestätigt die Zuordnung, dann weiter.

### Create Mix — Simpel mit Limiter

```
Sprach-Spuren (z.B. MIC1 + MIC2)
     ↓
ffmpeg: zusammenmischen + alimiter + normalisieren
     ↓
mix.mp3
```

Keine neue Dependency. ffmpeg ist bereits da. Auphonic-Integration optional für später.

### Screenshots — Zwei Audio-Modi

| Phase | Audio |
|-------|-------|
| Während Analyse läuft | Kamera-Ton (Video unmuten) |
| Nach Analyse fertig | Mix (simpleaudio, synchron) |

Screenshots können parallel zur Analyse gemacht werden, weil der Mix als Datei existiert (aus Create Mix) und nicht im RAM blockiert ist.

### Entscheidungen (Stand 2026-02-10)

| Thema | Entscheidung | Begründung |
|-------|--------------|------------|
| UI | Hub mit Buttons | Unabhängige Module, einzeln entwickelbar |
| Projekt-State | Kein persistenter State | Immer frisch scannen, kein "Projekt laden" |
| Modul-Kommunikation | Über Dateien | Kein shared RAM, keine Race Conditions |
| Create Mix | ffmpeg + Limiter | Keine neue Dependency |
| Descript | Manuell | Keine API-Integration fürs Erste |
| Screenshots Audio | Kamera-Ton während Analyse | Mix erst nach Analyse verfügbar für Sync |

### Geparkt (später)

- Descript API Integration
- SRT/Untertitel in XML einbetten
- Auphonic API für Mix-Polish
- In/Out Clip Editor

---

## Offen (aktuelles Release)

### PeakCut-Backlog — abgegrenzt 2026-05-16 (NICHT mehr Folgenschnitt-Feature)

Folgenschnitt (generisches Modell + Zuordnungs-Schritt) wurde 2026-05-16 von
Max für **fertig erklärt** (validiert: 304-Schnitt-Export = cutter-gelobte
Zahl, Leitplanke greift, 153 Tests grün). Folgendes ist bewusst *getrennter*
Backlog, kein offenes Feature mehr:
- [ ] **10.2 Shot-Combo-Kontrast (echter Bug, wiederöffnen bei Carl):** auf
  macOS rendert das *native* QComboBox-Popup die markierte Zeile weiß-auf-
  hellgrau (teils unlesbar). `QAbstractItemView`-Stylesheet greift nicht.
  Braucht Non-Native-View + explizite Item-Farben. Screenshot-Belege bei Max.
- [ ] **„LUT hinzufügen" (Max-Wunsch, eigenes Mini-Feature):** Datei-Dialog →
  LUT in `luts/` kopieren → bleibt künftig auswählbar. Eigene Mini-Spec.
- [ ] **Cutter-Qualitäts-Sign-off:** braucht 1 aufbewahrten sauberen Export
  (vollständige Zuordnung). XML ist regression-locked frame-identisch zur
  bereits gelobten reaktiven Version — Bestätigung, kein Blocker.
- [ ] **Fremdmaterial-Test (Max):** echte Fremdproduktion durchspielen.
  Produktionsunabhängigkeit ist testbewiesen — reale Bestätigung.
- [ ] Competitor-Recherche (autocut.com, Resolve Scene-Cut, GitHub-Repos) —
  Inspiration, geparkt.

### Quick Fixes (vor V3)
- [x] ~~`extract_guest_name` aus exporters.py in eigenes Modul~~ — erledigt (v2.9.0, → `core/guest_name.py`)
- [ ] Code Signing (Apple Developer Account) für Gatekeeper-freie Installation (geparkt — siehe Distribution)

### Strukturell (vor V3)
- [ ] **UI Revamp** — Redesign in Figma, dann Umsetzung in PyQt6. Figma ist das Design-Tool. Arbeitsteilung: Max/Design-KI designt in Figma → Screenshots an Claude → Claude setzt in PyQt6 um. Gleich den V3 Hub mitdesignen, nicht nur die aktuelle 3-Page-Struktur.

### V3 Module
- [ ] **Smart Scan** — Ordner scannen, Audio analysieren
- [ ] **Create Mix** — Sprach-Spuren zusammenmischen (mit Gain-Normalisierung)
- [ ] **Screenshots Page** — Eigene Page mit Video-Scrubbing, Thumbnail-Grid
- [ ] Marker-Export (Peaks als Marker statt Clips im XML)
- [ ] Einzelne Video-Clips pro Peak (MP4 Export)
- [ ] **Projekt-Metadaten**: Gastname, Aufnahmedatum, Kamera-Zuordnung — ersetzt `extract_guest_name` und Dateinamen-Parsing

### Erledigt
- [x] ~~Multiprocessing für Video-Sync~~ — erledigt (v2.6.0)
- [x] ~~Kamera-Namen editierbar~~ — erledigt (v2.4.0)
- [x] ~~Test Coverage~~ — 94 Tests (v2.7.0)
- [x] ~~Magic Numbers extrahieren~~ — erledigt (v2.6.1)
- [x] ~~apple_style.py aufteilen~~ — erledigt (v2.6.1)
- [x] ~~main_window.py aufteilen~~ — erledigt (v2.7.0, 780→270 Zeilen)
- [x] ~~File Logging~~ — erledigt (v2.7.0)
- [x] ~~Media-Validierung~~ — erledigt (v2.7.0)
- [x] ~~venv aufräumen~~ — erledigt (v2.7.0, 30→17 Packages)
- [x] ~~print(stderr) → Logger~~ — erledigt (v2.7.0)
- [x] ~~_FIRST_FRAME_DELAY_MS auf Modulebene~~ — erledigt (v2.7.0)
- [x] ~~MP3 Bitrate explizit 192k~~ — erledigt (v2.7.0)
- [x] ~~INTERN_DIR Dopplung~~ — erledigt (v2.7.0, config.py importiert aus utils.py)
- [x] ~~XML depth/channels per ffprobe~~ — erledigt (v2.7.0)
- [x] ~~CI: GitHub Action~~ — erledigt (v2.7.0)
- [x] ~~Qt raus aus Session~~ — erledigt (v2.7.0, StatusUpdate Callback-Klasse)
- [x] ~~np.abs(samples)~~ — erledigt (v2.7.0)
- [x] ~~Sync auf 10min begrenzen~~ — erledigt (v2.7.0, mit Fallback bei schwacher Korrelation)
- [x] ~~audio.py splitten~~ — erledigt (v2.7.0, detection.py + playback.py)
- [x] ~~Gastname-Dialog~~ — erledigt (v2.7.0, nach Import, auto-detected + editierbar)
- [x] ~~Export nach Downloads~~ — erledigt (v2.8.0, ~/Downloads/{Gastname} - PeakCut Export/)
- [x] ~~macOS .app Bundle~~ — erledigt (v2.8.0, PyInstaller + DMG, 67 MB)
- [x] ~~START HERE Ordner entfernt~~ — erledigt (v2.8.0, ersetzt durch .app)

### Technische Schulden (irgendwann)
- Type Hints systematisch
- FCPXML (FinalCut X Format)
- Drop-Frame Timecodes für 29.97fps
- simpleaudio ersetzen (für Clip Editor)
- ffmpeg Version-Pinning

## Langfristig (V4+) — Die großen Visionen

**Nie aus den Augen verlieren.** Bei jeder Architektur-Entscheidung prüfen: Stellen wir hier Weichen für später?

### Produkt

| Vision | Was | Weichen jetzt? |
|--------|-----|----------------|
| **Hardware-Button** | Physischer Marker statt Keyboard (~50-69€) | Keyboard-Erkennung abstrakt halten, nicht auf Piano-Sound hardcoden |
| **Abo-Modell** | ~10€/Monat Software, Hardware separat | Account-System vorbereiten (User-ID für ML-Daten) |

### Technik

| Vision | Was | Weichen jetzt? |
|--------|-----|----------------|
| **Electron + React** | Cross-Platform, Auto-Updates | Python-Core als Library bauen, nicht als Script. PyInstaller-Bundle ist Zwischenschritt. |
| **FastAPI Cloud** | Accounts, Sync, Profile zwischen Geräten | API-first denken bei neuen Features |
| **ML-Profile** | Lernt welche Clips gut sind, Vorhersage ohne Klick | Daten mitschreiben: peak_decisions.json, scan_corrections.json |

### Integrationen

| Vision | Was | Weichen jetzt? |
|--------|-----|----------------|
| **Descript** | Automatischer Upload, Transkript holen | Export-Ordner sauber halten für spätere Automation |
| **Google Drive** | Automatischer Upload/Download | — |
| **Automatische Captions** | SRT generieren, in Premiere nutzen | XML-Export erweiterbar halten |

### Features

| Vision | Was | Weichen jetzt? |
|--------|-----|----------------|
| **Smarte Clip-Grenzen** | Automatische Optimierung wo Clip anfängt/endet | Audio-Analyse-Code wiederverwendbar bauen |
| **Clip Editor** | In/Out Points anpassen | Peak-Datenmodell hat schon in_offset/out_offset |
| **Rückkanal von Reels** | Wissen welche Peaks veröffentlicht wurden → ML-Training | Tracking-ID pro Peak für späteren Abgleich |

---

## Changelog

### v2.11.0-dev (2026-05-16, develop — NOCH NICHT auf main) — Folgenschnitt Stufe 2 / Track 1

Deterministische Zeitlogik-Auflockerung als Schicht ÜBER Stufe 1
(unverändert). 4-Augen mit Carl (Plan + Snap-Delta), Claude TDD-Bau,
Max Entscheider. Spec: `docs/specs/2026-05-16-folgenschnitt-stufe2-track1-design.md`.

- **Neues Modul** `src/core/folgenschnitt_loosening.py`: Base-Camera-Adapter
  (weit>close>halbnah>totale → synthetisches `SHOT_WIDE` nur für den
  unveränderten Stufe-1-Aufruf), Block-Segmentierung (grosse Minuten-
  Blöcke, `first_block`→`target`→densify, harter `min_block`-Deckel),
  Kamera-Rotation, periodische Establishing-Totale, Pausen-Snapping
  (`build_pause_ranges` aus `speaker_activity`; Floor gewinnt IMMER,
  sequenziell, Klemmen statt roh, leeres Fenster → Cut weg).
- **Pluggbare Strategie** (`FolgenschnittLooseningStrategy` Protocol) —
  Track 2 (KI-Regisseur) wird später eingesteckt, nicht nachgebaut.
- Pipeline-Hook in `prepare_folgenschnitt_for_export`; `has_minimum`
  generalisiert (jede Kamera-Kombi inkl. nur-Totale → valide XML).
  Leitplanke + applied-Flag unverändert.
- Stufe 1 bit-stabil (Sicherheitsnetz-Tests); HM-XML-Regressionswächter
  grün. **Tests: 153 → 182.**
- v1-Defaults bewusst PROVISORISCH (min_block_to_loosen 120s, first 110s,
  target 90s, min_block 50s, totale 240s/25s). Carl-Schluss-Review
  technisch grün. **Vor main-Merge offen (Max-Entscheidung): Alex-
  Feedback + Premiere-EDL → v1-Zahlen justieren → neu verifizieren.**
  Anders als Folgenschnitt NICHT auf Carl-OK allein mergebar (neues
  Schnittverhalten, nicht regression-locked auf cutter-validierte Baseline).

### v2.10.0 (2026-05-16) — Generischer Zuordnungs-Schritt (Folgenschnitt produktiv)

*Versionslabel vorläufig — finale Nummer ist Max' Entscheidung.*

Folgenschnitt Stufe 1 in der App bedienbar gemacht und das Datenmodell von
Hotel-Matze-fest auf produktionsunabhängig generalisiert. 4-Augen mit Carl
(Plan), Claude (TDD-Bau), Max (Entscheider). Gate A bestanden. Spec:
`docs/specs/2026-05-16-zuordnung-generisch-design.md`.

- **Generisches Datenmodell**: `SpeakerId`/`CameraRole`-Enums entfernt.
  Person = freier String, `CameraAssignment = (shot_type, person|None)`,
  `MicAssignment` trennt `speaker_key` (Analyse) von `person` (final).
  Unknown = `None` statt `"unknown"`.
- **Gekapselter Zuordnungs-Schritt**: neue Page (Index 2) zwischen Analyse
  und Review. Voller Dateiname + Shot-Typ + bedingte Person, Mic→Person
  vorbelegt/überschreibbar. Async Kamera-Thumbnails. Review-Screen
  unverändert.
- **Harte Leitplanke**: `folgenschnitt_pipeline.prepare_folgenschnitt_for_export`
  + ExportWorker-Kapselung — Keyboardstellen-Export läuft IMMER, selbst bei
  unvollständiger Zuordnung oder Pipeline-Fehler (nur kurzer Hinweis).
- **Mic-Schutzfilter erhalten + testgesichert**: mix/keyboard/keys/klavier
  werden vor dem Paaren mit Personen weiter ausgefiltert.
- **Reaktives Cutter-Profil-Verhalten 1:1 erhalten** (HM-Regressions-Wächter
  grün). Cutter-Urteil zur reaktiven Vollfolge: "extrem stark, besser als
  Resolves Auto-Cut".
- **Tests**: 123 → 140 grün.

**Abnahme-Revisionen (2 Runden manuelle Abnahme durch Max):**
- Zuordnungs-Masken starten **komplett leer** (Kamera *und* Mic, keine
  vorgefüllte Namensliste). Getippte Namen wachsen in eine gemeinsame,
  überall auswählbare Liste. Grund: ein geratener Default, der „ausgefüllt"
  aussieht, ist gefährlicher als ein leeres Feld.
- `session.folgenschnitt_assignment_applied`: sobald der Zuordnungs-Schritt
  durchlaufen ist, fällt `prepare_folgenschnitt_for_export` **nicht** mehr
  auf Analyse-/Default-Mics zurück — eine bewusst leere Zuordnung bleibt
  leer (kein „hilfreicher" Automatismus).
- Hörprobe pro Mic-Zeile (`mic_preview_worker.py`): ffmpeg fast-seek,
  kurzer Ausschnitt off-main-thread, Start am **längsten** zusammenhängenden
  aktiven Block des Mics (nicht erstem Fenster), `play_audio`.
- Review-Kamera-Dropdown nicht mehr editierbar, zeigt die Zuordnung
  (`review_camera_labels.camera_display_label`); Screenshots nach Label.
- **Tests**: 140 → 147 grün.

**Task 10 — Abnahme-Politur (5 Mini-Pakete, kein Modell/Decision/Leitplanke):**
- 10.1 Bug: getippter Name füllt andere leere Felder nicht mehr
  (`_commit_person_name` sichert/restauriert currentText, blockt Signale).
- 10.2 Shot-Combo lesbarer Kontrast (`SHOT_COMBO_STYLESHEET`, lokal).
- 10.3 Review-LUT startet immer „Kein LUT" (+ `config lut_path=""`).
- 10.4 `ResettableBrightnessSlider`: Doppelklick → 0.
- 10.5 Import-Dialog immer Desktop (`default_import_folder()`, QSettings raus).
- Test-Harness: session-weite autouse QApplication-Fixture in
  `conftest.py` (PyQt6 GC-Sicherheit für Qt-Tests); ReviewPage-Tests
  rufen `cleanup()` (LUTWorker-QThread).
- **Tests**: 147 → 153 grün.

### v2.9.0 (2026-05-15) — CheckIn-Integration, Distribution-Pivot, Refactor

Maerz-Aenderungen aus 6 Wochen Produktivnutzung (entspricht "Haertetest bestanden") auf `main` gemergt. Neue Versionsnummer reflektiert die neue CLI-Schnittstelle.

**CheckIn-Integration (CLI-Schnittstelle):**
- **`--guest "Name"`**: PeakCut akzeptiert Gastname vom Aufrufer (commit 41e7c6a, 28.03.2026).
- **`--export-dir "/pfad/"`**: Export-Verzeichnis kommt vom Aufrufer statt aus ~/Downloads (commit 41e7c6a).
- **Signal-Datei `.peakcut_done`**: ExportWorker schreibt nach Abschluss eine Zeitstempel-Datei, die CheckIn ueberwachen kann (commit 6370386, 29.03.2026).

**Export-Fix:**
- **XML-Export**: Video-Clips heissen jetzt nach Originaldatei statt mit generischem Schema (commit deae779, 30.03.2026).

**Distribution-Pivot (Mai 2026):**
- PyInstaller-App-Bundle (`PeakCut.app` ~67 MB mit gebundeltem ffmpeg) aufgegeben.
- Stattdessen: AppleScript-Launcher (~2.6 MB) in /Applications, der den Repo-Code aufruft.
- DMG entfernt. Build-Skripte (`build.sh`, `PeakCut.spec`, `bundle_ffmpeg.sh`) bleiben fuer spaeteren Bedarf.
- Hintergrund: solange Max einziger Nutzer ist und CheckIn ohnehin den Repo-Code aufruft, gibt es nur noch **eine Codebasis** — Aenderungen sind sofort live.

**Refactoring:**
- **`extract_guest_name` extrahiert**: Aus `core/exporters.py` in eigenes Modul `core/guest_name.py`. Klarere Trennung. 94 Tests passen weiterhin gruen.

**Workflow-Aufraeumen:**
- `main` und `develop` wieder synchron auf demselben Stand. Ab jetzt: develop = Werkstatt, main = "Haertetest bestanden" (manueller Merge wenn etwas sich bewaehrt hat).
- **CLAUDE.md + CONTEXT.md zurueck ins Repo** (`App/CLAUDE.md`, `App/docs/CONTEXT.md`). Grund fuer das fruehere Verstecken (v2.4.0: DMG-Endnutzer sollen Entwickler-Doku nicht sehen) ist mit dem Distribution-Pivot weggefallen — es gibt keine DMG-Endnutzer mehr. Doku ist jetzt versioniert und fuer Mitlesende (z.B. Review) ueber Git zugaenglich.

### v2.8.1 (2026-03-24) — ffmpeg gebundelt, Ordnerstruktur aufgeräumt

**Distribution:**
- **ffmpeg/ffprobe ins App-Bundle eingebettet**: Keine externen Abhängigkeiten mehr. DMG enthält alles.
- **Release/-Ordner**: Versandfertiges Paket (DMG + INSTALLATION.md).
- **bundle_ffmpeg.sh**: Automatisches Bundling aller dylib-Abhängigkeiten mit Code-Signing.

**Struktur:**
- **`3 Intern/` aufgelöst**: src/, tests/, assets/ etc. direkt unter App/.
- **Dokumentation archiviert** (ZIP), Screenshot Tool + leere Ordner gelöscht.
- **Code**: `FFMPEG_BIN`/`FFPROBE_BIN` Konstanten in utils.py, `INTERN_DIR` → `APP_ROOT`.

### v2.8.0 (2026-03-23) — macOS App Bundle, Export nach Downloads

**Distribution:**
- **macOS .app Bundle**: PyInstaller-basiert, 67 MB DMG. Doppelklick-Installation, App-Icon im Dock.
- **build.sh**: Automatisiertes Build-Script (Tests → .app → DMG).
- **`START HERE <3/` und `2 Export/` entfernt**: Durch .app und Downloads-Export ersetzt.

**Export:**
- **Export nach Downloads**: Dateien landen in `~/Downloads/{Gastname} - PeakCut Export/` statt im App-Verzeichnis.
- **Screenshots-Ordner**: `{Gastname} - Screenshots/` (wird 1:1 ins Google Drive geladen).

**Architektur:**
- **FROZEN-aware Pfade**: `utils.py` erkennt PyInstaller-Bundle. Assets aus `sys._MEIPASS`, User-Daten nach `~/Library/Application Support/PeakCut/`.
- **Multiprocessing für gebundelte App**: `AnalysisWorker` nutzt `multiprocessing.Process` statt subprocess im .app Bundle.
- **`PeakCutProject()` ohne Argumente**: `export_dir` ist jetzt dynamische Property (aus `guest_name` abgeleitet), mit Setter für Tests.

**CI:**
- **CI gefixt**: `libasound2-dev` für simpleaudio, `pytest` als Dev-Dependency, `QT_QPA_PLATFORM=offscreen`.

### v2.7.0 (2026-03-22) — Härtung, Architektur, Pipeline-Tests

**Architektur:**
- **Qt raus aus Session**: `PeakCutSession` erbt nicht mehr von `QObject`. `pyqtSignal` ersetzt durch `StatusUpdate` Callback-Klasse. Core ist jetzt Qt-frei.
- **INTERN_DIR**: config.py importiert aus utils.py statt doppelte Berechnung.

**Härtung:**
- **Peak Detection**: `np.abs(samples)` statt nur positive Samples — erkennt Peaks unabhängig von Polarität.
- **XML Export**: Bit-Depth und Channels werden per ffprobe dynamisch erkannt statt hardcoded 16-bit/Stereo.
- **MP3 Export**: Bitrate explizit auf 192k gesetzt.
- **Sync Performance**: FFT-Korrelation auf erste 10 Minuten begrenzt, automatischer Fallback auf volle Länge bei schwacher Korrelation.
- **Logging**: `print(stderr)` → Logger in video_preview_peak.py. `_FIRST_FRAME_DELAY_MS` auf Modulebene.
- **File Logging**: Rotierender Log (`logs/peakcut.log`, 5 MB, 2 Backups).
- **Media-Validierung**: ffprobe-Check vor Analyse.
- **QThread SIGABRT Fix**: Screenshot-Worker wartet auf Thread-Ende vor `deleteLater()`.

**Refactoring:**
- **main_window.py aufgeteilt** (780 → 270 Zeilen):
  - `gui/review_page.py` (420 Zeilen) — ReviewPage Widget mit eigenem State + Signals
  - `gui/workers.py` (145 Zeilen) — AnalysisWorker + ExportWorker
- **sys.path.insert Hacks entfernt** aus session.py, exporters.py, main_window.py.
- **Fallback-Defaults korrigiert** in analysis_process.py.

**CI:**
- **GitHub Action**: pytest läuft automatisch bei Push/PR (Python 3.11 + ffmpeg).

**Dependencies:**
- 13 unused Packages entfernt (moviepy, opencv-python, imageio, requests, pillow, etc.) — 30→17 Packages im venv.

**Tests (94 Tests: 38 Unit + 16 Integration + 9 Config + 31 Pipeline):**
- `test_config.py` (9) — Config load/save, corrupt JSON fallback, thread safety, defaults
- `test_pipeline.py` (31) — End-to-End mit realistischem synthetischem Material (30s, 44100Hz):
  - Keyboard-Peaks mit Attack/Decay-Envelope + Ambient Noise
  - 2 Mic-Tracks mit simuliertem Sprachmuster (Bursts + Pausen)
  - 2 Kameras mit bekannten Offsets (1.5s, 3.2s) — Sync-Genauigkeit verifiziert
  - Stereo-Mix aus Mic-Tracks
  - Peak Detection: korrekte Anzahl, Positionen, Threshold-Varianten, Gap-Filterung
  - Analysis-Subprocess: Peaks + Multi-Kamera-Offsets + Audio-only
  - Session: Peaks, Offsets, Lazy Audio, Status-Callbacks (Qt-frei)
  - Alle Exporter (MP3, TXT, XML) mit Inhaltsprüfung
  - Edge Cases: alle ignoriert, Single Peak
  - Sync: bekannter Offset, Multi-Kamera, Audio-Limit, Korrelation
  - Media-Validierung: WAV, MP4, kaputte Dateien, kein Audio-Stream

### v2.6.1 (2026-02-25) — Sync-Fix, XML-Bugfixes, Integration Tests

**Kritische Bugfixes:**
- **Video-Sync Offsets repariert**: ffmpeg extrahiert Audio jetzt mit `-ar {ref_sr}` (Resampling auf Reference-Samplerate). Ohne Resampling waren alle Offsets 0 weil Camera-Audio (48kHz) ≠ Mix (44.1kHz).
- **XML max(0,...) Asymmetrie**: `source_out` für Video-Clips wird jetzt ebenfalls auf 0 geclamped — verhindert Duration-Mismatch bei negativen Offsets.
- **XML Frame-Rundung**: `clip_dur_f` wird als `source_out_f - source_in_f` berechnet statt separat aus ms → keine Off-by-one-Frame-Fehler mehr.

**Code-Qualität:**
- **Magic Numbers extrahiert**: Benannte Konstanten in audio.py, exporters.py, main_window.py, video_preview_peak.py, sync.py
- **apple_style.py aufgeteilt**: 15 benannte Section-Variablen statt einem monolithischen String. Public API unverändert.

**Tests (54 Tests: 38 Unit + 16 Integration):**
- `test_xml_integration.py` (16) — XML Pipeline End-to-End:
  - Video-Offsets korrekt angewandt (in/out verschoben vs. Audio)
  - Clip-Konsistenz (duration = out - in, end - start = duration, lückenlos)
  - Timeline-Alignment (Video + Audio gleiche start/end pro Peak)
  - Negative Offsets (Clamping, Duration trotzdem konsistent)
  - Sequence-Duration = Summe Clip-Durations
  - Sync-Offset Roundtrip (format_offset → parse_timecode_to_ms)
  - Multiple Kameras mit verschiedenen Offsets

### v2.6.0 (2026-02-25) — Architektur-Cleanup, Performance, Tests

**Architektur:**
- **material_dir entfernt**: `PeakCutProject` hat kein `material_dir` mehr — alle Dateien über `get_all_file_paths()` statt `os.listdir()` (verhindert "Unknown"-Bug bei Dateien von externen Pfaden)
- **guest_name als cached Property**: `project.guest_name` statt manuellem `extract_guest_name()` Aufruf überall
- **extract_guest_name**: Akzeptiert nur noch `file_paths` Liste, kein Directory-Scanning mehr. Regex-basiert, strippt "mix" aus Namen.

**Performance:**
- **MoviePy entfernt**: Direkter `ffmpeg`-Subprocess statt `VideoFileClip` für Audio-Extraktion — 12 transitive Dependencies entfernt
- **FFT-Korrelation**: `scipy.signal.fftconvolve` statt `scipy.correlate` — O((N+M)log(N+M)) statt O(N*M)
- **Paralleler Video-Sync**: `ThreadPoolExecutor` für mehrere Kameras gleichzeitig
- **Paralleles Audio-Laden**: `ThreadPoolExecutor` in `session.load_audio_lazy()`
- **Export im Hintergrund**: `ExportWorker` QThread, UI bleibt responsiv

**Robustheit:**
- **Pre-flight Validation**: Alle Dateien werden vor Analyse-Start auf Existenz geprüft
- **Analyse-Timeout**: 10-Minuten-Watchdog killt hängende Analyse-Prozesse
- **Spezifische Exceptions**: `except Exception:` durch konkrete Typen ersetzt (config.py, audio.py, video_preview_peak.py)
- **XML Sample Rate**: Nutzt jetzt geprobt `sample_rate` statt hardcodierter 48000Hz

**Code-Qualität:**
- **Timecode-Konsolidierung**: `ms_to_timecode`, `ms_to_frames`, `ms_to_mmss` aus Duplikaten in exporters.py/main_window.py → zentral in `utils.py`
- **Unused Imports entfernt**: QSizePolicy-Fehler beim Aufräumen sofort gefunden und gefixt

**Tests (38 Tests, pytest):**
- `test_project.py` (5) — PeakCutProject: file paths, reference track, kein material_dir
- `test_peak.py` (9) — Peak: clamping, offsets, ignored, duration
- `test_exporters.py` (7) — TXT/XML Export mit Mock-Session
- `test_extract_guest_name.py` (7) — Guest Name Extraktion aus Dateinamen
- `test_utils.py` (10) — Timecode-Konvertierungen, Roundtrip, Edge Cases

### v2.5.0 (2026-02-24) — Brightness-Regler, Parallele Screenshots, Peak-Detection Tuning

- **Brightness-Regler pro Kamera**: QSlider (-100 bis +100) in Top-Bar, Wert wird pro Kamera gespeichert
  - Live-Preview: Multiplikative Helligkeit VOR LUT (wie Premiere Exposure → LUT Pipeline)
  - Screenshots: `lutrgb` Filter in ffmpeg für identisches Ergebnis wie Preview
- **Parallele Screenshots**: Screenshot-Workers laufen parallel in einer Queue — kein Warten, kein Button-Disabling, kein Crash bei schnellem S-Drücken
- **Peak-Detection Tuning**: `threshold_factor` 0.4→0.3, `min_gap_ms` 15s→12s (mehr Peaks erkannt)

### v2.4.0 (2026-02-10) — Onboarding, Timeline Slider, Editierbare Kamera-Namen

- **Setup/Start Scripts**: `setup.sh` (Python/ffmpeg Check, venv, deps) + `start.sh` in "START HERE <3/" Ordner
- **README**: Komplett neu geschrieben für Nicht-Entwickler
- **Timeline Slider**: QSlider mit Position/Duration Timecode-Anzeige auf Review-Page
- **Editierbare Kamera-Namen**: Camera-Combo ist jetzt editierbar, Name wird für Screenshots übernommen
- **PyQt6 in requirements.txt**: Fehlte bisher, Setup schlug fehl
- **CLAUDE.md aus Repo entfernt**: Liegt jetzt außerhalb (`PeakCut/CLAUDE.md`), nicht sichtbar für User
- **Cleanup**: `__pycache__/`, `logs/`, `.DS_Store` entfernt

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
- **Analyse-Zeitschätzung ungenau** — Basiert auf Dateigrößen, nicht auf echtem Profiling
- **Kein Undo** — Clip-Änderungen (In/Out) und Ignore sind nicht rückgängig machbar

---

*Zuletzt aktualisiert: 2026-05-16 (v2.11.0-dev Folgenschnitt Stufe 2 / Track 1 auf develop — 182 Tests; main = v2.10.0)*
