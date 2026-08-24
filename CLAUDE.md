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

PeakCut ist eine Python/PyQt6 Desktop-App für Podcast-Nachbearbeitung. Sie erkennt Marker-Peaks in Audioaufnahmen und exportiert nummerierte Clips mit Timecodes.

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
    ├── tests/                 ← pytest Tests
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
- **Versionsdrift (bewusst geparkt, HC-1 2026-05-17):** `build.sh` (`VERSION`)
  und `PeakCut.spec` (gitignored, lokal) stehen noch auf `2.9.0` — NICHT
  die App-Version (main = v2.11.0-Stand). `build.sh` ist als
  `2.9.0-STALE-PARKED` markiert. Vor einer Bundle-Wiederbelebung beide
  aktualisieren; die finale Versionsnummer ist eine Max-Entscheidung,
  nicht automatisch hochzuzählen.

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
  - marker_track, mic_tracks, videos
  - set_files(), get_all_file_paths(), get_reference_track()
  - guest_name (settable property: user-set oder auto-detected aus Mix-Dateiname)

PeakCutSession (session.py)
  - status_update: StatusUpdate (callback-basiert, Qt-frei)
  - State: peaks, current_peak, mode, marker_audio, mic_audios, video_offsets
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
        │     ├── core/project.py
        │     └── core/playback_modes.py
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
| `PeakCutSession` | `peaks`, `current_peak`, `mode`, `marker_audio`, `mic_audios`, `video_offsets` |
| `config.py` | `_config` (JSON-basiert, lazy-loaded, thread-safe via `_lock`) |

---

## Data Flow

1. **User klickt "Import Files"** → Datei-Dialog, Dateien kategorisiert (marker/mics/videos)
2. **Falls Marker nicht auto-erkannt** → Dialog zur Auswahl
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
| `preview_duration_ms` | 1000 | Marker-Mode Preview Länge |
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

## Rollen-Erkennung (Marker / Mix / Mic / Kamera)

**Achtung: zwei Wege im Repo, bewusst — nicht verwechseln.**

### 1. Namens-Heuristik (`core/import_classifier.py`) — der Weg, den die PyQt-App geht
- **Marker**: Dateiname enthält `keyboard`, `keys` oder `klavier`
- **Mix/Referenz**: Token `mix`/`mixdown` **oder** Gerätemuster `_MIX_DEVICE_RE = ^p\d+mix(?:down)?$`
  (fängt die HM-Studio-Konvention „P8Mix" — Commit `91cc8ae`, Wurzelfix des Phasing-Bugs
  bei Johanna Klug). `remix`/`mixer`/`pmix` bleiben bewusst draußen.
- **Videos**: `.mp4` oder `.mov`
- Tokenisierung splittet auf nicht-alphanumerisch (`import_classifier._tokens`).

### 2. Inhalts-Erkennung (`core/material_scanner.py`) — der neue, robustere Weg
Erkennt den Marker **am Signal statt am Namen**: viel Stille + laute Einzelimpulse
(`material_scanner.py:56-63`, Commit `4fbb3d1` „Marker-Auto-Erkennung Hybrid" —
verstreute Fenster + bounded Voll-Pass). Der Test benennt die Datei absichtlich
`MIC4.wav` (`tests/test_marker_detection_hybrid.py:65-69`), weil genau dieser reale
HM-Fall über den Namen NICHT erkennbar war.

**Status ehrlich:** `material_scanner` hat in `App/src` **noch keinen Aufrufer** —
die PyQt-App rät weiterhin über den Dateinamen (`gui/main_window.py:219-236`).
Genutzt wird die Inhalts-Erkennung bisher nur von der Web-Oberfläche
(`PeakCut-web`, Bestätigen-Schritt). Das Zusammenführen ist offen (BACKLOG: AUD-1).

---

## Git Workflow

### Branch-Struktur (Stand 2026-08-17)
```
main              ← Stable Releases
develop           ← Integrationszweig
feature/redesign  ← HIER WIRD SEIT 2026-06-22 GEARBEITET (= Max' Produktionsstand)
```

**Wichtig — warum `feature/redesign` und nicht `develop`:** Der Launcher in
`/Applications/PeakCut.app` ruft den Repo-Code **direkt** auf. Was ausgecheckt ist,
ist die produktiv laufende App. Max arbeitet seit dem 25.06. aus `feature/redesign`;
der Zweig ist also kein Nebengleis, sondern der scharfe Stand.

Seit dem Merge `deb6265` (2026-08-17) sind **alle drei Zweige inhaltlich identisch**
(845 Tests grün, CI grün). Vorher lag `feature/redesign` 18 Commits vorn und trug als
einziger Schema v5 + die Import-Pivot-Module — ein Zweigwechsel machte damit sowohl
Max' Produktionsakte unlesbar als auch die Web-Oberfläche im Schwester-Repo
`PeakCut-web` unstartbar. **Nicht wieder auseinanderlaufen lassen.**

### Regeln
- **Kleine Features**: Direkt auf dem Arbeitszweig
- **Große Features** (>1 Tag): Neuer `feature/name` Branch
- **Nach jeder Änderung**: Committen!
- **Commit-Message**: Kurz, prägnant, mit Co-Author
- **main-Merge**: `--no-ff` Marker-Commit, braucht Max-Go (Konvention seit `26f8097`)
- **Vor jedem Zweigwechsel prüfen:** Läuft gerade eine Produktion? Trägt der Zielzweig
  `CURRENT_SCHEMA_VERSION` ≥ dem, was in Max' Akten steht?

---

## Produkt-Strategie & Roadmap — Assistant Editor für Gesprächsformate

> Konvergenz aus 2 unabhängigen Strategie-Pässen (Carl + Claude,
> 2026-05-18), von Max abgenommen. Ersetzt die frühere „V3 — Modulare
> Production Suite". Lebendes Dokument — Identität/Reihenfolge ändert
> nur Max.

### Identität

PeakCut ist **keine** breite Post-Produktions-Suite. Es ist ein
**Assistant Editor für lange Gesprächsformate / das Gedächtnis einer
Produktion**: Raw-Aufnahmeordner rein → editor-ready Paket raus (Sync,
Marker, sinnvolle Clip-Kandidaten, Multicam-Rohschnitt, XML/Assets/
Metadaten). PeakCut sitzt **vor** Premiere/Pro Tools/CheckIn/Opus und
macht aus chaotischem Material strukturierte Entscheidungen — es
ersetzt sie nicht. Drei Dinge: Material **verstehen** → redaktionelle
**Absicht erkennen** → **Übergabe-Artefakte** für Profisysteme erzeugen.

**Bewusst NICHT:** NLE, Social-Scheduler, Analytics-Plattform, Pro-
Tools-Ersatz, generischer „KI macht dir Content"-Kasten. Je näher an
finaler Kreativentscheidung/Publishing, desto mehr verwässert der
Vorteil. Das Wort „Suite" ist raus — es verführt zum Alles-Bauen.

### Nutzer

Bester nächster Nutzer = **Team mit wiederkehrenden langen Gesprächs-
Produktionen** (getrennte Spuren, Multicam, echter Cutter):
Produktionsfirmen, Podcast-Studios, Producer wie Matze, Cutter-Teams.
NICHT der Solo-Creator (kommt später). Wertversprechen: „nimm 70 % der
stumpfen Vorarbeit weg, ohne den Premiere-Workflow kaputtzumachen".

### Kern-Objekt: ClipCandidate

Nicht nur „Peak". Felder: peak_id, Boundary, Transkript-Auszug, Grund,
Score, Status: vorgeschlagen → ausgewählt → produziert → veröffentlicht
→ verworfen. Plus `peak_decisions.json` als Rückkanal. Die
**Negativdaten** (nicht produziert / produziert-nicht-veröffentlicht /
veröffentlicht-aber-geflopt) sind der Burggraben — genau das haben
Opus-artige Tools nicht. **Minibar = Max' privates R&D-Labor** für
dieses Lernsystem, KEIN Produkt-Feature.

