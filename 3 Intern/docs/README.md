# PeakCut

## Was ist PeakCut?

PeakCut ist ein Desktop-Tool zur Podcast-Nachbearbeitung. Es erkennt automatisch Keyboard-Peaks (Fußpedalmarker) in Audioaufnahmen und exportiert nummerierte Audioclips mit Timecodes.

## Für wen ist es?

- Podcast-Produzenten die mit Fußpedal-Markern arbeiten
- Entwickelt für die Produktion von "Hotel Matze"
- Ideal für Interview-Podcasts mit mehreren Kameras

## Zwei Versionen

PeakCut existiert in zwei Versionen:

| Version | Entry Point | Status |
|---------|-------------|--------|
| **PyQt6** | `main_pyqt.py` | Aktive Entwicklung |
| Tkinter | `main.py` | Legacy (Backup) |

### PyQt6 Version (Empfohlen)
```bash
"./3 Intern/venv311/bin/python" "./3 Intern/src/main_pyqt.py"
```
- Modernes Apple-Style UI
- Keyboard Shortcuts (Leertaste, Pfeiltasten, S, I, E)
- SF Pro Display Font

### Tkinter Version (Legacy)
```bash
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"
```
- Ursprüngliche Version
- Bleibt als Backup erhalten

## Was kann PeakCut?

### Kernfunktionen

- **Peak-Erkennung**: Findet automatisch Keyboard-Peaks (Fußpedalschläge) in der Audiospur
- **Audio-Preview**: Spielt jeden Peak einzeln ab - im Keyboard-Modus (1 Sekunde) oder Mic-Modus (30 Sekunden Kontext)
- **Navigation**: Vor/Zurück durch alle Peaks, einzelne Peaks ignorieren
- **Export**: Erstellt MP3 mit gesprochenen Nummern + TXT mit allen Timecodes

### Keyboard Shortcuts (PyQt6)

| Taste | Aktion |
|-------|--------|
| `Leertaste` | Play/Stop |
| `→` | Nächster Peak |
| `←` | Vorheriger Peak |
| `S` | Switch Mode |
| `I` / `Delete` | Ignore Peak |
| `E` | Export |

### Zusatzfunktionen

- **Video-Sync**: Berechnet automatisch Offsets zwischen Video- und Audiospuren via Cross-Correlation
- **Screenshots**: Extrahiert 100 zufällige Frames pro Video mit optionalem Kodak-LUT
- **Config System**: Alle Parameter in `config.json` anpassbar

### Technische Details

- Python 3.11 + PyQt6 (oder Tkinter)
- macOS only (nutzt `say` für TTS)
- Unbegrenzte Anzahl von Peaks (TTS statt MP3-Dateien)
