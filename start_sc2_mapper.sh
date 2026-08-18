#!/usr/bin/env bash
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAPPER="$SCRIPT_DIR/sc2_sdl3_mapper.py"

echo -e "${CYAN}=== Starting Steam Controller 2026 mapper ===${NC}"

if [ ! -f "$MAPPER" ]; then
  echo -e "${RED}Not found: $MAPPER${NC}"
  echo "Place this wrapper in the same folder as sc2_sdl3_mapper.py, or edit the MAPPER variable."
  exit 1
fi

if pgrep -x steam >/dev/null 2>&1; then
  echo -e "${YELLOW}Steam is running - closing it to release the gamepad...${NC}"
  killall steam >/dev/null 2>&1
  for i in $(seq 1 10); do
    pgrep -x steam >/dev/null 2>&1 || break
    sleep 1
  done
  if pgrep -x steam >/dev/null 2>&1; then
    echo -e "${RED}Steam did not close properly. Close it manually then rerun this script.${NC}"
    exit 1
  fi
  echo -e "${GREEN}Steam closed.${NC}"
else
  echo "Steam is not running, continuing."
fi

if ! lsmod | grep -q '^uinput'; then
  echo "Loading uinput module..."
  sudo modprobe uinput
fi

if [ -w /dev/uinput ]; then
  echo -e "${GREEN}Direct access to /dev/uinput, running without sudo.${NC}"
  RUNNER="python3"
else
  echo -e "${YELLOW}No direct access to /dev/uinput, running with sudo.${NC}"
  echo "(To avoid this in the future: set up the udev rule.)"
  RUNNER="sudo python3"
fi

echo -e "${CYAN}Starting mapping - Ctrl+C to stop cleanly.${NC}\n"
exec $RUNNER "$MAPPER" "$@"
