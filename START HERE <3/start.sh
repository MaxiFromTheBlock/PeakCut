#!/bin/bash
#
# PeakCut starten
#

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$APP_DIR/3 Intern/venv311"

if [ ! -d "$VENV_DIR" ]; then
    echo "FEHLER: venv nicht gefunden unter $VENV_DIR"
    echo ""
    echo "Bitte zuerst Setup ausführen:"
    echo "  ./setup.sh"
    exit 1
fi

export QT_LOGGING_RULES="qt.qpa.fonts.warning=false;qt.multimedia.ffmpeg.warning=false"
"$VENV_DIR/bin/python" "$APP_DIR/3 Intern/src/main_pyqt.py" 2>/dev/null
