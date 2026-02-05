===========================================
PEAKCUT (v1.4.0)
===========================================
Automatische Clip-Extraktion für Podcast-Produktion


FÜR MAX (Entwickler)
--------------------

PeakCut starten:
    source ~/Desktop/PeakCut/App/"3 Intern"/venv311/bin/activate && python ~/Desktop/PeakCut/App/"3 Intern"/src/main.py

Mit Claude Code weiterarbeiten:
    cd ~/Desktop/PeakCut/App && claude

GitHub:
    Branch 'develop' enthält die aktuelle Entwicklung
    Branch 'main' ist die stabile Produktionsversion



FÜR ALLE ANDEREN (Erste Einrichtung)
-------------------------------------

Voraussetzung: Python 3.11 muss installiert sein
Download: https://www.python.org/downloads/

1. Terminal öffnen (Programme → Dienstprogramme → Terminal)

2. Einmalig ausführen - Virtual Environment erstellen:

    cd ~/Desktop/PeakCut/App && python3.11 -m venv "3 Intern/venv311" && source "3 Intern/venv311/bin/activate" && pip install -r "3 Intern/requirements.txt"

3. Warten bis Installation fertig (kann ein paar Minuten dauern)

4. PeakCut starten:

    cd ~/Desktop/PeakCut/App && source "3 Intern/venv311/bin/activate" && python "3 Intern/src/main.py"



ORDNERSTRUKTUR
--------------
1 Material/  ← Deine Audio/Video-Dateien hier reinlegen
2 Export/    ← Hier findest du die fertigen Exports
3 Intern/    ← Programm-Dateien (nicht anfassen)
   └── config.json  ← Einstellungen (Threshold, FPS, TTS-Stimme etc.)



WORKFLOW
--------
1. Dateien in "1 Material" legen:
   - Keyboard-Audio (Dateiname muss "keyboard", "keys" oder "klavier" enthalten)
   - Mix-Audio (Dateiname muss "mix" enthalten)
   - Videos (.mp4/.mov) - optional

2. PeakCut starten

3. "Analyze" klicken → erkennt Peaks

4. Mit Play/Next/Back die Peaks durchhören

5. "Ignore" für falsche Peaks

6. "Export" klicken → MP3 + TXT + XML landen in "2 Export"
   (Export enthält immer die Mic-Spuren, nicht das Keyboard-Audio)

7. Optional: "Screenshot" Button für Frame mit LUT → landet in "2 Export/Screenshots"


EINSTELLUNGEN
-------------
Die Datei "3 Intern/config.json" enthält alle Parameter:
- threshold_factor: Empfindlichkeit der Peak-Erkennung (0.4 = 40%)
- min_gap_ms: Mindestabstand zwischen Peaks in ms (15000 = 15s)
- context_duration_ms: Kontext um jeden Peak im Export (15000 = ±15s)
- fps: Framerate für Timecodes (25)
- tts_voice: macOS Stimme für Nummern ("Anna" = Deutsch)
- lut_path: Pfad zur aktiven .cube LUT-Datei (über GUI wählbar)
