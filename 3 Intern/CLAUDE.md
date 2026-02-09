# CLAUDE.md

Das zentrale Entwickler-Dokument für PeakCut. Enthält alles was Claude Code (und Entwickler) wissen müssen.

---

## ⚠️ AKTUELLER STATUS (2026-02-06)

**ACHTUNG: Uncommitted Changes!**

Die App wurde radikal vereinfacht nach einer Debug-Session mit vielen Crashes.

**Aktueller Stand:**
- UI vereinfacht: Welcome → Analyse (warten) → Peak Review
- Analyse läuft in separatem Subprocess (`core/analysis_process.py`)
- Screenshots-Feature temporär entfernt
- Clip-Editing-Feature temporär entfernt
- Audio-Video-Sync noch nicht perfekt

**Siehe:** `DEV_NOTES_2026-02-06.md` für alle Details der Debug-Session.

**Nächste Schritte:**
1. Testen ob Export (MP3/TXT/XML) funktioniert
2. Audio-Sync verbessern
3. Wenn stabil → committen
4. Optional: Screenshots/Clip-Editing sauber neu bauen

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
├── main_pyqt.py              # PyQt6 Entry Point (Single-Instance Lock)
├── core/                      # Core Logic (Class-basiert, keine GUI-Abhängigkeiten)
│   ├── project.py             # PeakCutProject - Datei-Abstraktion
│   ├── session.py             # PeakCutSession - State Management + Qt Signals
│   ├── peak.py                # Peak Datenmodell (position_ms, in/out points)
│   ├── exporters.py           # MP3/XML/TXT Exporter (Pluggable Pipeline)
│   ├── audio.py               # Peak Detection + Audio Playback (pydub + simpleaudio)
│   └── sync.py                # Video-Audio Sync (Cross-Correlation)
├── gui/
│   ├── main_window.py         # Hauptfenster: 2-Phasen UI + Mode-System
│   ├── apple_style.py         # macOS Dark-Theme Stylesheet + COLORS dict
│   ├── video_preview_peak.py  # Reiner Video-Player: QMediaPlayer + LUT + Async Screenshots
│   └── peak_timeline.py       # 3 Timeline-Widgets: ScrubTimeline, PeakStrip, ClipTimeline
├── lib/
│   └── lut_processor.py       # LUT Trilinear Interpolation (numpy)
├── config.py                  # JSON Config Management (lazy-loaded)
└── utils.py                   # Pfade (MATERIAL_DIR, EXPORT_DIR, LUTS_DIR)
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
        ├── gui/apple_style.py        (COLORS dict, get_stylesheet())
        ├── gui/video_preview_peak.py  (PeakVideoPreview — reiner Player)
        │     └── lib/lut_processor.py
        ├── gui/peak_timeline.py       (ScrubTimeline, ClipTimeline)
        ├── core/project.py
        ├── core/session.py
        │     ├── core/peak.py
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

| Taste | Aktion | Kontext |
|-------|--------|---------|
| `→` | Next Peak | Peaks-Modus, nach Analyse |
| `←` | Previous Peak | Peaks-Modus, nach Analyse |
| `Space` | Play / Pause | Workspace |
| `[` | Set In Point | Peaks-Modus, nach Analyse |
| `]` | Set Out Point | Peaks-Modus, nach Analyse |
| `r` | Reset Clip | Peaks-Modus, nach Analyse |

Shortcuts sind deaktiviert wenn das Kamera-Name-Feld fokussiert ist.

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

## Aktuelles UI-Design (v2.1-dev, Stand 2026-02-05)

### 2-Phasen UI

Die App hat zwei Phasen, gesteuert über einen `QStackedWidget`:

| Phase | Seite | Inhalt |
|-------|-------|--------|
| **Welcome** | 0 | Zentrierter "PeakCut" Titel + "Import Files" Button. Sonst nichts. |
| **Workspace** | 1 | Video-Player + Timelines + Controls. Wird sofort nach Datei-Import angezeigt. |

Es gibt **keine Summary-Page** mehr — nach dem Import geht es direkt in den Workspace.

### Workspace Layout (von oben nach unten)

