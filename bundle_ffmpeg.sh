#!/bin/bash
# Bundle ffmpeg + ffprobe with all Homebrew dylib dependencies.
# Creates a self-contained directory that works on any Mac (same arch).
set -e

DEST="${1:-bundled_ffmpeg}"
rm -rf "$DEST"
mkdir -p "$DEST/bin" "$DEST/lib"

FFMPEG_REAL=$(realpath "$(which ffmpeg)")
FFPROBE_REAL=$(realpath "$(which ffprobe)")

echo "Bundling ffmpeg from: $FFMPEG_REAL"
echo "Bundling ffprobe from: $FFPROBE_REAL"

cp "$FFMPEG_REAL" "$DEST/bin/ffmpeg"
cp "$FFPROBE_REAL" "$DEST/bin/ffprobe"
chmod 755 "$DEST/bin/ffmpeg" "$DEST/bin/ffprobe"

# Resolve @rpath references by searching common Homebrew paths
resolve_rpath() {
    local ref="$1"
    local name="${ref#@rpath/}"
    for search_dir in /opt/homebrew/lib /opt/homebrew/opt/*/lib /usr/local/lib; do
        if [ -f "$search_dir/$name" ]; then
            echo "$search_dir/$name"
            return 0
        fi
    done
    return 1
}

# Recursively copy all non-system dylib dependencies
copy_dylibs() {
    local binary="$1"
    otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r dylib; do
        # Skip system libraries
        case "$dylib" in
            /usr/lib/*|/System/*|@executable_path/*|@loader_path/*) continue ;;
        esac

        local dylib_real dylib_name
        if [[ "$dylib" == @rpath/* ]]; then
            dylib_real=$(resolve_rpath "$dylib") || continue
            dylib_name=$(basename "$dylib")
        else
            dylib_real=$(realpath "$dylib" 2>/dev/null) || continue
            dylib_name=$(basename "$dylib")
        fi

        if [ ! -f "$DEST/lib/$dylib_name" ]; then
            cp "$dylib_real" "$DEST/lib/$dylib_name"
            chmod 755 "$DEST/lib/$dylib_name"
            # Recurse into this dylib's dependencies
            copy_dylibs "$DEST/lib/$dylib_name"
        fi
    done
}

echo "Copying dylib dependencies..."
copy_dylibs "$DEST/bin/ffmpeg"
copy_dylibs "$DEST/bin/ffprobe"

# Fix rpaths: binaries reference libs via @loader_path/../lib/
fix_rpaths() {
    local binary="$1"
    local relative_lib_path="$2"  # e.g. "../lib" for bin/, "." for lib/

    otool -L "$binary" | tail -n +2 | awk '{print $1}' | while read -r dylib; do
        case "$dylib" in
            /usr/lib/*|/System/*|@loader_path/*|@executable_path/*) continue ;;
        esac
        local dylib_name
        dylib_name=$(basename "$dylib")
        install_name_tool -change "$dylib" "@loader_path/${relative_lib_path}/${dylib_name}" "$binary" 2>/dev/null || true
    done
    # Remove any existing rpaths that point to Homebrew
    otool -l "$binary" 2>/dev/null | grep -A2 "LC_RPATH" | grep "path " | awk '{print $2}' | while read -r rpath; do
        install_name_tool -delete_rpath "$rpath" "$binary" 2>/dev/null || true
    done
}

echo "Fixing rpaths for binaries..."
fix_rpaths "$DEST/bin/ffmpeg" "../lib"
fix_rpaths "$DEST/bin/ffprobe" "../lib"

echo "Fixing rpaths for libraries..."
for lib in "$DEST/lib/"*.dylib; do
    # Set the dylib's own install name
    local_name=$(basename "$lib")
    install_name_tool -id "@loader_path/$local_name" "$lib" 2>/dev/null || true
    # Fix references to other libs (same directory)
    fix_rpaths "$lib" "."
done

# Re-sign everything (install_name_tool invalidates signatures on arm64)
echo "Re-signing binaries and libraries..."
for lib in "$DEST/lib/"*.dylib; do
    codesign --force --sign - "$lib" 2>/dev/null || true
done
codesign --force --sign - "$DEST/bin/ffmpeg"
codesign --force --sign - "$DEST/bin/ffprobe"

LIB_COUNT=$(ls "$DEST/lib/"*.dylib 2>/dev/null | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$DEST" | cut -f1)
echo ""
echo "=== Bundle complete ==="
echo "  Binaries: $DEST/bin/ffmpeg, $DEST/bin/ffprobe"
echo "  Libraries: $LIB_COUNT dylibs in $DEST/lib/"
echo "  Total size: $TOTAL_SIZE"
