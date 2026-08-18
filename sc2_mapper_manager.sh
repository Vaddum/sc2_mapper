#!/usr/bin/env bash
#
# sc2_mapper_manager.sh
# Gestion complète du mapper Steam Controller 2026 (SDL3) :
# installation, configuration, lancement/arrêt, désinstallation.
#
# Doit se trouver dans le même dossier que :
#   sdl3_gamepad.py, sc2_sdl3_mapper.py, sc2_mapper_gui.py, start_sc2_mapper.sh
# (le contenu du .desktop est généré directement par ce script, pas besoin
# du fichier .desktop séparé)
#
# Prérequis : zenity
#   sudo pacman -S zenity
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/sc2-mapper.desktop"
CONFIG_DIR="$HOME/.config/sc2_mapper"
UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"

PAYLOAD_FILES=(sdl3_gamepad.py sc2_sdl3_mapper.py sc2_mapper_gui.py start_sc2_mapper.sh)

# =============================================================================
# Utilitaires
# =============================================================================

check_zenity() {
  command -v zenity >/dev/null 2>&1 || { echo "zenity requis : sudo pacman -S zenity"; exit 1; }
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
      echo "Installé — mapping actuellement ACTIF"
    else
      echo "Installé — mapping inactif"
    fi
  else
    echo "Non installé"
  fi
}

# =============================================================================
# Installation
# =============================================================================

do_install() {
  local missing_src=()
  for f in "${PAYLOAD_FILES[@]}"; do
    [ -f "$SCRIPT_DIR/$f" ] || missing_src+=("$f")
  done
  if [ ${#missing_src[@]} -gt 0 ]; then
    zenity --error --width=420 --text="Fichiers manquants à côté de ce script :\n\n$(printf '  - %s\n' "${missing_src[@]}")\nPlace-les dans le même dossier que sc2_mapper_manager.sh avant d'installer."
    return
  fi

  mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR"
  for f in "${PAYLOAD_FILES[@]}"; do
    cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
  done
  chmod +x "$INSTALL_DIR/start_sc2_mapper.sh"

  cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Type=Application
Name=Steam Controller 2026 Mapper
Comment=Configuration graphique du mapping pour le Steam Controller 2026 (SDL3)
Exec=sh -c "python3 $HOME/.local/bin/sc2_mapper_gui.py"
Terminal=false
Icon=input-gaming
Categories=Game;Utility;
EOF
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1

  # --- Dépendances système ---
  local missing_pkgs=()
  pacman -Qi sdl3 >/dev/null 2>&1 || missing_pkgs+=("sdl3")
  pacman -Qi tk >/dev/null 2>&1 || missing_pkgs+=("tk")
  if [ ${#missing_pkgs[@]} -gt 0 ]; then
    if zenity --question --text="Paquets manquants : ${missing_pkgs[*]}\n\nLes installer maintenant (sudo pacman -S) ?"; then
      sudo pacman -S --noconfirm "${missing_pkgs[@]}"
    fi
  fi

  if ! python3 -c "import evdev" >/dev/null 2>&1; then
    if zenity --question --text="Le module Python 'evdev' est requis et absent.\n\nL'installer maintenant ?\n(pip install evdev --break-system-packages)"; then
      pip install evdev --break-system-packages
    fi
  fi

  # --- Accès uinput sans sudo (optionnel) ---
  if [ ! -f "$UDEV_RULE" ]; then
    if zenity --question --text="Configurer l'accès à /dev/uinput sans sudo à chaque lancement ?\n(règle udev + ajout au groupe 'input' ; déconnexion/reconnexion nécessaire ensuite)"; then
      echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee "$UDEV_RULE" >/dev/null
      sudo udevadm control --reload-rules
      sudo usermod -aG input "$USER"
      zenity --info --text="Règle udev installée.\nDéconnecte-toi/reconnecte-toi pour que l'appartenance au groupe 'input' prenne effet."
    fi
  fi

  zenity --info --text="Installation terminée.\n\nRaccourci disponible dans le menu applications :\n'Steam Controller 2026 Mapper'"
}

# =============================================================================
# Désinstallation
# =============================================================================

do_uninstall() {
  if ! is_installed; then
    zenity --info --text="Rien à désinstaller, ce n'est pas installé."
    return
  fi
  if ! zenity --question --text="Tout désinstaller (scripts, raccourci, config) ?"; then
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
    if zenity --question --text="Supprimer aussi la règle udev ($UDEV_RULE) ?"; then
      sudo rm -f "$UDEV_RULE"
      sudo udevadm control --reload-rules
    fi
  fi

  zenity --info --text="Désinstallation terminée.\n\n(sdl3 et tk sont laissés en place, d'autres logiciels peuvent en dépendre.\nSupprime-les manuellement via pacman si tu es sûr de ne plus en avoir besoin.)"
}

# =============================================================================
# Configuration / Lancement / Arrêt
# =============================================================================

do_configure() {
  if ! is_installed; then
    zenity --error --text="Pas encore installé. Utilise \"Installer\" d'abord."
    return
  fi
  python3 "$INSTALL_DIR/sc2_mapper_gui.py" &
  disown
}

do_launch() {
  if ! is_installed; then
    zenity --error --text="Pas encore installé. Utilise \"Installer\" d'abord."
    return
  fi
  if pgrep -f sc2_sdl3_mapper.py >/dev/null 2>&1; then
    zenity --info --text="Le mapping tourne déjà."
    return
  fi

  local term=""
  for t in konsole gnome-terminal xterm; do
    command -v "$t" >/dev/null 2>&1 && { term="$t"; break; }
  done
  if [ -z "$term" ]; then
    zenity --error --text="Aucun terminal graphique trouvé (konsole/gnome-terminal/xterm).\nLance manuellement : $INSTALL_DIR/start_sc2_mapper.sh"
    return
  fi

  case "$term" in
    gnome-terminal)
      "$term" -- bash -c "'$INSTALL_DIR/start_sc2_mapper.sh'; echo; read -p 'Appuie sur Entree pour fermer...'" &
      ;;
    *)
      "$term" -e bash -c "'$INSTALL_DIR/start_sc2_mapper.sh'; echo; read -p 'Appuie sur Entree pour fermer...'" &
      ;;
  esac
  disown
}

do_stop() {
  if ! pgrep -f sc2_sdl3_mapper.py >/dev/null 2>&1; then
    zenity --info --text="Le mapping n'est pas actif."
    return
  fi
  pkill -f sc2_sdl3_mapper.py
  zenity --info --text="Mapping arrêté."
}

# =============================================================================
# Menu principal
# =============================================================================

check_zenity

while true; do
  CHOICE=$(zenity --list --title="Steam Controller 2026 Mapper — Gestion" \
    --text="Statut actuel : $(status_text)" \
    --column="Action" \
    "Installer" \
    "Configurer (interface graphique)" \
    "Lancer le mapping" \
    "Arrêter le mapping" \
    "Désinstaller" \
    "Quitter" \
    --width=460 --height=400)

  case "$CHOICE" in
    "Installer") do_install ;;
    "Configurer (interface graphique)") do_configure ;;
    "Lancer le mapping") do_launch ;;
    "Arrêter le mapping") do_stop ;;
    "Désinstaller") do_uninstall ;;
    "Quitter"|"") exit 0 ;;
  esac
done
