#!/usr/bin/env bash
# Build VideoCraft.AppImage from the PyInstaller onedir bundle.
#
# Usage:  packaging/build_appimage.sh
# Env:    PYTHON   python interpreter with the runtime deps + pyinstaller
#                  (default: python3)
#         ARCH     target arch tag for the AppImage name (default: uname -m)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
ARCH="${ARCH:-$(uname -m)}"
APPDIR="$ROOT/build/VideoCraft.AppDir"
TOOLS="$ROOT/build/tools"

echo ">> 1/5  PyInstaller build (onedir)"
"$PYTHON" -m PyInstaller --noconfirm --clean videocraft.spec

# Guard: if a static FFmpeg is present in the source tree it MUST end up in
# the bundle. Catches the case where a source binary went missing and the
# build would otherwise silently ship without it.
for tool in ffmpeg ffprobe; do
    if [[ -f "assets/bin/$tool" && ! -f "dist/VideoCraft/_internal/assets/bin/$tool" ]]; then
        echo "ERROR: assets/bin/$tool exists but was not bundled into the AppImage" >&2
        exit 1
    fi
done

echo ">> 2/5  Assembling AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# PyInstaller onedir output → usr/bin
cp -a "$ROOT/dist/VideoCraft/." "$APPDIR/usr/bin/"

# Desktop entry + icon (both at AppDir root, as appimagetool requires,
# plus the standard freedesktop locations)
install -m 644 packaging/videocraft.desktop "$APPDIR/videocraft.desktop"
install -m 644 packaging/videocraft.desktop "$APPDIR/usr/share/applications/videocraft.desktop"
install -m 644 assets/icons/videocraft.png "$APPDIR/videocraft.png"
install -m 644 assets/icons/videocraft.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/videocraft.png"

install -m 755 packaging/AppRun "$APPDIR/AppRun"

echo ">> 3/5  Fetching appimagetool"
mkdir -p "$TOOLS"
TOOL="$TOOLS/appimagetool-$ARCH.AppImage"
if [[ ! -x "$TOOL" ]]; then
    curl -fSL --retry 3 \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage" \
        -o "$TOOL"
    chmod +x "$TOOL"
fi

echo ">> 4/5  Packaging AppImage"
OUT="$ROOT/dist/VideoCraft-$ARCH.AppImage"
# --appimage-extract-and-run avoids needing FUSE for appimagetool itself
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"

echo ">> 5/5  Done"
ls -lh "$OUT"
