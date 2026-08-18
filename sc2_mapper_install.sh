#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"

if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP)"
else
  DESKTOP_DIR="$HOME/Desktop"
fi
DESKTOP_ICON="$DESKTOP_DIR/sc2-mapper.desktop"

REPO_RAW_URL="https://raw.githubusercontent.com/Vaddum/sc2_mapper/main/Sc2_mapper.py"

TARGET="$INSTALL_DIR/Sc2_mapper.py"

echo "=== Steam Controller 2026 Mapper - Install ==="
echo "Desktop folder detected: $DESKTOP_DIR"

mkdir -p "$INSTALL_DIR"

if [ -f "$SCRIPT_DIR/Sc2_mapper.py" ]; then
  cp "$SCRIPT_DIR/Sc2_mapper.py" "$TARGET"
  echo "Copied local Sc2_mapper.py to $TARGET"
else
  echo "Sc2_mapper.py not found next to this script, downloading from GitHub..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$REPO_RAW_URL" -o "$TARGET"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$REPO_RAW_URL" -O "$TARGET"
  else
    echo "Neither curl nor wget available. Install one, or place Sc2_mapper.py next to this script."
    exit 1
  fi
  if [ ! -s "$TARGET" ]; then
    echo "Download failed. Check your internet connection."
    rm -f "$TARGET"
    exit 1
  fi
  echo "Downloaded to $TARGET"
fi

chmod +x "$TARGET"

DESKTOP_CONTENT="[Desktop Entry]
Type=Application
Name=SC2 Mapper
Comment=SDL3-based mapping configuration and launcher for the Steam Controller 2026
Exec=python3 \"$TARGET\"
Terminal=false
Icon=input-gaming
Categories=Game;Utility;"

mkdir -p "$(dirname "$DESKTOP_ICON")"
echo "$DESKTOP_CONTENT" > "$DESKTOP_ICON"
chmod +x "$DESKTOP_ICON"
echo "Desktop icon created at $DESKTOP_ICON"

MISSING_PKGS=()
pacman -Qi sdl3 >/dev/null 2>&1 || MISSING_PKGS+=("sdl3")
pacman -Qi tk >/dev/null 2>&1 || MISSING_PKGS+=("tk")

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
  echo "Missing system packages: ${MISSING_PKGS[*]}"
  read -p "Install them now with sudo pacman -S? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    sudo pacman -S --noconfirm "${MISSING_PKGS[@]}"
  fi
fi

if ! python3 -c "import evdev" >/dev/null 2>&1; then
  echo "Python module 'evdev' is missing."
  read -p "Install it now with pip? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    pip install evdev --break-system-packages
  fi
fi

echo
echo "Installation complete."
echo "Script: $TARGET"
echo "Desktop icon: $DESKTOP_ICON"
echo
echo "On first launch from the Desktop icon, your file manager may ask you to confirm trust/allow execution - that is normal."
