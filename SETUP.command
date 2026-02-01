#!/bin/bash
# PeakCut Setup Script für macOS
# Doppelklick zum Ausführen

cd "$(dirname "$0")"

echo "========================================"
echo "  PeakCut Setup"
echo "========================================"
echo ""

# Check Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 nicht gefunden!"
    echo ""
    echo "Bitte installieren:"
    echo "  1. Öffne: https://www.python.org/downloads/"
    echo "  2. Lade Python 3.11 herunter"
    echo "  3. Installieren und dieses Script nochmal ausführen"
    echo ""
    read -p "Drücke Enter zum Beenden..."
    exit 1
fi

echo "✅ Python 3.11 gefunden"

# Create venv if not exists
if [ ! -d "venv311" ]; then
    echo "📦 Erstelle virtuelle Umgebung..."
    python3.11 -m venv venv311
fi

echo "📦 Installiere Abhängigkeiten..."
source venv311/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "========================================"
echo "  ✅ Setup abgeschlossen!"
echo "========================================"
echo ""
echo "Starte PeakCut mit Doppelklick auf:"
echo "  START.command"
echo ""
read -p "Drücke Enter zum Beenden..."