```
┌──────────────────────────────────────────────────────┐
│ [Peaks] [Screenshots] [📷]  Kamera:[▼ name]  LUT:[▼]│ ← Top-Bar
│ ┌──────────────────────────────────────────────────┐ │
│ │                                                  │ │
│ │              VIDEO PLAYER                        │ │
│ │           (kein Rahmen, direkt)                   │ │
│ │                                                  │ │
│ └──────────────────────────────────────────────────┘ │
│ In: 01:23:05 [Set In] [====|####|====] [Set Out] Out│ ← Timeline (Peak- oder Screenshot-Modus)
│ [◀][▶] [Play] | 01:23 / 02:15 | [Ignore]  KB 3/47  │ ← Toolbar (oder Analyse-Indikator)
│                Analysiere...                         │ ← Statusbar
└──────────────────────────────────────────────────────┘
```

### Mode-System: Peaks vs. Screenshots

Zwei Modi, schaltbar über Tab-Buttons in der Top-Bar:

| Modus | Timeline | Zweck | Besonderheiten |
|-------|----------|-------|----------------|
| **Screenshots** | `ScrubTimeline` (full-duration, 44px) | Durch gesamte Aufnahme scrubben, Screenshots machen | 📷-Button sichtbar, Toolbar immer sichtbar |
| **Peaks** | `ClipTimeline` (gezoomt ±30s, 44px) + In/Out Controls | Clip-Editing pro Peak | 📷-Button versteckt, Toolbar erst nach Analyse sichtbar |

**Wichtig**: Der Peaks-Modus zeigt vor Abschluss der Analyse **keine Controls** — nur einen Analyse-Indikator mit geschätzter Restzeit. Nach Analyse-Ende erscheinen Timeline + Toolbar automatisch.

### Widget-Struktur Workspace

```
workspace_page (QWidget)
└── QVBoxLayout
    ├── top_bar (QHBoxLayout)
    │   ├── tab_peaks (QPushButton)
    │   ├── tab_screenshots (QPushButton)
    │   ├── screenshot_btn (QPushButton, 📷, nur in Screenshots-Modus sichtbar)
    │   ├── Spacing
    │   ├── cam_label + video_combo (QComboBox, editable → Kamera-Name)
    │   ├── Stretch
    │   └── lut_label + lut_combo (QComboBox)
    │
    ├── video_preview (PeakVideoPreview, stretch=1)
    │
    ├── timeline_stack (QStackedWidget)
    │   ├── Page 0: peak_page — ClipTimeline + In/Out Labels + Set/Reset Buttons
    │   └── Page 1: scrub_page — ScrubTimeline
    │
    └── bottom_stack (QStackedWidget, 36px)
        ├── Page 0: analysis_page — Status-Text + Geschätzte Restzeit
        └── Page 1: toolbar_widget — ◀ ▶ Play | Time | Ignore | KB | 3/47 | Export
```

### Timeline-Widgets (peak_timeline.py)

| Widget | Höhe | Sichtbar | Beschreibung |
|--------|------|----------|--------------|
| `ScrubTimeline` | 44px | Screenshots-Modus | Full-Duration, Drag-to-Scrub, Peak-Marker (faint), Time-Labels, Playhead |
| `ClipTimeline` | 44px | Peaks-Modus | Gezoomt ±30s um Peak. Große In/Out-Marker (grün/rot, 6×30px) draggbar. Blaue Clip-Region. Orange Peak-Zentrum. 5s-Ticks mit Labels alle 10s. Min-Clip: 1000ms. |
| `PeakStrip` | 20px | **Aktuell unbenutzt** | Dünner Strip für Full-Duration Peak-Übersicht (existiert im Code, nicht eingebunden) |

### Video-Player (video_preview_peak.py)

Reiner Video-Player ohne eingebettete Controls:

- **QMediaPlayer** + **QVideoSink** für Frame-Interception
- **LUTWorker** (QThread): Verarbeitet Frames off-main-thread mit LUT (Trilinear Interpolation)
- **ScreenshotWorker** (QThread): Async Screenshots via ffmpeg + PIL + LUT
- **Deferred Play**: `play_from(in_ms, out_ms)` — wenn Video noch nicht geladen, wird der Play-Befehl gespeichert und nach `durationChanged` ausgeführt
- **Clip-Playback**: Stoppt automatisch am Out-Point (`_on_position_changed`)
- Kein eigenes UI — nur ein `QLabel` für Video-Display (schwarzer Hintergrund)

