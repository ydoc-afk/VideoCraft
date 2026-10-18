#!/usr/bin/env bash
# Install VideoCraft for the current user (Linux).
#
#   ./install.sh                 # install, detect an NVIDIA GPU, set up the AI tools
#   ./install.sh --gpu cpu       # extra arguments are passed to `videocraft setup`
#   ./install.sh --no-ml         # app only; skip the AI packages (run `videocraft setup` later)
#   ./install.sh --uninstall     # remove the app (keeps your config and downloaded models)
#
# Re-run it after `git pull` to update.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_HOME="$DATA/videocraft-app"
VENV="$APP_HOME/venv"
BIN="$HOME/.local/bin"
DESKTOP_DIR="$DATA/applications"
ICON_DIR="$DATA/icons/hicolor/256x256/apps"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -rf "$APP_HOME" "$BIN/videocraft" "$DESKTOP_DIR/videocraft.desktop" "$ICON_DIR/videocraft.png"
    echo "VideoCraft removed. Config (~/.config/videocraftapp) and models ($DATA/videocraft) were kept."
    exit 0
fi

SETUP_ML=1
ARGS=()
for a in "$@"; do
    if [[ "$a" == "--no-ml" ]]; then SETUP_ML=0; else ARGS+=("$a"); fi
done

# ── Python 3.11+ ──
PY=""
# 3.12/3.11 first: the Real-ESRGAN dependency 'basicsr' does not build on 3.13 yet.
for cand in python3.12 python3.11 python3.13 python3; do
    if command -v "$cand" >/dev/null 2>&1 \
       && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
        PY="$cand"; break
    fi
done
if [[ -z "$PY" ]]; then
    echo "Python 3.11 or newer is required (try: sudo apt install python3 python3-venv)." >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Note: FFmpeg is not installed. VideoCraft needs it (sudo apt install ffmpeg)." >&2
fi

echo ">> Creating environment in $VENV"
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip

echo ">> Installing VideoCraft"
"$VENV/bin/python" -m pip install --quiet "$ROOT"

mkdir -p "$BIN" "$DESKTOP_DIR" "$ICON_DIR"
ln -sf "$VENV/bin/videocraft" "$BIN/videocraft"

# Launcher entry + icon (absolute Exec so it works without ~/.local/bin on PATH)
sed "s|^Exec=.*|Exec=$BIN/videocraft %F|" "$ROOT/packaging/videocraft.desktop" > "$DESKTOP_DIR/videocraft.desktop"
cp "$ROOT/videocraft/assets/icons/videocraft.png" "$ICON_DIR/videocraft.png"

if [[ "$SETUP_ML" == "1" ]]; then
    echo ">> Setting up the AI tools (this downloads PyTorch — several GB)"
    "$VENV/bin/videocraft" setup "${ARGS[@]}"
else
    echo ">> Skipped AI tools. Run 'videocraft setup' later to add them."
fi

case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "Note: add $BIN to your PATH to run 'videocraft' from a terminal." ;;
esac
echo "Done. Start VideoCraft from your app menu or with: videocraft"
