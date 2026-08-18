#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/sc2-mapper.desktop"
CONFIG_DIR="$HOME/.config/sc2_mapper"
UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"

REPO_RAW_BASE="https://raw.githubusercontent.com/Vaddum/sc2_mapper_manager"
REPO_BRANCHES=("main" "master")

PAYLOAD_FILES=(sdl3_gamepad.py sc2_sdl3_mapper.py sc2_mapper_gui.py start_sc2_mapper.sh)

check_zenity() {
  command -v zenity >/dev/null 2>&1 || { echo "zenity required: sudo pacman -S zenity"; exit 1; }
}

run_sudo() {
  local pass
  pass=$(zenity --password --title="Administrator password")
  if [ -z "$pass" ]; then
    return 1
  fi
  echo "$pass" | sudo -S "$@" 2>/tmp/sc2_mapper_sudo_err
  local status=$?
  if [ $status -ne 0 ]; then
    zenity --error --width=420 --text="Administrator command failed:\n\n$(cat /tmp/sc2_mapper_sudo_err 2>/dev/null)"
  fi
  rm -f /tmp/sc2_mapper_sudo_err
  return $status
}

download_file() {
  local remote_name="$1" local_path="$2" branch url
  for branch in "${REPO_BRANCHES[@]}"; do
    url="$REPO_RAW_BASE/$branch/$remote_name"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$url" -o "$local_path" 2>/dev/null && [ -s "$local_path" ] && return 0
    elif command -v wget >/dev/null 2>&1; then
      wget -q "$url" -O "$local_path" 2>/dev/null && [ -s "$local_path" ] && return 0
    else
      return 2
    fi
  done
  return 1
}

is_installed() {
  for f in "${PAYLOAD_FILES[@]}"; do
    [ -f "$INSTALL_DIR/$f" ] || return 1
  done
  return 0
}

status_text() {
  if is_installed; then
    if pgrep -f sc2_sdl3_mapper.py >/dev/null 2>&1; then
      echo "Installed - mapping currently ACTIVE"
    else
      echo "Installed - mapping inactive"
    fi
  else
    echo "Not installed"
  fi
}