**Schärfung (Carl/Claude/Max 2026-05-20, nach #3-Rev):** Der eigentliche
Burggraben ist NICHT der Decider-Prompt selbst, sondern die
**redaktionelle Urteilsschule** von Max/Alex/Matze — operationalisiert
als Few-Shot-Beispiele, Anti-Patterns und Statusentscheidungen, die
sich über Zeit aus `peak_decisions.json` schärfen. Der aktuelle
Prompt ist nur die **v1-Oberfläche** dieses Wissens. Schutzfokus: die
Sammlung, nicht den Text fetischisieren. Anbieter (Opus/Riverside/
Spike) können denselben Prompt schreiben, aber nicht 70+ Folgen
Cut-Entscheidungen aus eurer Produktion replizieren.

### Nach #3-Rev-Smoke: Prompt-Tuning-Slice (vor Phasing-Fix)

**Smoke-Ergebnis 2026-05-21 (Sheila de Liz, 36 Peaks, Descript-
Bypass):** Pipeline läuft end-to-end an echtem Material. 35 von 36
Peaks bekamen narrative Sinnabschnitt-Vorschläge mit Konfidenz
0.78–0.80 (Beispiel-Reason: „Beginn der Reflexion über Reise mit
Partner, Peak in Studienfrage, Landung bei Erkenntnis aus Berichten
und Achterbahn-Analogie"). Peak 1 war ignoriert → korrekt kein
Sinnabschnitt + Bubble „Standard-Fenster wird verwendet". R4-
Disziplin live bewährt (kein/ungültiger Key → klare Statuszeile,
keine Pseudo-Einträge). Persistenz/HC-4-Cache greift („Analyse
übersprungen"). Drei Smoke-Befunde nachgezogen (Validator-
Verschärfung, temperature-Parameter, Descript-Import via CLI).

**Smoke-Blocker für eigentliches Hör-Urteil:** Wiedergabe-Schicht
ist UX-broken (Task #76) — Sinnabschnitt-▶ läuft im Video stumm,
Play startet Mic-Mode-Mix (alte Logik), Audio nicht synchron zum
Bild. Max muss erst Wiedergabe sortieren, bevor er die Vorschläge
beurteilen kann.

**Reihenfolge (Stand 2026-05-25):** Smoke ✓ → **#71a Audio-Routing-
Mini ✓** (auf main gelandet 2026-05-25) → **#76 Wiedergabe-UX**
(jetzt baufertig) → **Import-Refactor + Marker-Rename (#37, #77)** →
**#70 Prompt-Tuning**.

**Phasing-Wurzel diagnostiziert 2026-05-21:** Beim Import landet die
Mix-Datei in `project.mic_tracks` (main_window 232-237 sortiert alles
außer der Marker-Spur („keyboard/keys/klavier") als Mic). MP3Exporter (`exporters.py`
142-144) und `session.play_current` Mic-Mode (`session.py` 100-107)
overlay-summieren `mic_audios[0]` + `mic_audios[1:]` — die Mix-Datei
steckt aber als eine dieser „Mic-Spuren" mit drin. Folge: ProTools-
Mix wird on-top zu allen Einzel-Mics drauf-overlayt, jeder Sprecher
zweimal addiert (raw + bereits-gemischt). Latenz/Versatz → Phasing
sowohl im Cutter-MP3 als auch in der Speak-Mode-Wiedergabe.

**Carl-Fahrplan B-prime (statt voller Import-Refactor zuerst):**
- **#71a:** neuer Helper `core/audio_routing.py` (is_mix_track,
  get_mix_track, get_source_mic_tracks, get_speech_audio_segment).
  Regel: Mix vorhanden → Speech-Audio = Mix allein; sonst Overlay
  der echten Mics. MP3Exporter + `session.play_current` +
  `assignment_page` nutzen Helper. **XMLExporter + folgenschnitt_
  exporter BLEIBEN unangetastet** — Pin-1 (Keyboardstellen-XML byte-
  identisch). Trade-off: Hören sauber, XML-Pfade behalten Mix-als-
  Mic-Semantik bis zum Import-Refactor.
- **#76:** Carls bestehender Plan wird leicht angepasst — Speak/
  Smart laufen auf `get_speech_audio_segment` statt direkter Mix-
  Datei-Logik. Spec bleibt sonst gültig.
- **Import-Refactor (großer Slice):** Slots beim Import (Marker /
  Mics / Mix / Transkript / Kameras), Namens-Heuristik raus,
  separates `project.mix_track`, `.peakcut` Schema-v3 mit
  Backwards-Kompat, Pflicht-Regeln. Vereint #37.
- **#70:** Prompt-Tuning wie geplant.

Aufteilung: **Max + Claude editorial** (3–5 echte Beispielstellen
aus euren Folgen, jeweils positiv UND negatives Anti-Beispiel mit
Begründung; Hotel-Matze-Stilbeschreibung als redaktionelles
Regelwerk, nicht Marketingtext). **Carl Werkzeug** (A/B-Harness:
zwei Prompt-Varianten gegen dieselben BoundaryScaffolds, ohne sie
als Wahrheit in `.peakcut` zu schreiben; blinder Vergleich,
Urteilskategorien statt „besser/schlechter"; persistiert in
separatem `.peakcut/prompt_eval/`-Pfad).

Hebel (Reihenfolge der erwarteten Wirkung): Few-Shot (wenige sehr
gute Beispiele schlagen viele mittelmäßige) > Anti-Patterns
(lehrreicher als Idealfälle) > Stil-Profil als redaktionelles
Regelwerk > Self-Critique im selben Call (zweiter Modell-Call
erst, wenn A/B beweist, dass er hilft). Modell bleibt Opus —
Herzstück ist Urteil, da wird nicht gespart, bevor die Qualität
steht. Beispiele sind ab Tag 1 maschinenlesbar strukturiert
(Variant-ID, Beispiel-ID, erwartete Boundary, Begründung,
menschliches Urteil) — kein Fließtext-Friedhof.

### Roadmap-Reihenfolge (Carl/Claude-Konsens — ersetzt alte V3-Liste)

1. **Persistenz + `.peakcut`-Projektakte** (= HC-4, der Schlussstein —
   IST das Produkt, nicht „kein State" wie früher gedacht).
2. **ClipCandidate-Modell** inkl. Rückweg-Status.
3. **Smarte Clip-Grenzen** um Peaks (Transkript/KI: wo beginnt/endet
   der Gedanke, Hook).
4. **Profile als Datenmodell** — zweigeteilt: *Production-Profil* (fps,
   NLE, Kamera/Mic, LUT, Export, Sync) + *Brand/Social-Profil* (Logo,
   Font, Untertitel, Safe Areas, Formate). Erst Datenvertrag, dann
   simple Exporte, dann schöner Renderer.
5. **Hybrid/NAS-Pilot** (s. u.).
6. **Dann erst** Hub / UI-Revamp. Konkret verankert (Carl-Formulierung,
   2026-05-18, NICHT HC-4-Scope): **„Projekt öffnen/Hub: Zuordnung
   bearbeiten, Archiv zurücksetzen/neu analysieren, Ignoriert-Status
   sichtbar machen."** — d.h. Projekt direkt über `.peakcut` öffnen
   (`load_project_archive` akzeptiert Datei/Ordner/Root bereits);
   bestehende Zuordnung voll hydratisieren + editierbar + neu speichern
   + Review konsistent neu aufsetzen (nur so ist ein „Zurück" sauber,
   Carl: sonst halbe Hub-Funktion mit Edge-Cases); Archiv
   zurücksetzen/neu analysieren; Ignoriert-Status im Review sichtbar
   (vorhandene UI-Lücke, nicht von HC-4 eingeführt).
7. **Danach** Social-Asset / Opus-artiges Modul.

Bewusst NICHT V3-Start: UI-Revamp, Create Mix. **Opus-Score: als
Nordstern eine Falle, als spätes Modul auf besseren Rohdaten ok** —
nicht kopieren, von unten unterlaufen. **Create Mix** kein Flaggschiff
(HM mischt in Pro Tools via CheckIn), höchstens später Preview-Mix für
fremde Teams.

### Deployment-Topologie: Hybrid (KEIN Web-Rewrite)

Interaktives (PyQt, Scrubbing, LUT-Preview, NLE-Nähe) bleibt am
Studio-Mac. NAS = Hintergrund-Rückgrat:
1. NAS-Projektordner wird Wahrheit: `.peakcut/` = State, relative
   Pfade, Assignments, Analyse, ClipCandidates, Profile-Refs.
2. Pro Studio-Mac kleiner Launcher → kein MacBook-Zwang.
3. Headless Worker: `peakcut analyze/export <ordner>` lokal ODER im
   Synology-Container.
4. Web-Hub nur für Status/Queue/Profile/Approval — NICHT Voll-Video-
   Review.
5. Web/Electron erst, wenn wirklich externe Teams bedient werden.

### Geparkt (später)

Descript-API, SRT/Untertitel in XML, Auphonic Mix-Polish, In/Out-Clip-
Editor, voller Social-Renderer, Smart Scan (relevant sobald fremdes
Material zählt), Marker-Export, Einzel-Clip-MP4, Projekt-Metadaten.

**Sprecher-Gegencheck über die Mics** (Max-Idee 2026-05-19, eigener
Roadmap-Punkt, NICHT #3-Scope): Descript-Sprecher-Label gegen
tatsächliche Mic-Aktivität (speaker_activity) abgleichen → fängt
mis-attribuierte/kaputte Sprecher-Labels automatisch ab (defensiv,
„Vertrauen durch Tooling"). PeakCut hat die Mic-Aktivitätsdaten schon.
Eigener kleiner Brainstorm → Spec, bevor gebaut wird.

---

## V3 Vision — Modulare Production Suite (HISTORISCH — überholt 2026-05-18)

> Belassen als Kontext. Die Reihenfolge/Identität gilt **nicht** mehr —
> maßgeblich ist „Produkt-Strategie & Roadmap" oben. Insb. „Kein
> persistenter State" ist überholt: Persistenz ist jetzt der Kern.

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

## Offen / Backlog

> **Todos leben jetzt ausschließlich in [`App/BACKLOG.md`](BACKLOG.md)** — der
> Single Source of Truth (Bugs · Funktions-Ausbau · Fundament & Architektur ·
> Hygiene · Abnahme · offene Entscheidungen · Zukunftsmusik + Erledigt-Historie).
> Hier NICHT mehr doppelt pflegen — sonst laufen die Listen auseinander.
>
> Verwandtes lebt weiter an seinem Platz: **Strategie/Produktrichtung** oben unter
> „Produkt-Strategie & Roadmap", **langfristige Visionen** unten unter „Langfristig
> (V4+)", **abgeschlossene Arbeit + Bau-Provenienz** (Folgenschnitt Stufe 1/2,
> Slice B, #71a, HC-2…5, ClipCandidate, Daten-Riegel, #76) im **Changelog** weiter
> unten. Specs/Pläne erledigter Slices liegen in `docs/specs/archiv/` bzw.
> `docs/plans/archiv/`.

## Langfristig (V4+) — Die großen Visionen

**Nie aus den Augen verlieren.** Bei jeder Architektur-Entscheidung prüfen: Stellen wir hier Weichen für später?

### Produkt

| Vision | Was | Weichen jetzt? |
|--------|-----|----------------|
| **Hardware-Button** | Physischer Marker statt Keyboard (~50-69€) | Keyboard-Erkennung abstrakt halten, nicht auf Piano-Sound hardcoden |

**Lastenheft Hardware-Button (erarbeitet 2026-05-17 mit Max — die
Markt-Recherche ergab: gibt's nicht von der Stange, das IST das
Produkt):**
- Fußbedienung, flaches Bodenteil, unter dem Tisch unsichtbar
  (Folgen werden gefilmt — nichts auf dem Tisch, Moderator drückt
  elegant mit dem Fuß, Körper sichtbar unverändert).
- Auslösung **nahezu lautlos**: kein mechanisches Klack/Klick und kein
  Boden-Dröhnen — Gerät liegt im mikrofonierten Aufnahmeraum, jedes
  Eigengeräusch blutet in die Sprach-Mikros. NICHT vorab gegen ein
  Trigger-Pad entschieden: Empfindlichkeit hoch → leichter Fußtipp
  möglich. Ob der Tipp in die Sprach-Mikros blutet, ist eine
  EMPIRISCHE Frage (2-Min-Test: Sprach-Mikros + Marker-Spur parallel
  aufnehmen, in die Sprach-Mikros reinhören). Startone wird von Matze
  aktiv abgelehnt → echter Ersatz ist aktiver Bedarf, keine Politur.
- Erzeugt **selbst** einen Ton, kurz/knackig, **fester Pegel** →
  immer der lauteste, gut getrennte Impuls auf seiner Spur
  (PeakCut-Schwelle ist relativ zum Spur-Maximum, 0.3×max, min_gap
  12s — kurzer harter Sound = robusteste Erkennung).
- **Ein** Kabel, möglichst balanciert/XLR direkt ins Multicore (ohne
  DI-Box). XLR nicht zwingend, aber Ziel = Kabelsalat weg.
- Robuster, wiederholbarer, eleganter Druckpunkt.
- **Max-Entscheidung 2026-05-17: Roland SPD::ONE KICK** (nicht WAV).
  Grund: **Plug-and-play** für den Alltag — feste eingebaute Sounds,
  kein Sample laden/auswählen, anmachen und treten. Der WAV-Vorteil
  (eigenes Sample) war nur marginaler Erkennungs-Feinschliff; ein
  Kick-Sound ist für PeakCut ohnehin nahezu ideal (kurzer, knackiger,
  breitbandiger Impuls, keine Tonhöhen-Mehrdeutigkeit) → Erkennungs-
  qualität wird NICHT geopfert.
- **Unverändert offen (modell-unabhängig): der akustische Bleed-Test.**
  Kein SPD hat externen Trigger-Eingang (nur OUT + PHONES 6,3 mm +
  USB; kein XLR → DI bleibt). Man MUSS die Gummifläche tippen → ob der
  leise Fußtipp in die Sprach-Mikros blutet, ist die alleinige
  Entscheidungsfrage, gleich für KICK wie WAV. Test auf weicher Matte
  (Körperschall/Boden killen). „KICK genommen" ≠ „erledigt".
- KICK-Spec-Befund (Roland, 2026-05-17): Bedienung über PHYSISCHE
  Knöpfe (INST=Soundwahl, THRES/SENS, POWER) → Knopfstellung bleibt
  per Bau-Prinzip stehen = echtes Plug-and-play, kein Setup pro
  Session. Ausgang Mono 6,3 mm + Phones (ideal für 1 Marker-Spur),
  KEIN XLR (DI bleibt). 22 Sounds + 1 User-Sample-Slot (≤5 s WAV,
  optional, nicht nötig). Strom: 4×AA ODER Netzteil DC9V (separat).
  OFFEN: Auto-Power-Off in Manuals nicht dokumentiert → Empfehlung
  Netzbetrieb (killt Leere-Batterie- + meist Auto-Off-Risiko); vor
  produktivem Verlass am Gerät/Roland-Support gegenchecken.
- Das fehlende Trigger-In bleibt das Kernargument für den eigenen
  Hardware-Button (lautloser Schalter + Tongeber = was dem SPD fehlt).
- Startone ist KEINE Dauerbrücke mehr (Matze will es weg).
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

### Kandidaten quellenunabhängig — v6-Vertrag + zentrale Sicht (feature/kandidaten-quellenunabhaengig, 2026-08-19/20)

Vier-Augen mit Carl (Spec + Gate A), Claude TDD-Bau über 4 Tasks + Abschluss-Review +
Fix-Welle. Ziel: eine „Stelle" (bisher nur vom Fußpedal) wird quellenunabhängig — künftig
auch aus Transkript-Analyse, automatischer Clip-Findung oder von Hand.

- **Task 1 — v6-Vertrag atomar (`4dbdf5e`):** `ClipCandidate` trägt jetzt eine stabile
  Identität (`candidate_id`), ihre Herkunft (`origin` — marker/transcript/auto/manual)
  und einen expliziten Anker (`anchor_ms`, der Sprungpunkt für die Review-Navigation,
  NIEMALS aus `boundary.start_ms` abgeleitet). `peak_id` ist nur noch eine optionale
  Rückreferenz für markergebundene Kandidaten, keine Identität mehr. `.peakcut`-Schema
  v5 → **v6**. `ClipCandidate.from_dict` ist strikt (v6-Pflichtfelder müssen da sein);
  v1–v5-Migration passiert beim Hydrieren in `project_archive.py`, wo `session.peaks`
  vorliegt (Anker = `peak.position_ms`). Kaputte/fremd-hergeleitete Akten scheitern
  kontrolliert statt still umgedeutet zu werden.
- **Task 2 — Reconciliation statt Replace (`4f2289b`):** `load_analysis_results`
  gleicht die Marker-Partition der Kandidatenliste jetzt ab statt sie zu ersetzen —
  Fremdquellen (auto/transcript/manual) und der Bearbeitungszustand bestehender
  Marker-Kandidaten bleiben über eine Reanalyse hinweg erhalten. Atomar: eine
  Kollision (doppelte `candidate_id`) wirft, BEVOR irgendetwas an der Session
  verändert wurde.
- **Task 3 — zentrale Marker-Sicht statt fünf blinder Joins (`2df30fc`):** neues
  Qt-freies Modul `core/candidate_view.py` (`marker_candidates_by_peak_id`,
  `marker_candidate_for_peak`) — die EINE Stelle, die Kandidaten über `peak_id`
  joint. Vorher taten das fünf Stellen blind (XML-Export, Smart-Playback,
  Ignorieren, Grenzen-Pipeline, Web-Serialisierer); ein Fremdkandidat mit
  kollidierender Legacy-`peak_id` konnte dort den Marker-Kandidaten verdrängen,
  im Web-Serialisierer sogar still überschreiben. Schlägt bei Doppelzuordnung
  jetzt FEHL statt einen Treffer zu raten. `build_playback_window` fängt den
  Kollisionsfehler kontrolliert als `disabled_reason` ab (Qt-Slot-Schutz).
- **Task 4 — auto-Kandidat kompletter Datenweg (`b353984`):** Kollisionssicherheit
  End-to-End belegt (Reconciliation → zentrale Sicht → Export/Playback/Ignorieren),
  reales Paritäts-Gate gegen die Ilka-Akte grün.
- **Fix-Welle nach Abschluss-Review (diese Runde):** zweiter Absturzweg geschlossen
  — `review_page.on_ignore` fing `ClipCandidateError` aus `session.ignore_peak()`
  bisher nicht ab (gleicher SIGABRT-Auslöser wie der bereits gefixte Play-Pfad),
  jetzt kontrollierte Statuszeile + Test. Web-Engine (`PeakCut-web/engine/
  engine_core.py`): `candidate_view`-Import von Funktions- auf Modulebene gehoben
  — vorher startete die Engine gegen einen zu alten Kern sauber durch und starb
  erst beim ersten Projekt-Öffnen mit 500 (widersprach der README-Zusage „der
  Bruch ist laut, nicht leise"). Web-README auf v6 nachgezogen + `core/candidate_view`
  in die Modul-Mindestliste ergänzt. Zwei Tests geschärft (waren grün ohne wirklich
  zu prüfen — per Mutationstest belegt): `test_pfad_playback_spielt_nicht_das_
  fremdfenster` prüft jetzt POSITIV die Marker-Boundary statt nur „≠ Eindringling-
  Fenster" (letzteres blieb auch ohne Herkunfts-Filter wahr, weil beide Fälle auf
  ein disabled `(0,0)`-Fenster liefen); `test_v6_ohne_pflichtfelder_wird_abgelehnt`
  verlangt jetzt `ClipCandidateError` allein statt eines Tupels mit `KeyError`.
  Stale Schema-Namen in vier Testdateien korrigiert (v5→v6).
- **Bewusst NICHT in dieser Runde (→ BACKLOG.md):** zwei herkunftsblinde Aggregate
  in `review_page.py` (Sinnabschnitte-bereit-Zähler), fehlende Nachsortierung/
  Eindeutigkeitsprüfung beim Akten-Laden (`project_archive.py`), Namensdrift
  `peak_decisions`/`candidate_decisions`/`CandidateDecision` (33 Fundstellen),
  `main_window.py:280/316` fangen `ClipCandidateError` nicht, offene
  Vertragsfrage ob `peak_id` bei `origin != marker` erlaubt bleiben soll.
- **Reales Risiko geprüft:** Migration an Max' echter Ilka-Akte read-only
  nachgefahren — 31/31 Kandidaten korrekt, Anker == `peak.position_ms`, keine
  inhaltliche Abweichung, Akte-SHA vorher==nachher. KEIN Verlust.
- **909 Kern-Tests grün** (Web: 362 passed/10 skipped/1 deselected), Pin-1
  byte-identisch. Merge-Auflagen aus dem Abschluss-Review: v6 gleichzeitig auf
  `feature/redesign`+`develop`+`main` landen (kein Zweig bleibt zurück),
  Web-Merge zusammen mit dem Kern-Merge, vor dem ersten v6-Schreiben Kopie von
  `2026_Ilka Bessin/1_Material/.peakcut/` wegsichern.

### Core-Extraction Zuordnungs-Datenschicht (develop + feature/redesign, 2026-06-20)

Vorbedingung für den **Web-Zuordnungs-Screen** (Schwester-Repo `PeakCut-web`,
Carl-Fahrplan #4 Slice 1): die Web-Engine ist Qt-frei und kann
`gui/assignment_page.py` (PyQt-Import) nicht laden. Reine Extraktion **ohne
Verhaltensänderung**, damit das Web den Kern *aufruft* statt ihn nachzubauen
(Carl-Invariante „Web ruft nur", kein Drift).

- **Neu `core/folgenschnitt_assignment.py` (Qt-frei):** `AssignmentState`,
  `CameraRow`, `MicRow`, `SHOT_CHOICES`, `NEUTRAL_SHOT_LABEL`,
  `_default_unused_clips_mode`, `build_assignment_state`,
  `preview_start_s_for_mic` — wortgleich aus `gui/assignment_page.py` gehoben.
- `gui/assignment_page.py` importiert diese Symbole zurück (eine Wahrheit);
  Widget/Stylesheets/`make_shot_combo` bleiben in `gui`. Tote Importe entfernt.
- Neuer Qt-freier Kern-Test `tests/test_folgenschnitt_assignment.py` (direkt aus
  `core` importiert, charakterisiert das unveränderte Verhalten). Bestehende
  `test_folgenschnitt_assignment_page.py` **unverändert** grün.
- Keine Umbenennung, keine neuen Defaults, keine Semantik-Glättung.
- **793 Tests grün, Pin-1 byte-identisch.** Auf `develop` (7062e19), nach
  `feature/redesign` gemergt. **Carl-Cross-Review grün (2026-06-20, keine
  P1/P2).** P3: `_default_unused_clips_mode` bewusst NICHT nach `gui`
  zurück-exportiert (kleinere Oberfläche). Slice-1-Auflage (Carl): expliziter
  Test, dass das Qt-freie Engine-venv `core.folgenschnitt_assignment` laden kann.

### Marker + Vergleichbarkeit Keyboardstellen ↔ Sinnabschnitte (develop, 2026-06-18)

Vier-Augen mit Carl (Carl-Plan, Claude-TDD, Max-Abnahme), aus der Philip-Siefer-
Produktion. Ziel: beide XMLs direkt in Premiere vergleichbar machen.

- **Neuer Helfer `core/xml_sequence_helpers.py`:** EINE Wahrheit für Stellennummer
  (`peak.index` → Stelle 1..N über aktive Peaks) + kompakte Record-Positionen +
  Marker. `active_smart_candidates` filtert/sortiert/nummeriert die Smart-Kandidaten
  zentral (raw + smart + Marker hängen sich daran).
- **Keyboardstellen-XML (`exporters.py`):** Sequenz „PeakCut" → **„Keyboardstellen
  raw"**, nummerierte **Bereich-Marker** „Stelle N" (so lang wie die Stelle, lesbar).
- **Sinnabschnitt-XML (`sinnabschnitt_exporter.py`):** von Audio-only auf **kompakte
  Multicam** (Video je Kamera + dieselben Tonspuren wie raw) gehoben, Sequenz
  **„Keyboardstellen smart"**, Clip-Namen = Quelldateien, Marker mit der **gleichen
  Keyboardstellen-Nummer** (löst den `candidate.peak_id`-Versatz durch ignorierte
  Peaks). TXT zählt jetzt auch in Stellennummern. Bleibt eigener Codepfad (nicht in
  `_build_exporters`).
- **Pin-1 bewusst zweimal neu eingefroren** (Marker + Name; dann Bereich-Marker) —
  beabsichtigte Änderung, im Test begründet. Abnahme-Riegel = Max' Premiere-Import
  (bestätigt: Marker lesbar, Bild+Ton, 3 Tonspuren in beiden, Nummern synchron).
- TDD, 785 Tests grün. **Offen:** Carl-Schluss-Review; nächster Slice „Grenzen auf
  Satzanfang/-ende einrasten" (mechanisch, ≠ #70-Aufhänger-Wahl).

### Erste Eigen-Produktion (Philip Siefer) + Sinnabschnitt-Import-Fix (develop, 2026-06-17)

Max hat erstmals seit Langem selbst eine Postproduktion gemacht und PeakCut am
echten Material der Philip-Siefer-Folge benutzt (nicht nur Smoke).

- **Folgenschnitt-XML real bestätigt:** „funktioniert super" — erste echte
  Eigen-Nutzung außerhalb der Smoke-Tests.
- **Sinnabschnitt-XML in Premiere importierbar gemacht** (`core/sinnabschnitt_exporter.py`,
  Commit `64870c0`): Den Audio-Clips fehlten die FCP7-Pflichtangaben (`<duration>`,
  die Datei-Audio-Beschreibung `<media><audio>`, `<sourcetrack><mediatype>audio`),
  darum lehnte Premiere den Import ab. Jetzt aufgebaut wie die funktionierende
  Keyboardstellen-XML: Datei EINMAL voll definiert, danach per id referenziert,
  plus Sequenz-Audioformat. Neuer Test `test_xml_audio_clips_are_premiere_importable`.
  **Eigener Codepfad — nicht in `_build_exporters`, Keyboardstellen-Pfad/Pin-1
  unberührt.**
- **OFFENER FOLGE-BEFUND (in BACKLOG → Bugs):** Die Sinnabschnitt-XML importiert
  jetzt, zeigt in der Timeline aber NUR Ton, kein Bild. Aktuell by-design
  (v1 = leichtgewichtige Ton-Spannenliste), aber Max hat etwas anderes erwartet.
  Erst mit Max klären, was in der Timeline liegen soll, dann entscheiden.
- **Neue Wünsche aus der Produktion (in BACKLOG):** nummerierte Marker in der
  Keyboardstellen-XML (klein); SRT-Untertitel für Premiere (groß, Descript-API
  prüfen).

### Fix-Runde — Python-Pin, Dropdown-Lesbarkeit, Crash auf „Weiter" (develop, 2026-06-16/17)

Carl-Review: keine P1/P2, mergefähig. Drei Korrekturen abseits von #77:

- **Python 3.11 gepinnt:** `.python-version` + weiche Start-Wache
  (`python_version_warning` in `utils.py`) — tickende Uhr pydub/audioop bei 3.13.
- **Shot-Dropdown macOS lesbar (visuell bestätigt):** Das native Popup ignorierte
  das Stylesheet → markierte Zeile war weiß-auf-hellgrau. Fix: nicht-natives Popup
  (`QListView`) + explizite `QListView::item:selected/:hover`-Regeln (blau + weiß)
  in `assignment_page.py`, angewandt auf Shot- UND beide Person-Combos
  (Kamera + Mic). Verifiziert per gerendertem PNG + Pixel-Probe (highlight = #007AFF).
  Max-O-Ton „sah besser aus". Commits `74a18fc`/`6f0fd55`.
- **Crash-Fix auf „Weiter" (SIGABRT):** Hatte eine Kamera einen Personen-Shot
  (Weit/Nah/Halbnah) OHNE zugewiesene Person, warf `CameraAssignment` einen
  ValueError im Qt-Slot → `abort()`. `to_camera_assignments` überspringt jetzt
  unvollständige Personen-Shots statt zu crashen (Altbestands-Bug v2.10, NICHT von
  #77). Commit `f7310d0`.

### #77 Import-Refactor — Strukturteil gebaut, Rest bewusst geparkt (develop, 2026-06-16)

Vier-Augen mit Carl (Carl: Plan + Gate-Reviews, Claude: TDD-Bau, Max: Entscheider).
Plan: `docs/plans/2026-06-16-77-import-refactor-plan.md` (inkl. Scope-Entscheidung).

- **Was gebaut wurde (Tasks 0/1/2/3/4/6, Carl-Review grün):**
  - Eigenes `project.mix_track`-Feld (Mix strukturell getrennt statt nur zur
    Laufzeit aus `mic_tracks` gefiltert).
  - Zentraler Klassifizierer `core/import_classifier.py` als EINE Wahrheit für
    „Mix/Marker/Mic/Transkript/Kamera?" — letzte Heuristik-Insel eingesammelt.
  - `.peakcut` Schema **v4, additiv + rückwärtskompatibel** (`project_archive.py`):
    schreibt `marker_track`/`mix_track`/`transcript_path`, migriert v1–v3.
- **Bewusst ADDITIV, nicht „sauber":** Der Mix bleibt VORERST zusätzlich in
  `mic_tracks`, weil der XMLExporter die Audiospuren noch direkt von dort baut.
  Würde man ihn jetzt strippen, fiele die Mix-Spur aus der Keyboardstellen-XML →
  Pin-1-Bruch. Mein eigener Pin-1-Test hat genau das gefangen.
- **Geparkt:** Task 5 „Mix aus `mic_tracks` strippen" (Pin-1-riskant + kosmetisch),
  Task 7 Import-UI + Task 8 Transcript — bis die Produkt-/Kundenrichtung klar ist
  (Marker-Pflicht? Erkennung per Audio-Inhalt? für wen?). Nächste Energie →
  Produkt-Validierung (#70 + Cutter-Sign-off), nicht weiter am Import.

### Putzfirma — Hygiene-Pass über das ganze Repo (auf develop, 2026-06-16)

Ultracode-Audit (20 Agenten, 5 Dimensionen, adversarial gegengeprüfte Lösch-
Kandidaten) + Umsetzung in 6 getrennten Häppchen, je mit voller Suite (689) +
Pin-1 als Tor. Kein Verhalten geändert, nichts an Pin-1/Export angefasst.
- **Toter Code:** 6 ungenutzte src-Importe + 13 Test-Importe + 2 tote Test-
  Variablen + 4 tote Reste (LUT-`_lookup_table` ~50 MB RAM, write-only
  `_cli_guest`/`_current_video_index`, `field`-Import). 2 verwaiste .pyc weg.
- **Logger-Fix:** `video_preview_peak` schrieb Fehler an den unkonfigurierten
  Root-Logger → jetzt `get_logger("peakcut.videopreview")` (landet in der Log-Datei).
- **Konsistenz:** nackte ffmpeg-Timeouts → benannte Konstanten; englische
  Docstrings der folgenschnitt-Module eingedeutscht; Smart-Boundary-Modell
  `claude-opus-4-7` → `claude-opus-4-8`.
- **Doku/SSOT:** Modul-Diagramm-Fehler (gelöschtes `core/audio.py`) korrigiert;
  feste Testzahlen aus der Doku entfernt (driften sonst); der duplizierte
  ~240-Zeilen-Backlog-Block in CLAUDE.md durch einen Verweis auf `BACKLOG.md`
  ersetzt; 11 erledigte Specs + 4 Pläne nach `docs/{specs,plans}/archiv/`.
- **Bewusst NICHT angefasst (→ Carl bzw. eigene Slices):** 5 nie aufgerufene
  Player-Methoden + `decide_with_brake`-Wrapper (mögliche Schnittstellen),
  Test→`logs/peakcut.log`-Redirect (Logging-Architektur), Heuristik-Inseln (#77).

### #76 Wiedergabe-UX (auf main gelandet 2026-06-16)

Synchrone Ton+Bild-Vorschau zum Beurteilen der Schnittgrenzen. Carl-Plan +
Claude-Cross-Review (`docs/plans/archiv/2026-06-15-wiedergabe-76-plan.md`), TDD,
Gate E/F (Carl) + App-Smoke (Max) bestanden. 593 → 689 Tests, Pin-1 stabil.

- **Architektur:** statt zweier unsynchronisierter Engines (simpleaudio-Ton +
  stummes QMediaPlayer-Bild) jetzt `gui/review_playback_controller.py` —
  eigener Audio-QMediaPlayer als **Master**, Video folgt; bei Drift >
  Toleranz schnappt das Bild auf die Audio-Timeline. Readiness-Gate (beide
  Medien geladen, Timeout) + harte stop()/cleanup() (deleteLater, schließt
  CONC-3 mit). simpleaudio ist aus dem Review-Pfad raus (bleibt nur für
  MicPreviewWorker; play_current entfernt).
- **Kern-Bausteine (Qt-frei):** `core/playback_modes.py` (key/speak/smart),
  `core/playback_windows.py` (Fenster pro Modus, Smart-disabled wenn kein
  Kandidat), `core/playback_audio_source.py` (Key=Keyboard, Speak/Smart=Mix;
  ohne Mix gecachte Vorschau-WAV mit Mic-Quellen-Fingerprint).
- **Modus-Zyklus** über den Mode-Button (key→speak→smart), persistiert in
  `config.playback_mode`; kein Auto-Play mehr bei Navigation/Moduswechsel.
- **Drift-Schwelle 100ms** (provisorisch): der Spike
  (`scripts/verify_qmediaplayer_position_resolution.py`) zeigte
  position()-Kadenz ~50-100ms auf macOS → 40ms unter dem Granularitätsboden.
  Korrigierter Restdrift an echter Folge ≤85ms (`verify_playback_sync_real.py`).
- **Play ab Scrub-Stelle (A):** nach echtem Scrub setzt Play dort auf
  (speak/smart auf der vollen Mix-Spur: innerhalb des Clips bis Clip-Ende,
  dahinter frei bis Medienende). **KEY bleibt immer beim Marker-Clip** — die
  Key-Tonquelle ist ein kurzer Klick-Track ohne Episoden-Timeline (Produkt-
  entscheidung Max+Carl). Resume nur bei echtem Scrub (`_scrubbed_pos`-Flag),
  nicht über die unzuverlässige async-Position.
- **Geparkt/offen:** finale Drift-Schwelle nach mehr Real-Material; optionale
  defensive Klemmung von media_start gegen Quellendauer; Slider-Click-to-Seek
  (ScrubSlider) als spätere UX-Politur.

### Daten-Integritäts-Riegel (auf main gelandet 2026-06-15)

Erstes Paket nach dem Fundament-Health-Check
(`docs/specs/2026-06-15-state-of-peakcut-health-check.md`, Urteil mostly-solid).
Carl-Plan + Claude-Cross-Review (`docs/plans/archiv/2026-06-15-data-integritaets-riegel.md`),
TDD, getrennte Commits + Gates. 593 → 621 Tests grün, Pin-1 byte-identisch stabil.

- **DATA-1 (`7f032ad`):** neues neutrales Modul `core/atomic_io.py`
  (`write_json_atomic`: tmp im selben Ordner → flush → fsync → `os.replace`
  → best-effort dir-fsync; bei Abbruch tmp weg, alte Datei byte-identisch).
  `save_project_archive` + `write_transcript_json` laufen darüber — ein Abbruch
  mitten im Schreiben kann die zentrale `.peakcut/project.json` nicht mehr
  truncieren (Risiko steigt auf NAS, G3).
- **DATA-2 (`f6e9054`):** Schema-Versions-Policy. Zukunfts-Akte
  (schema_version > CURRENT) wird beim **Laden** abgelehnt UND beim
  **Speichern** nicht überschrieben (`_assert_archive_write_allowed` prüft die
  vorhandene Datei) — sonst schneidet ein älterer Client beim nächsten Autosave
  neuere Felder still weg. Bewusste Vertragsänderung: der alte „future loads
  best effort"-Test ist gesplittet (Zukunft lehnt ab, uralt lädt).
- **KI-2 (`3f86de8`):** R2-Ausricht-Riegel zentral in `prepare_smart_boundaries`.
  Drift (Text-Spanne vs. Audiodauer > Toleranz) → `INFRA_FEHLT`, Decider nicht
  aufgerufen, keine Kandidaten/Scores → die G5-`peak_decisions`-Sammlung wird
  nicht mit zeitlich falschen Sinnabschnitten vergiftet. Nutzt die bestehende
  `INFRA_FEHLT`-Semantik (kein neuer Contract).
- **AUD-1a (`2875fa0`):** `speaker_activity._is_speaker_mic_candidate` erkennt
  Mix über den zentralen `audio_routing.is_mix_track` (token-bewusst) statt
  naivem `'mix' in basename` — `mixer_recording.wav` nicht mehr fälschlich als
  Mix ausgeschlossen. keyboard/keys/klavier bleiben lokal bis #77;
  `guest_name`/`_categorize_files` unangetastet (Pin-1/#77).

Bewusst NICHT hier: Export-Orchestrierung raus aus GUI (ARCH-1 → vor NAS),
großer Klassifizierer-Merge + `_categorize_files`/`guest_name` (→ #77).
**Gelandet 2026-06-15:** Carl-Schluss-Review grün (P3 eingearbeitet); Premiere-Smoke
(Slice B, beide Varianten) + App-Smoke (echte Akte: v2 laden → v3 atomar speichern →
neu laden) bestanden. Gemeinsam mit Slice B nach main gemergt.

### Slice B — Multi-Track-Folgenschnitt-XML (auf main gelandet 2026-06-15)

Aus dem Fremdmaterial-Test (1plus1, Mälzer/Ullrich) entstandener Slice: die
Folgenschnitt-XML schreibt jetzt pro Kamera eine eigene Video-Spur — V1 Totale
durchgehend als Sicherheits-Unterlage, V2/V3 Personen mit Lücken (Premiere
„oberste sichtbare gewinnt", Overlay-Variante) — und Audio = Mix-only (kein
Phasing in der Timeline; Fallback auf echte Mics nur ohne Mix). Default-Mode =
disable (deaktivierte statt entfernte Clips), über die Zuordnungs-Seite auf
remove umschaltbar. `.peakcut` Schema-v3 (`folgenschnitt_unused_clips_mode`)
rückwärtskompatibel. Carl-Plan + Claude-Cross-Review
(`docs/specs/archiv/2026-06-03-multitrack-folgenschnitt-xml-design.md`), TDD über
9 Tasks (Aufteilung: Claude Datenstruktur/UI ↔ Carl XML-Writer), Pin-1
durchgehend byte-identisch. Premiere-Smoke beider Modi + Carl-Schluss-Review
bestanden; gemeinsam mit dem Daten-Integritäts-Riegel nach main gemergt.
593 Tests grün vor Merge.

### #71a Audio-Routing-Mini-Slice (auf main gelandet 2026-05-25)

Phasing-Wurzel-Fix für den Keyboardstellen-Cutter-MP3 und die Review-
Speak-Mode-Wiedergabe. Diagnose 2026-05-21 (Carl-Cross-Review von
#76-Plan): Mix-Datei landet beim Import in `project.mic_tracks` (alles
außer `keyboard/keys/klavier` → Mic). MP3Exporter und
`session.play_current` Mic-Mode overlay-summierten `mic_audios[0]` +
`mic_audios[1:]` — d.h. der ProTools-Mix wurde on-top zu allen Einzel-
Mics drauf-overlayt, jeder Sprecher doppelt addiert, Phasing landete
im Output an Matze/Cutter.

Carl-Fahrplan B-prime statt voller Import-Refactor: zentraler
Helfer `core/audio_routing.py` als eine Wahrheit für Mix vs. echte
Mics, alle Hör-/Renderpfade hängen sich daran auf, XML-Pfade und
`.peakcut`-Schema unangetastet bis #77.

- **Helfer:** `is_mix_track` (Token-Heuristik via
  `re.split(r'[^a-z0-9]+', stem.lower())` + `{"mix", "mixdown"}` —
  fängt False-Positives wie `mixer_recording.wav` ab),
  `get_mix_track`, `get_source_mic_tracks`, `get_speech_audio_segment`
  (Mix vorhanden → Mix allein; sonst Overlay echter Mics; bei
  `mic_tracks`/`mic_audios`-Längen-Mismatch → `None` statt versteckt
  falsches Audio).
- **Consumer umgehängt:** MP3Exporter, `session.play_current`
  Mic-Mode, AssignmentPage (Mix-Filter), SinnabschnittExporter-
  Fallback. `project.get_reference_track` delegiert ebenfalls an
  `audio_routing.get_mix_track` → eine Wahrheit auch für die
  Smart-Boundary-Pipeline und den XML-Probe-Pfad (ohne XML-Bytes
  zu ändern).
- **Pin-Garantien (alle stabil):** Pin-1 Keyboardstellen-XML
  byte-identisch (SHA-256-Hash in
  `tests/test_audio_routing_safety.py`), Pin-2 HC-2-Lifecycle,
  Pin-3 `.peakcut`-Schema unverändert, Pin-Gastname (alte
  `guest_name.py`-Heuristik unangetastet → kein Drift im
  XML-Dateinamen).
- **Production-Quickfix** vom 2026-05-21 (Mid-Slice für laufende
  Produktion, Commit 3c8d6ba) wurde in Task 3 sauber durch den
  Helper-Pfad ersetzt.
- **Parallel-Workflow** mit Carl etabliert: Plan-Cross-Review
  (P1/P2/P3-Befunde wechselseitig), Task-Aufteilung 3+4 (Claude
  Hör-Pfad) ↔ 5+6 (Carl UI + Sinnabschnitt-Fallback), Schluss-
  Cross-Review von Carl 2026-05-25 grün ohne P1/P2.
- **Real-Smoke:** Max-O-Ton „kein Phasing mehr" auf produzierter
  Folge nach dem Refactor. `scripts/verify_audio_routing_real.py`
  liefert pro Akte einen Routing-Report und optional drei
  Vergleichs-WAVs (Mix-allein vs. Pre-#71a-Reproduktion vs.
  nur-echte-Mics).
- **519 → 519 + 64 Pin-Tests** grün vor Merge.
- **P3-Backlog für #77 (Carl-Schluss-Review-Befund):**
  `speaker_activity.py:49` hat noch eigene Substring-Heuristik
  („mix"/„keyboard"/…), Analyse-Defensiv-Pfad nicht Render-Pfad —
  sollte beim Import-Refactor auf den zentralen Klassifizierer
  ziehen. Plus: `verify_audio_routing_real.py` benennt Debug-WAVs
  immer `mix_only.wav`, auch wenn Quelle echte Mics sind —
  quellenabhängiger Name wäre sauberer.

Merge-Range: `728abca..17b5aad` (9 Commits, Aufteilung Claude/Carl
siehe Commit-Autoren).

### Roadmap #2 — ClipCandidate + Rückweg (auf main gelandet 2026-05-18, Merge d8d9e33)

Erstes Produktobjekt im `.peakcut`-Gedächtnis. `core/clip_candidates.py`:
`ClipBoundary`/`ClipCandidate`/`PeakDecision` (frozen, roundtrip-exakt),
> **Nachtrag 2026-08-23:** `PeakDecision` heißt seit dem Kandidaten-Umbau
> `CandidateDecision` und hängt an `candidate_id` statt an `peak_id`; der
> Übergangs-Alias ist mit Gate B ersatzlos entfernt. Der Rest dieses
> Eintrags bleibt als Historie stehen.
Statusmaschine `proposed→selected→produced→published→discarded`
(published terminal v1), `PeakDecision` selbst-validierend.
Bootstrap je Peak in `load_analysis_results` (ignoriert→discarded);
`ignore_peak` koppelt via `Peak.index` → discarded + `PeakDecision`
(source=ignore_peak), idempotent. `.peakcut` Schema **v2** additiv
(`clip_candidates`/`peak_decisions` optionale Sektionen, v1+v2
tolerant, v1-Akte bootstrappt; kaputte v2 → `ProjectArchiveError`,
HC-4-Robustheit erhalten). Keyboardstellen-XML byte-identisch
(Metadaten, kein Export-Einfluss). Erster echter Rückkanal über das
bestehende Ignorieren (kein neuer GUI-Code). Carl-Plan + Schluss-
Review grün (Gate-A-P2 + Schluss-P2), Gate-F-App-Smoke an echtem
HR-Material bestanden. 243 → 261 Tests. Nächster Roadmap-Schritt:
#3 smarte/KI-Clip-Grenzen.

### HC-4 — .peakcut-Projektakte (auf main gelandet 2026-05-18, Merge 317a576)

PeakCut bekommt Gedächtnis: Lauf speichern + wieder laden statt erneut
analysieren. `core/project_archive.py` über bestehenden
`load_analysis_results`-Vertrag; relative Pfade (verschiebbar, inkl.
aller Assignment-Listen — Carl-P1-Fix); Peak-Round-Trip exakt;
speaker_activity per CSV-Referenz; Keyboardstellen-XML byte-identisch
nach Save/Load. Minimale GUI-Einhängung (Akte gefunden → Analyse
überspringen; guarded Autosave nach Analyse/Zuordnung/Ignorieren/
Schließen). Ohne `.peakcut` unverändertes Verhalten. Carl-Plan +
Schluss-Review grün (P1 nachgezogen), Max-App-Smoke an echtem
HR-Material bestanden. 221 → 243 Tests. UX-Punkte (Zuordnung-Edit/
Archiv-Reset/Ignoriert sichtbar) bewusst Hub-Schritt (Roadmap), nicht
HC-4. Damit ist der Roadmap-Schlussstein (das Produktions-Gedächtnis)
gelegt.

### HC-3 (auf main gelandet 2026-05-18, Merge 7c1bd8e)

Sync liest im schnellen Pfad nur das 10-Min-Fenster statt der vollen
Datei (`load_audio_as_array` echtes `sf.read(frames=)`); volle
Referenz/Target nur beim Confidence-Fallback, Referenz lazy + Lock
(1× bei parallelen Kameras). RAM-Peak bei langen Folgen × N Kameras
weg. Offsets bit-identisch — Tests (Identität + Fallback==Legacy) UND
echte HR-Folge (alle 3 Kameras framegenau == akzeptierte alte XML,
Fallback real geübt, `scripts/verify_hc3_sync_real.py`). Carl-Plan,
Carl-Schluss-Review grün. `core/session.py` + `calculate_offset` +
Konstanten/Signatur unberührt. 215 → 221 Tests. Carl-Restnotiz
(ffmpeg extrahiert weiter volle Temp-WAV) bewusst out-of-scope →
geparkt an HC-5 (Audio-Schicht).

### Härtung-Welle (auf main gelandet 2026-05-17, Merge b81d7ab; Versionslabel = Max-Entscheidung)

Aus dem 2-Pass-Health-Check (Carl + Claude unabhängig). Marker-Commit
`b81d7ab` (3395ecd..b81d7ab), 215 Tests grün, CI grün am echten
Runner, echter App-Smoke-Test durch Max bestanden (Analyse/
Screenshots/LUT/Close). `core/` + Folgenschnitt-Leitplanke unberührt.

- **LUT hinzufügen** (Review-Seite „LUT +"): Datei-Dialog →
  Validierung mit echtem Parser → in `luts/` kopieren; Kollision-
  Rückfrage, IO-/Permission-Schutz (read-only Bundle). 4-Augen-
  Post-Review Carl grün.
- **HC-1:** XML-Escaping-Bug im produktiven Keyboardstellen-Export
  behoben (Gastname/Dateiname mit `&`/`<`/`>`); veralteter
  Zuordnungs-Hinweis korrigiert; Build/Spec-Versionsdrift als
  STALE-PARKED markiert + dokumentiert.
- **HC-2 (höchste Konfidenz, Carl-Plan):** Worker-/Subprocess-
  Lifecycle gehärtet — faktisch toter Frozen-/Multiprocess-Timeout
  repariert (Deadline vor Pollschleife, exitcode=None kontrolliert),
  öffentliche `request_stop()`-API, `closeEvent` ohne Prozess-
  Interna, `ScreenshotWorker` cancelbar + non-blocking Cleanup.
  Carl-Schluss-Review grün (P2 nachgezogen).
- **CI-Fix:** `libegl1`/`libgl1` ergänzt — CI war seit Tagen still
  rot (PyQt6-Import scheiterte auf dem Runner, jeder Commit „failed").

### v2.11.0 (Stufe 2 — auf main gelandet 2026-05-17; Versionslabel = Max-Entscheidung) — Folgenschnitt Stufe 2 / Track 1

**main-Merge 2026-05-17:** `--no-ff` Marker-Commit `3395ecd`
"Folgenschnitt Stufe 2 + v1-Kalibrierung — Feature gelandet"
(26f8097..3395ecd), 197 grün auf main, zurück auf develop. Carl
redaktionell grün + Max-Go. v1-Zahlen bewusst PROVISORISCH — Alex-
Sichtung + Fremdproduktion sind erwartete Real-Bestätigungen, können
einen kleinen Tunables-Nachdreh auslösen (kein Regressionsrisiko: Stufe
1 regression-gesperrt, Track 2/KI fasst die Logik ohnehin nochmal an).

Deterministische Zeitlogik-Auflockerung als Schicht ÜBER Stufe 1
(unverändert). 4-Augen mit Carl (Plan + Snap-Delta), Claude TDD-Bau,
Max Entscheider. Spec: `docs/specs/archiv/2026-05-16-folgenschnitt-stufe2-track1-design.md`.

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
- **v1-Kalibrierung (2026-05-17, Carl-Ruling, Max-Go):** Schätz-Parser
  `scripts/analyze_fcpxml.py` (Carl-Spec, NICHT autoritativ) liest messy
  Premiere-FCPXML rückwärts. Confidence-Gate + **Plausibilitätsbremse**
  (dominante Kamera ≥80%, längster Run ≥20×P75 oder ≥20min, <30 Runs bei
  >60min → LOW). Auf Alex' Realfiles: Schirach HIGH/brauchbar, Hüther
  LOW/verworfen (las Basis-Assembly, nicht den Schnitt). Aus Schirach
  (P75 ~49s Halte-Decke) v1-Zahlen moderat gesenkt: min_block_to_loosen
  120→90s, first 110→70s, target 90→55s, min_block 50→35s, totale_block
  25→20s. **Neu-Verifikation an echter Folge erledigt** (Hartmut Rosa,
  gecachte Analyse, `scripts/verify_folgenschnitt_recut.py`, OLD-Lauf
  reproduziert bestehende XML exakt): max-Block 118s→89s, Blöcke >90s
  26→0, Clips 325→347, Schnitte/Min 1,95→2,08 (Median 16,4→19,7 weil
  Über-90s-Blöcke zu 35–55s-Blöcken zerlegt, nicht "alles kürzer").
  **Offen vor main-Merge: Carl-Review des Ergebnisses + Max-Go.**
  Tests 182 → 197.

### v2.10.0 (2026-05-16) — Generischer Zuordnungs-Schritt (Folgenschnitt produktiv)

*Versionslabel vorläufig — finale Nummer ist Max' Entscheidung.*

Folgenschnitt Stufe 1 in der App bedienbar gemacht und das Datenmodell von
Hotel-Matze-fest auf produktionsunabhängig generalisiert. 4-Augen mit Carl
(Plan), Claude (TDD-Bau), Max (Entscheider). Gate A bestanden. Spec:
`docs/specs/archiv/2026-05-16-zuordnung-generisch-design.md`.

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

*Zuletzt aktualisiert: 2026-08-23 (Carl-Gate B gruen, Vertrag eingefroren, gemeinsamer Merge Kern+Web freigegeben; Bau 2026-08-19/21 auf feature/kandidaten-quellenunabhaengig: Kandidaten quellenunabhängig — `.peakcut`-Schema v5→v6, `ClipCandidate` trägt jetzt `candidate_id`/`origin`/`anchor_ms` (optionales `peak_id`), Reconciliation statt Replace, zentrale Marker-Sicht `core/candidate_view.py` statt fünf blinder Joins. Fix-Welle danach: zweiter Absturzweg `review_page.on_ignore` geschlossen, Web-Engine-Import `candidate_view` auf Modulebene gehoben, Web-README auf v6 nachgezogen, zwei stumpf gewordene Tests per Mutationstest geschärft, aufgeschobene Punkte in BACKLOG.md gerettet. 909 Kern-Tests grün, Web 362 grün, Pin-1 stabil, reale Ilka-Akte read-only migrationsgeprüft (31/31 korrekt, SHA vorher==nachher). Davor 2026-06-20: Core-Extraction der Zuordnungs-Datenschicht nach `core/folgenschnitt_assignment.py`. Todos in App/BACKLOG.md.)*
