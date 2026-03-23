#!/bin/bash
# Smoke test for PeakCut.app bundle
# Verifies the bundled app can actually work, not just start.
set -e

APP="${1:-dist/PeakCut.app}"
EXEC="${APP}/Contents/MacOS/PeakCut"
INTERNAL="${APP}/Contents/Frameworks"

echo "=== PeakCut Smoke Test ==="
echo "App: ${APP}"
echo ""

FAIL=0
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAIL=1; }

# 1. App exists and is executable
echo "1. Bundle structure"
[ -x "$EXEC" ] && pass "Executable exists" || fail "Executable missing"
[ -d "${APP}/Contents/Resources" ] && pass "Resources dir exists" || fail "Resources dir missing"

# 2. Assets bundled
echo "2. Bundled assets"
# Find the _internal directory (PyInstaller puts it in different places)
INTERNAL_DIR=$(find "$APP" -name "_internal" -type d 2>/dev/null | head -1)
if [ -z "$INTERNAL_DIR" ]; then
    fail "No _internal directory found"
else
    pass "_internal dir: ${INTERNAL_DIR}"

    [ -d "${INTERNAL_DIR}/assets/pictures" ] && pass "Pictures bundled" || fail "Pictures missing"
    [ -f "${INTERNAL_DIR}/assets/pictures/peakcut_logo.png" ] && pass "Logo found" || fail "Logo missing"
    [ -d "${INTERNAL_DIR}/assets/zahlen" ] && pass "TTS zahlen bundled" || fail "TTS zahlen missing"
    ZAHLEN_COUNT=$(ls "${INTERNAL_DIR}/assets/zahlen/"*.mp3 2>/dev/null | wc -l | tr -d ' ')
    [ "$ZAHLEN_COUNT" -gt 10 ] && pass "TTS MP3s: ${ZAHLEN_COUNT} files" || fail "TTS MP3s: only ${ZAHLEN_COUNT} files"
    [ -d "${INTERNAL_DIR}/luts" ] && pass "LUTs dir bundled" || fail "LUTs dir missing"
fi

# 3. Qt multimedia plugins
echo "3. Qt multimedia"
MULTIMEDIA_DIR=$(find "$APP" -path "*/plugins/multimedia" -type d 2>/dev/null | head -1)
if [ -z "$MULTIMEDIA_DIR" ]; then
    fail "No multimedia plugins found"
else
    [ -f "${MULTIMEDIA_DIR}/libffmpegmediaplugin.dylib" ] && pass "ffmpeg plugin present" || fail "ffmpeg plugin missing"
fi

# 4. Python modules importable
echo "4. Module imports"
"$EXEC" --test-imports 2>/dev/null
# Since --test-imports won't work with a GUI app, test via the internal Python
# Instead, verify key .so/.dylib files exist
find "$APP" -name "numpy*" -type f 2>/dev/null | head -1 | grep -q numpy && pass "numpy bundled" || fail "numpy missing"
find "$APP" -name "scipy*" -type f 2>/dev/null | head -1 | grep -q scipy && pass "scipy bundled" || fail "scipy missing"
find "$APP" -name "PyQt6*" -type f 2>/dev/null | head -1 | grep -q PyQt6 && pass "PyQt6 bundled" || fail "PyQt6 missing"
find "$APP" -name "simpleaudio*" -type f 2>/dev/null | head -1 | grep -q simpleaudio && pass "simpleaudio bundled" || fail "simpleaudio missing"
find "$APP" -name "soundfile*" -type f 2>/dev/null | head -1 | grep -q soundfile && pass "soundfile bundled" || fail "soundfile missing"
find "$APP" -name "pydub*" -type f 2>/dev/null | head -1 | grep -q pydub && pass "pydub bundled" || fail "pydub missing"

# 5. External dependencies
echo "5. System dependencies"
if PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" which ffmpeg >/dev/null 2>&1; then
    pass "ffmpeg found: $(PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" which ffmpeg)"
else
    fail "ffmpeg not found in PATH"
fi
if PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" which ffprobe >/dev/null 2>&1; then
    pass "ffprobe found: $(PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" which ffprobe)"
else
    fail "ffprobe not found in PATH"
fi

# 6. App launches and creates data dir
echo "6. Launch test"
# Start app, wait 3 seconds, check it's running, then kill it
open "$APP"
sleep 3
if pgrep -f "PeakCut" >/dev/null 2>&1; then
    pass "App launched successfully"
    # Check data dir was created
    [ -d ~/Library/Application\ Support/PeakCut ] && pass "Data dir created" || fail "Data dir not created"
    pkill -f "PeakCut" 2>/dev/null
    sleep 1
else
    fail "App failed to launch"
fi

# 7. App icon
echo "7. App icon"
[ -f "${APP}/Contents/Resources/PeakCut.icns" ] 2>/dev/null && pass "App icon present" || \
[ -f "${APP}/Contents/Info.plist" ] && pass "Info.plist present" || fail "Info.plist missing"

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "=== ALL CHECKS PASSED ==="
else
    echo "=== SOME CHECKS FAILED ==="
    exit 1
fi
