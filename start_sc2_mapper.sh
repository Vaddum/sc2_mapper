#!/usr/bin/env bash
#
# start_sc2_mapper.sh
# Wrapper de confort pour lancer sc2_sdl3_mapper.py proprement :
#   - ferme Steam s'il tourne (pour libérer le HID de la manette)
#   - s'assure que le module uinput est chargé
#   - lance le mapper avec ou sans sudo selon les permissions
#
# Place ce script dans le même dossier que sc2_sdl3_mapper.py.

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAPPER="$SCRIPT_DIR/sc2_sdl3_mapper.py"

echo -e "${CYAN}=== Lancement du mapper Steam Controller 2026 ===${NC}"

if [ ! -f "$MAPPER" ]; then
  echo -e "${RED}Introuvable : $MAPPER${NC}"
  echo "Place ce wrapper dans le même dossier que sc2_sdl3_mapper.py, ou édite la variable MAPPER."
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Fermer Steam s'il tourne (libère l'accès exclusif au HID de la manette)
# ---------------------------------------------------------------------------
if pgrep -x steam >/dev/null 2>&1; then
  echo -e "${YELLOW}Steam est en cours d'exécution — fermeture pour libérer la manette...${NC}"
  killall steam >/dev/null 2>&1
  # Attendre que le process disparaisse vraiment (jusqu'à 10s)
  for i in $(seq 1 10); do
    pgrep -x steam >/dev/null 2>&1 || break
    sleep 1
  done
  if pgrep -x steam >/dev/null 2>&1; then
    echo -e "${RED}Steam ne s'est pas fermé proprement. Ferme-le manuellement puis relance ce script.${NC}"
    exit 1
  fi
  echo -e "${GREEN}Steam fermé.${NC}"
else
  echo "Steam n'est pas lancé, on continue."
fi

# ---------------------------------------------------------------------------
# 2. S'assurer que le module uinput est chargé
# ---------------------------------------------------------------------------
if ! lsmod | grep -q '^uinput'; then
  echo "Chargement du module uinput..."
  sudo modprobe uinput
fi

# ---------------------------------------------------------------------------
# 3. Lancer le mapper (sudo seulement si /dev/uinput n'est pas accessible
#    directement, ex. si la règle udev n'a pas encore été mise en place)
# ---------------------------------------------------------------------------
if [ -w /dev/uinput ]; then
  echo -e "${GREEN}Accès direct à /dev/uinput, lancement sans sudo.${NC}"
  RUNNER="python3"
else
  echo -e "${YELLOW}Pas d'accès direct à /dev/uinput, lancement avec sudo.${NC}"
  echo "(Pour éviter ça à l'avenir : voir la règle udev mentionnée précédemment)"
  RUNNER="sudo python3"
fi

echo -e "${CYAN}Démarrage du mapping — Ctrl+C pour arrêter proprement.${NC}\n"
exec $RUNNER "$MAPPER" "$@"
