===========================================
PEAKCUT V3
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

6. "Export" klicken → MP3 + TXT landen in "2 Export"

7. Optional: "Screenshots" für Thumbnails
