# PeakCut

## Was ist PeakCut?

PeakCut ist ein Desktop-Tool zur Podcast-Nachbearbeitung. Es erkennt automatisch Keyboard-Peaks (Fußpedalmarker) in Audioaufnahmen und exportiert nummerierte Audioclips mit Timecodes.

## Für wen ist es?

- Podcast-Produzenten die mit Fußpedal-Markern arbeiten
- Entwickelt für die Produktion von "Hotel Matze"
- Ideal für Interview-Podcasts mit mehreren Kameras

## Was kann PeakCut?

### Kernfunktionen

- **Peak-Erkennung**: Findet automatisch Keyboard-Peaks (Fußpedalschläge) in der Audiospur
- **Audio-Preview**: Spielt jeden Peak einzeln ab - im Keyboard-Modus (1 Sekunde) oder Mic-Modus (30 Sekunden Kontext)
- **Navigation**: Vor/Zurück durch alle Peaks, einzelne Peaks ignorieren
- **Export**: Erstellt MP3 mit gesprochenen Nummern + TXT mit allen Timecodes

### Zusatzfunktionen

- **Video-Sync**: Berechnet automatisch Offsets zwischen Video- und Audiospuren via Cross-Correlation
- **Screenshots**: Extrahiert 100 zufällige Frames pro Video mit optionalem Kodak-LUT

### Technische Details

- Python/Tkinter Desktop-App
- macOS only (nutzt `say` für TTS)
- Unbegrenzte Anzahl von Peaks (TTS statt MP3-Dateien)
