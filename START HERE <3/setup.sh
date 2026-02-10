#!/bin/bash
#
# PeakCut Setup
# Erstellt die virtuelle Umgebung und installiert alle Dependencies.
#

set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$APP_DIR/3 Intern/venv311"
REQ_FILE="$APP_DIR/3 Intern/requirements.txt"

echo "=== PeakCut Setup ==="
echo ""

# --- Python 3.11+ prüfen ---
PYTHON=""

# Zuerst pyenv-Versionen durchsuchen (bevorzugt)
if [ -d "$HOME/.pyenv/versions" ]; then
    for p in "$HOME"/.pyenv/versions/3.1[1-9]*/bin/python3; do
        if [ -x "$p" ]; then
            PYTHON="$p"
            break
        fi
    done
fi

# Fallback: System-Python prüfen
if [ -z "$PYTHON" ]; then
    if command -v python3 &>/dev/null; then
        PY_VERSION=$(python3 -c 'import sys; print(sys.version_info.minor)')
        if [ "$PY_VERSION" -ge 11 ] 2>/dev/null; then
            PYTHON="python3"
        fi
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "FEHLER: Python 3.11 oder neuer nicht gefunden."
    echo ""
    echo "Installiere Python 3.11+ z.B. via Homebrew:"
    echo "  brew install python@3.11"
    echo ""
    echo "Oder via pyenv:"
    echo "  brew install pyenv"
    echo "  pyenv install 3.11"
    exit 1
fi

PY_FULL_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
echo "Python gefunden: $PY_FULL_VERSION ($PYTHON)"

# --- ffmpeg prüfen ---
if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "FEHLER: ffmpeg nicht gefunden."
    echo ""
    echo "Installiere ffmpeg via Homebrew:"
    echo "  brew install ffmpeg"
    exit 1
fi

FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1)
echo "ffmpeg gefunden: $FFMPEG_VERSION"

# --- Virtual Environment erstellen ---
echo ""
if [ -d "$VENV_DIR" ]; then
    echo "venv existiert bereits: $VENV_DIR"
    echo "Überspringe Erstellung. (Zum Neuerstellen: rm -rf \"$VENV_DIR\" und setup.sh erneut starten)"
else
    echo "Erstelle venv..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "venv erstellt: $VENV_DIR"
fi

# --- Dependencies installieren ---
echo ""
echo "Installiere Dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$REQ_FILE" --quiet
echo "Dependencies installiert."

# --- Ordner erstellen ---
mkdir -p "$APP_DIR/1 Material"
mkdir -p "$APP_DIR/2 Export"

echo ""
echo "=== Setup abgeschlossen ==="
echo ""
echo "Starte die App mit:  ./start.sh"
