#!/bin/bash
# Smoke test for PeakCut.app bundle
# Verifies the bundled app can actually work, not just start.
set -e

APP="${1:-dist/PeakCut.app}"
EXEC="${APP}/Contents/MacOS/PeakCut"

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
# Find the data directory (PyInstaller puts assets in Frameworks/ or _internal/)
INTERNAL_DIR=$(find "$APP" -name "Frameworks" -type d 2>/dev/null | head -1)
[ -z "$INTERNAL_DIR" ] && INTERNAL_DIR=$(find "$APP" -name "_internal" -type d 2>/dev/null | head -1)
if [ -z "$INTERNAL_DIR" ]; then
    fail "No Frameworks or _internal directory found"
else
    pass "Data dir: ${INTERNAL_DIR}"

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

# 4. Python modules bundled
echo "4. Module imports"
# Verify key modules exist (as files OR directories)
find "$APP" -name "numpy" 2>/dev/null | head -1 | grep -q numpy && pass "numpy bundled" || fail "numpy missing"
find "$APP" -name "scipy" 2>/dev/null | head -1 | grep -q scipy && pass "scipy bundled" || fail "scipy missing"
find "$APP" -name "PyQt6" 2>/dev/null | head -1 | grep -q PyQt6 && pass "PyQt6 bundled" || fail "PyQt6 missing"
find "$APP" -name "simpleaudio" 2>/dev/null | head -1 | grep -q simpleaudio && pass "simpleaudio bundled" || fail "simpleaudio missing"
find "$APP" -name "_soundfile_data" 2>/dev/null | head -1 | grep -q _soundfile && pass "soundfile bundled" || fail "soundfile missing"
# pydub is pure Python — bundled inside PyInstaller's PKG archive, not visible on filesystem

# 5. Bundled ffmpeg
echo "5. Bundled ffmpeg"
if [ -n "$INTERNAL_DIR" ]; then
    FFMPEG_BUNDLED="${INTERNAL_DIR}/ffmpeg_bin/bin/ffmpeg"
    FFPROBE_BUNDLED="${INTERNAL_DIR}/ffmpeg_bin/bin/ffprobe"
    [ -x "$FFMPEG_BUNDLED" ] && pass "ffmpeg bundled: ${FFMPEG_BUNDLED}" || fail "ffmpeg not bundled"
    [ -x "$FFPROBE_BUNDLED" ] && pass "ffprobe bundled: ${FFPROBE_BUNDLED}" || fail "ffprobe not bundled"
    # Test that bundled ffmpeg actually runs
    if [ -x "$FFMPEG_BUNDLED" ]; then
        "$FFMPEG_BUNDLED" -version >/dev/null 2>&1 && pass "ffmpeg executes OK" || fail "ffmpeg fails to execute"
    fi
    if [ -x "$FFPROBE_BUNDLED" ]; then
        "$FFPROBE_BUNDLED" -version >/dev/null 2>&1 && pass "ffprobe executes OK" || fail "ffprobe fails to execute"
    fi
    FFMPEG_LIBS=$(ls "${INTERNAL_DIR}/ffmpeg_bin/lib/"*.dylib 2>/dev/null | wc -l | tr -d ' ')
    [ "$FFMPEG_LIBS" -gt 50 ] && pass "ffmpeg dylibs: ${FFMPEG_LIBS}" || fail "ffmpeg dylibs: only ${FFMPEG_LIBS} (expected 50+)"
else
    fail "Cannot check ffmpeg — _internal dir not found"
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
