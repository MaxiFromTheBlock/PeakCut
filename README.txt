===========================================
PEAKCUT
===========================================


FÜR MAX (Entwickler)
--------------------

PeakCut starten:
    source ~/Desktop/PeakCut/App/"3 Intern"/venv311/bin/activate && python ~/Desktop/PeakCut/App/"3 Intern"/src/main.py

Mit Claude Code weiterarbeiten:
    cd ~/Desktop/PeakCut/App && claude



FÜR ALLE ANDEREN (Erste Einrichtung)
-------------------------------------

1. Terminal öffnen (Programme → Dienstprogramme → Terminal)

2. Diesen Befehl kopieren und einfügen:

    cd ~/Desktop/PeakCut/App && python3.11 -m venv "3 Intern/venv311" && source "3 Intern/venv311/bin/activate" && pip install -r "3 Intern/requirements.txt"

3. Warten bis Installation fertig (kann ein paar Minuten dauern)

4. Fertig! Ab jetzt PeakCut starten mit:

    cd ~/Desktop/PeakCut/App && source "3 Intern/venv311/bin/activate" && python "3 Intern/src/main.py"


ORDNERSTRUKTUR
--------------
1 Material/  ← Hier deine Audio/Video-Dateien reinlegen
2 Export/    ← Hier findest du die fertigen Exports
3 Intern/    ← Nicht anfassen (Programm-Dateien)
