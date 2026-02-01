#!/bin/bash
# PeakCut starten - Doppelklick zum Ausführen

cd "$(dirname "$0")"

if [ ! -d "venv311" ]; then
    echo "❌ Bitte zuerst SETUP.command ausführen!"
    read -p "Drücke Enter zum Beenden..."
    exit 1
fi

source venv311/bin/activate
python src/main.py
