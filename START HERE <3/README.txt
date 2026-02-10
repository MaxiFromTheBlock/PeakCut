===========================================
PEAKCUT
===========================================
Automatische Clip-Extraktion für Podcast-Produktion


EINRICHTUNG (einmalig)
----------------------

Voraussetzungen:
  - macOS
  - Python 3.11+ (https://www.python.org/downloads/ oder: brew install python@3.11)
  - ffmpeg (brew install ffmpeg)

1. Terminal öffnen (Programme → Dienstprogramme → Terminal)

2. Setup-Script ausführen:

    cd ~/Desktop/PeakCut/App/"START HERE <3" && ./setup.sh

3. Warten bis fertig (kann beim ersten Mal ein paar Minuten dauern)


APP STARTEN
-----------

    cd ~/Desktop/PeakCut/App/"START HERE <3" && ./start.sh


WORKFLOW
--------
1. PeakCut starten
2. "Import Files" klicken → Dateien wählen:
   - Keyboard-Audio (Dateiname enthält "keyboard", "keys" oder "klavier")
   - Mix-Audio (Dateiname enthält "mix")
   - Videos (.mp4/.mov) — optional
3. Analyse startet automatisch
4. Mit Play/Next/Back die Peaks durchhören
5. "Ignore" für falsche Peaks
6. "Mode" wechselt zwischen Keyboard- und Mikrofon-Vorschau
7. "Screenshot" für Frame-Export mit LUT
8. "Export" klicken → MP3 + TXT + XML landen in "2 Export/"


TASTATURKÜRZEL
--------------
→         Nächster Peak
←         Vorheriger Peak
Leertaste Play / Stop
I         Peak ignorieren
S         Screenshot


ORDNERSTRUKTUR
--------------
1 Material/      ← Audio/Video-Dateien hier reinlegen
2 Export/         ← Fertige Exports
3 Intern/        ← Programm-Dateien (nicht anfassen)
START HERE <3/   ← Setup, Start, diese Anleitung


EINSTELLUNGEN
-------------
Die Datei "3 Intern/config.json" enthält alle Parameter:
- threshold_factor: Empfindlichkeit der Peak-Erkennung (0.4 = 40%)
- min_gap_ms: Mindestabstand zwischen Peaks in ms (15000 = 15s)
- context_duration_ms: Kontext um jeden Peak im Export (15000 = ±15s)
- fps: Framerate für Timecodes (25)
- tts_voice: macOS Stimme für Nummern ("Anna" = Deutsch)
- lut_path: Aktive .cube LUT-Datei (über GUI wählbar)