do_install() {
  local work_dir
  work_dir=$(mktemp -d)

  local to_download=()
  for f in "${PAYLOAD_FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
      cp "$SCRIPT_DIR/$f" "$work_dir/$f"
    else
      to_download+=("$f")
    fi
  done

  if [ ${#to_download[@]} -gt 0 ]; then
    (
      for f in "${to_download[@]}"; do
        echo "# Downloading $f..."
        if ! download_file "$f" "$work_dir/$f"; then
          echo "FAILED:$f" >> "$work_dir/.dl_errors"
        fi
      done
    ) | zenity --progress --pulsate --no-cancel --auto-close \
        --title="Installation" --text="Downloading files from GitHub..."

    if [ -f "$work_dir/.dl_errors" ]; then
      zenity --error --width=420 --text="Download failed:\n\n$(cat "$work_dir/.dl_errors")\n\nCheck your internet connection, or place the files manually next to this script."
      rm -rf "$work_dir"
      return
    fi
  fi

  mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR"
  for f in "${PAYLOAD_FILES[@]}"; do
    cp "$work_dir/$f" "$INSTALL_DIR/$f"
  done
  chmod +x "$INSTALL_DIR/start_sc2_mapper.sh"
  rm -rf "$work_dir"

  cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Steam Controller 2026 Mapper
Comment=Graphical mapping configuration for the Steam Controller 2026 (SDL3)
Exec=python3 "$INSTALL_DIR/sc2_mapper_gui.py"
Terminal=false
Icon=input-gaming
Categories=Game;Utility;
EOF
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1

  local missing_pkgs=()
  pacman -Qi sdl3 >/dev/null 2>&1 || missing_pkgs+=("sdl3")
  pacman -Qi tk >/dev/null 2>&1 || missing_pkgs+=("tk")
  if [ ${#missing_pkgs[@]} -gt 0 ]; then
    if zenity --question --text="Missing packages: ${missing_pkgs[*]}\n\nInstall them now (sudo pacman -S)?"; then
      run_sudo pacman -S --noconfirm "${missing_pkgs[@]}"
    fi
  fi

  if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    zenity --warning --width=420 --text="Tkinter (package 'tk') is still not available.\n\nThe graphical interface will not open until this is fixed.\nTry manually: sudo pacman -S tk"
  fi

  if ! python3 -c "import evdev" >/dev/null 2>&1; then
    if zenity --question --text="The Python module 'evdev' is required and missing.\n\nInstall it now?\n(pip install evdev --break-system-packages)"; then
      pip install evdev --break-system-packages
    fi
  fi

  if [ ! -f "$UDEV_RULE" ]; then
    if zenity --question --text="Set up passwordless access to /dev/uinput?\n(udev rule + adding your user to the 'input' group; log out/in required afterwards)"; then
      if run_sudo bash -c "echo 'KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\"' > '$UDEV_RULE' && udevadm control --reload-rules && usermod -aG input '$USER'"; then
        zenity --info --text="udev rule installed.\nLog out/in for the 'input' group membership to take effect."
      fi
    fi
  fi

  zenity --info --text="Installation complete in:\n$INSTALL_DIR\n\nShortcut available in the application menu:\n'Steam Controller 2026 Mapper'"
}

do_uninstall() {
  if ! is_installed; then
    zenity --info --text="Nothing to uninstall, it is not installed."
    return
  fi
  if ! zenity --question --text="Uninstall everything (scripts, shortcut, config)?"; then
    return
  fi

  pkill -f sc2_sdl3_mapper.py 2>/dev/null

  rm -f "$DESKTOP_FILE"
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1

  for f in "${PAYLOAD_FILES[@]}"; do
    rm -f "$INSTALL_DIR/$f"
  done

  rm -rf "$CONFIG_DIR"

  if [ -f "$UDEV_RULE" ]; then
    if zenity --question --text="Also remove the udev rule ($UDEV_RULE)?"; then
      run_sudo bash -c "rm -f '$UDEV_RULE' && udevadm control --reload-rules"
    fi
  fi

  zenity --info --text="Uninstallation complete.\n\n(sdl3 and tk are left in place, other software may depend on them.\nRemove them manually via pacman if you are sure you no longer need them.)"
}

do_configure() {
  if ! is_installed; then
    zenity --error --text="Not installed yet. Use \"Install\" first."
    return
  fi
  python3 "$INSTALL_DIR/sc2_mapper_gui.py" &
  disown
}

do_launch() {
  if ! is_installed; then
    zenity --error --text="Not installed yet. Use \"Install\" first."
    return
  fi
  if pgrep -f sc2_sdl3_mapper.py >/dev/null 2>&1; then
    zenity --info --text="Mapping is already running."
    return
  fi

  local term=""
  for t in konsole gnome-terminal xterm; do
    command -v "$t" >/dev/null 2>&1 && { term="$t"; break; }
  done
  if [ -z "$term" ]; then
    zenity --error --text="No graphical terminal found (konsole/gnome-terminal/xterm).\nRun manually: $INSTALL_DIR/start_sc2_mapper.sh"
    return
  fi

  case "$term" in
    gnome-terminal)
      "$term" -- bash -c "'$INSTALL_DIR/start_sc2_mapper.sh'; echo; read -p 'Press Enter to close...'" &
      ;;
    *)
      "$term" -e bash -c "'$INSTALL_DIR/start_sc2_mapper.sh'; echo; read -p 'Press Enter to close...'" &
      ;;
  esac
  disown
}

do_stop() {
  if ! pgrep -f sc2_sdl3_mapper.py >/dev/null 2>&1; then
    zenity --info --text="Mapping is not active."
    return
  fi
  pkill -f sc2_sdl3_mapper.py
  zenity --info --text="Mapping stopped."
}

check_zenity

while true; do
  CHOICE=$(zenity --list --title="Steam Controller 2026 Mapper - Management" \
    --text="Current status: $(status_text)" \
    --column="Action" \
    "Install" \
    "Configure (graphical interface)" \
    "Launch mapping" \
    "Stop mapping" \
    "Uninstall" \
    "Quit" \
    --width=460 --height=400)

  case "$CHOICE" in
    "Install") do_install ;;
    "Configure (graphical interface)") do_configure ;;
    "Launch mapping") do_launch ;;
    "Stop mapping") do_stop ;;
    "Uninstall") do_uninstall ;;
    "Quit"|"") exit 0 ;;
  esac
done
