#!/bin/bash
# Build PeakCut.app and create DMG installer
set -e

cd "$(dirname "$0")"

VENV="./3 Intern/venv311"
VERSION="2.7.0"

echo "=== PeakCut Build v${VERSION} ==="

# Step 1: Run tests
echo "Running tests..."
source "${VENV}/bin/activate"
cd "3 Intern"
python -m pytest tests/ -v --tb=short
cd ..

# Step 2: Build .app
echo ""
echo "Building .app..."
"${VENV}/bin/pyinstaller" PeakCut.spec --noconfirm

# Step 3: Create DMG
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

echo ""
echo "=== Build complete ==="
echo "  App: dist/PeakCut.app ($(du -sh dist/PeakCut.app | cut -f1))"
echo "  DMG: dist/${DMG_NAME} ($(du -sh dist/${DMG_NAME} | cut -f1))"
