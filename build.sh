#!/bin/bash
# Build PeakCut.app and create DMG installer
set -e

cd "$(dirname "$0")"

VENV="./venv311"
# ACHTUNG: DMG-/Bundle-Build ist seit dem Launcher-Pivot (Mai 2026)
# bewusst geparkt. Diese VERSION ist STALE und NICHT die App-Version
# (siehe CLAUDE.md Changelog/Distribution). Vor einer Bundle-
# Wiederbelebung hier + PeakCut.spec aktualisieren (Versionsnummer =
# Max-Entscheidung, nicht automatisch hochzählen).
VERSION="2.9.0-STALE-PARKED"

echo "=== PeakCut Build v${VERSION} ==="

# Step 1: Bundle ffmpeg (if not already bundled or outdated)
if [ ! -f "bundled_ffmpeg/bin/ffmpeg" ]; then
    echo ""
    echo "Bundling ffmpeg..."
    ./bundle_ffmpeg.sh
else
    echo "Using existing bundled ffmpeg."
fi

# Step 2: Run tests
echo ""
echo "Running tests..."
"${VENV}/bin/python" -m pytest tests/ -v --tb=short

# Step 3: Build .app
echo ""
echo "Building .app..."
"${VENV}/bin/pyinstaller" PeakCut.spec --noconfirm

# Step 4: Inject bundled ffmpeg into .app (AFTER PyInstaller, so rpaths stay intact)
echo ""
echo "Injecting bundled ffmpeg into .app..."
FRAMEWORKS_DIR="dist/PeakCut.app/Contents/Frameworks"
cp -R bundled_ffmpeg "${FRAMEWORKS_DIR}/ffmpeg_bin"
# Re-sign the .app after modification
codesign --force --deep --sign - "dist/PeakCut.app"

# Step 5: Create DMG
echo ""
echo "Creating DMG..."
DMG_NAME="PeakCut-${VERSION}.dmg"
rm -f "dist/${DMG_NAME}"

create-dmg \
    --volname "PeakCut" \
    --volicon "PeakCut.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "PeakCut.app" 150 190 \
    --app-drop-link 450 190 \
    --hide-extension "PeakCut.app" \
    "dist/${DMG_NAME}" \
    "dist/PeakCut.app"

# Step 6: Copy to Release
echo ""
echo "Copying to Release..."
mkdir -p ../Release
cp "dist/${DMG_NAME}" "../Release/${DMG_NAME}"

echo ""
echo "=== Build complete ==="
echo "  App: dist/PeakCut.app ($(du -sh dist/PeakCut.app | cut -f1))"
echo "  DMG: dist/${DMG_NAME} ($(du -sh dist/${DMG_NAME} | cut -f1))"
echo "  Release: ../Release/${DMG_NAME}"
