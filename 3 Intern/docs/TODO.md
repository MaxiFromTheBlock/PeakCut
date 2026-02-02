# PeakCut TODO

Vollständige Aufgabenliste für die Weiterentwicklung von PeakCut.

---

## Kurzfristig (Aktuelle PyQt Migration)

### Phase 1-2: Foundation & Core
- [x] PyQt6 installiert und konfiguriert
- [x] apple_style.py von Screenshot Tool übernommen
- [x] lut_processor.py von Screenshot Tool übernommen
- [x] Main Window mit Apple-Style UI
- [x] Core-Verbindung (peaks.py, sync.py, export.py)
- [x] Playback Controls (Play/Stop/Back/Next/Switch/Ignore)
- [x] Status Display zentriert mit SF Pro Display Font
- [x] Export stoppt Playback automatisch
- [x] Keyboard Shortcuts (Leertaste, Pfeiltasten, S, I, E)
- [x] Config System (config.py mit JSON)
- [x] Export Bug Fix (verwendet immer mic_audios)

### Phase 3-5: Offen
- [ ] Phase 3: Video Preview mit Peak-Markern auf Timeline
- [ ] Phase 4: LUT Integration (lut_processor.py nutzen, LUT-Auswahl im GUI)
- [ ] Phase 5: EDL Export für Premiere Pro
- [ ] Threading für Analyse (UI friert ein, Rainbow Wheel)
- [ ] Progress Indicator mit echter Animation (bewegende Punkte)

---

## UX Verbesserungen

- [ ] "Video laden" Button umbenennen → "Dateien wählen" oder "Open Source Files"
- [ ] Finder-Browser implementieren statt Material-Ordner-Zwang
- [ ] User soll beliebigen Ordner wählen können
- [ ] Automatische Dateierkennung statt Dateinamen-Konvention (keyboard/keys/klavier)
- [ ] Alternative: Manuelle Zuweisung im GUI (Dropdown: "Diese Datei ist Keyboard-Spur")
- [ ] Zuletzt verwendete Ordner merken (QSettings)
- [ ] Zuletzt verwendete LUTs merken

---

## Bekannte Bugs

- [x] 49 Zahlen-Limit → gelöst mit TTS (generate_tts_number)
- [x] fps hardcoded auf 25 → jetzt in config.json konfigurierbar
- [ ] Keyboard Auto-Shutdown nach Inaktivität
- [ ] Video-Offsets nicht frame-genau
- [ ] Manuelle Umbenennung der Keyboard-Spur nötig
- [ ] Keine Warnung wenn 0 Peaks gefunden

---

## Technical Debt

- [ ] Global State refactoren (_peaks, _current_peak, _mode, _keyboard_audio, _mic_audios, _video_offsets)
- [ ] Error Recovery implementieren
- [ ] Hardcoded LUT Pfad entfernen (screenshots.py)
- [ ] Mixed Language bereinigen (DE/EN im Code)
- [ ] Tests schreiben
- [ ] Sync läuft immer (auch wenn keine Videos vorhanden)
- [ ] Screenshots LUT Interpolation unterscheidet sich von Premiere (nearest-neighbor statt trilinear)

---

## Von Screenshot Tool übernehmen

- [ ] video_preview.py adaptieren für Peak-Timeline
- [ ] progress_dialog.py für lange Operationen
- [ ] Worker Threads (QThread) für Background Processing ohne UI-Freeze
- [ ] QSettings Pattern für persistente Einstellungen

---

## Mittelfristig (v2.0 / v3.0)

### Profile System
- [ ] User-Profile anlegen können
- [ ] Einstellungen pro Profil speichern
- [ ] Profile zwischen Geräten synchronisieren

### Erweiterte Features
- [ ] Transkripte generieren (Speech-to-Text)
- [ ] Smarte Clip-Grenzen (automatische Optimierung)
- [ ] Batch-Processing (mehrere Episoden)
- [ ] Undo/Redo für Ignore-Aktionen

---

## Langfristig (V4 Vision)

### Drei-Schichten-Architektur
- [ ] Electron Desktop App (saubere Installation, Auto-Updates)
- [ ] Python Engine (Audio Processing, ML)
- [ ] FastAPI Cloud Backend (Accounts, Sync, Learning Profiles)

### Machine Learning
- [ ] ML soll Clips automatisch vorhersagen ohne manuelles Markieren
- [ ] Training aus Nutzungsdaten (welche Peaks behalten/ignoriert)
- [ ] Lernende Profile pro Format/Podcast
- [ ] Confidence Score pro vorgeschlagenem Clip

### Hardware
- [ ] Physischer Marker-Button entwickeln (Ziel: ca. 50€)
- [ ] Bluetooth/USB Verbindung
- [ ] Aktueller Workaround: Startone Keyboard (35€)

### Business Model
- [ ] Software: Abo ca. 10€/Monat/Profil
- [ ] Hardware: ca. 50€ pro Button
- [ ] Fokus: Zeitersparnis & Fehlerreduktion verkaufen

---

## Dokumentation

Diese Docs aktuell halten:
- [ ] TODO.md (diese Datei)
- [ ] CHANGELOG.md (Versionshistorie)
- [ ] ARCHITECTURE.md (Code-Struktur, Datenfluss)
- [ ] README.md (Setup, Nutzung)
- [ ] COMMANDS.md (Terminal-Befehle)
- [ ] SETUP.md (Installation)

---

## Aktuelle Dateistruktur

```
3 Intern/src/
├── main.py              # Tkinter Entry Point (Legacy)
├── main_pyqt.py         # PyQt Entry Point (Neu)
├── gui/                 # PyQt GUI Module
│   ├── __init__.py
│   ├── main_window.py
│   ├── apple_style.py
│   └── video_preview.py # (noch nicht integriert)
├── lib/                 # Externe Libraries
│   ├── __init__.py
│   └── lut_processor.py
├── peaks.py             # Peak Detection
├── sync.py              # Video Sync
├── export.py            # MP3 + TXT Export
├── utils.py             # Pfade, Hilfsfunktionen
├── config.py            # JSON Config System
├── status.py            # Status Callbacks
└── screenshots.py       # Frame Extraction
```

---

*Zuletzt aktualisiert: 2025-02-02*
