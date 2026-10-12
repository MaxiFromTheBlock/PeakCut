#!/usr/bin/env bash
# Baut einen kleinen AppleScript-Launcher, der immer auf DIESES Checkout zeigt.
# Der Zielpfad ist bewusst benutzerspezifisch und wird erst beim Ausfuehren
# eingesetzt; im Repository steht kein /Users/<name>-Pfad.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_ROOT/venv311/bin/python"
ENTRYPOINT="$REPO_ROOT/src/main_pyqt.py"
TARGET="${1:-$HOME/Applications/PeakCut.app}"
ICON="$REPO_ROOT/PeakCut.icns"

if [[ ! -x "$PYTHON" ]]; then
  echo "FEHLER: Python-Umgebung fehlt: $PYTHON" >&2
  echo "Zuerst Python 3.11 + venv311 einrichten (docs/HOST_SETUP.md)." >&2
  exit 2
fi
if [[ ! -f "$ENTRYPOINT" ]]; then
  echo "FEHLER: PeakCut-Einstieg fehlt: $ENTRYPOINT" >&2
  exit 2
fi
if [[ -e "$TARGET" ]]; then
  echo "FEHLER: Ziel existiert bereits: $TARGET" >&2
  echo "Bestehenden Launcher bewusst sichern/entfernen oder ein anderes Ziel angeben." >&2
  exit 2
fi

mkdir -p "$(dirname "$TARGET")"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/peakcut-launcher.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

# AppleScript-Strings brauchen nur Backslash und Anfuehrungszeichen escaped.
escape_applescript() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

PY_AS="$(escape_applescript "$PYTHON")"
ENTRY_AS="$(escape_applescript "$ENTRYPOINT")"
cat > "$TMP_DIR/starter.applescript" <<APPLESCRIPT
on run
  set repoPython to "$PY_AS"
  set repoScript to "$ENTRY_AS"
  try
    do shell script quoted form of repoPython & " " & quoted form of repoScript & " > /dev/null 2>&1 &"
  on error errMsg
    display dialog "PeakCut konnte nicht gestartet werden:" & return & return & errMsg buttons {"OK"} default button "OK" with icon stop
  end try
end run
APPLESCRIPT

osacompile -o "$TARGET" "$TMP_DIR/starter.applescript"

if [[ -f "$ICON" ]]; then
  cp "$ICON" "$TARGET/Contents/Resources/applet.icns"
  rm -f "$TARGET/Contents/Resources/Assets.car"
fi

/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName PeakCut" "$TARGET/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.peakcut.launcher" "$TARGET/Contents/Info.plist"
codesign --force --deep --sign - "$TARGET"

echo "PeakCut-Launcher gebaut: $TARGET"
echo "Checkout: $REPO_ROOT"