### Analyse-Flow

```
1. User klickt "Import Files" → Datei-Dialog
2. Dateien werden kategorisiert (keyboard/mics/videos)
3. Falls Keyboard nicht auto-erkannt → Dialog zur Auswahl
4. Dateien nach 1 Material/ kopiert (falls nötig)
5. → Workspace wird angezeigt (Screenshots-Modus)
6. → Video wird geladen, Screenshots sofort möglich
7. → AnalysisWorker startet im Hintergrund
8.   → session.analyze(): Sync (falls Videos) + Peak Detection
9.   → Status-Updates via session.status_update Signal
10.  → Geschätzte Restzeit basierend auf Dateigrößen
11. → Analyse fertig: Wechsel zu Peaks-Modus, navigate_to_peak(0)
12.   → Video spielt automatisch von In bis Out
```

### Signal-Ketten

**Peak-Navigation:**
```
next_btn.clicked → _on_next() → navigate_to_peak(index)
  → session.set_current_peak(index)
  → clip_timeline.set_peak(pos, in, out)
  → scrub_timeline.set_current_peak(index)
  → in_label/out_label/peak_label aktualisieren
  → video_preview.play_from(in_ms, out_ms)
  → play_pause_btn.setText("Pause")
```

**Clip-Editing (Drag):**
```
clip_timeline.clip_in_changed(ms)
  → session.adjust_clip(idx, in_ms=ms)
  → video_preview.set_position(ms)
  → in_label aktualisieren
```

**Screenshot (Async):**
```
screenshot_btn.clicked → _on_capture_screenshot()
  → screenshot_btn disabled, Status "Screenshot..."
  → video_preview.capture_screenshot_async(camera_name)
  → ScreenshotWorker startet (ffmpeg + PIL + LUT)
  → screenshot_done Signal → Button re-enabled, Status zeigt Dateiname
```

### Kamera-Namen

- `video_combo` ist **editierbar** — dient gleichzeitig als Kamera-Wähler und Name-Eingabe
- Default-Name: Dateiname ohne Extension (z.B. "C0001" für "C0001.MP4")
- `activated` Signal für Kamera-Wechsel (nicht `currentIndexChanged`)
- `textEdited` Signal für Name-Eingabe
- Namen werden in `_camera_names` dict gespeichert (video_path → name)
- Screenshots nutzen den Kamera-Namen: "Matze 1.jpg", "Matze 2.jpg", etc.

---

## Bekannte UX-Probleme (Stand 2026-02-05)

> **Kontext**: Das UI wurde in mehreren Iterationen gebaut und fühlt sich noch nicht "richtig" an.
> Der Eigentümer möchte das UI mit einem UX-Designer oder erfahrenen Frontend-Entwickler besprechen.

### Offene UX-Fragen

1. **Gesamtlayout fühlt sich unausgewogen an** — Die Anordnung von Tabs, Video, Timeline, Toolbar wurde mehrfach umgebaut. Es fehlt ein durchdachtes Design-Konzept (Figma/Sketch) bevor weiter im Code iteriert wird.

2. **Zwei Timeline-Modi sind konzeptuell unklar** — ScrubTimeline (Screenshots) vs. ClipTimeline (Peaks) sind funktional unterschiedlich, aber visuell/konzeptuell nicht klar genug getrennt. Der Modus-Wechsel per Tabs ist nicht intuitiv.

3. **Screenshot-Workflow** — Der 📷-Button ist jetzt oben, aber der gesamte Screenshot-Workflow (Kamera wählen → Position finden → Screenshot → nächste Position) könnte als zusammenhängender Flow designt werden.

4. **Peak-Review-Workflow** — Navigation (◀ ▶), Playback (Play/Pause), Clip-Editing (In/Out) und Bewertung (Ignore) sind alle in einer flachen Toolbar. Könnte besser gruppiert/priorisiert werden.

5. **Analyse-Wartezeit** — Geschätzte Restzeit ist implementiert, aber die Wartezeit selbst ist lang bei großen Dateien. Der User kann während der Analyse nur Screenshots machen — kein Feedback ob Analyse "fast fertig" ist.

6. **Kein visuelles Feedback bei Aktionen** — Screenshot-Erfolg nur in Statusbar (leicht zu übersehen). Clip-Änderungen haben kein Undo. Ignore hat keine visuelle Markierung im Timeline.

### Empfehlung

Bevor weitere Code-Iterationen am UI gemacht werden:
- [ ] **Figma-Mockups** erstellen mit einem UX-Designer (idealerweise mit macOS/Desktop-Erfahrung)
- [ ] **User-Testing** mit einem echten Podcast-Editor (nicht dem Entwickler)
- [ ] Design-System definieren: Spacing, Typografie, Farbhierarchie, Interaktionsmuster

---

## TODO

### Aktuell offen (Priorität)
- [ ] **UX-Review mit Designer** — Gesamtlayout, Workflows, Interaktionsmuster
- [ ] **Multiprocessing für Video-Sync** — Sync ist langsam bei großen Dateien
- [ ] EDL/XML in Premiere testen — Format validieren

### Mittelfristig
- [ ] Smart Scan: Ordner wählen statt einzelne Dateien
- [x] ~~Clip Editor: In/Out Points anpassen~~ (implementiert via ClipTimeline + Peak Datenmodell)
- [ ] Undo/Redo für Clip-Editing
- [ ] Profile System
- [ ] Batch Processing (Session pro Projekt)

### Langfristig (V4)
- [ ] Electron App + Python Engine + Cloud Backend
- [ ] Machine Learning für automatische Clip-Vorhersage
- [ ] Hardware: Physischer Marker-Button

---

## Changelog

### v2.1.0-dev (2026-02-05) — UX Redesign (WIP)
- **2-Phasen UI** — Welcome → Workspace (Summary-Page entfernt)
- **Mode-System** — Peaks-Modus (ClipTimeline) + Screenshots-Modus (ScrubTimeline)
- **ClipTimeline** (NEU) — Gezoomte ±30s Ansicht mit großen draggbaren In/Out-Markern
- **ScrubTimeline** (NEU) — Full-Duration Timeline für Screenshot-Workflow
- **Video Auto-Play** — Peak-Navigation spielt automatisch von In bis Out
- **Async Screenshots** — ScreenshotWorker (QThread), UI bleibt responsiv
- **Deferred Play** — play_from() wartet auf Video-Load bei noch nicht geladenem Video
- **Peak Datenmodell** — `Peak` Klasse mit position_ms, in/out_point_ms, ignored Flag
- **Kamera-Name als Combo** — Editable QComboBox (Wähler + Name-Eingabe in einem)
- **Default Kamera-Namen** — Dateiname ohne Extension statt leer
- **Analyse-Indikator** — Geschätzte Restzeit, Controls versteckt bis Analyse fertig
- **Mode-Tabs oben** — Peaks/Screenshots Tabs in der Top-Bar über dem Video
- **Clean Shutdown** — closeEvent() stoppt LUT-Worker und wartet auf Threads
- **Bugfixes**:
  - `from_wav()` → `from_file()` (Crash bei MP3-Dateien)
  - Race Condition bei Video-Load + play_from() behoben
  - Kamera-Wechsel: `activated` statt `currentIndexChanged` Signal
  - Focus-Handling: ClipTimeline mit ClickFocus Policy
- **Status**: UI funktional aber UX-Design braucht Review mit Designer

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

- **macOS only** — Nutzt `say` Command für TTS, `fcntl` für Single-Instance Lock
- **No Tests** — Zero Test Coverage
- **UX unfertig** — Funktional komplett, aber Layout/Interaktionsdesign braucht professionelles Review
- **Analyse-Zeitschätzung ungenau** — Basiert auf Dateigrößen, nicht auf echtem Profiling
- **Kein Undo** — Clip-Änderungen (In/Out) und Ignore sind nicht rückgängig machbar

---

*Zuletzt aktualisiert: 2026-02-05*
