#!/usr/bin/env bash
set -euo pipefail
rm -f \
  "${HOME}/.local/bin/desktop-clock" \
  "${HOME}/.local/share/applications/desktop-clock.desktop" \
  "${HOME}/.config/autostart/desktop-clock.desktop"
rm -rf "${HOME}/.local/share/desktop-clock" \
  "${HOME}/.local/share/cinnamon/desklets/desktop-clock@burnt1983" \
  "${HOME}/.local/share/cinnamon/applets/desktop-clock@burnt1983"
echo "Removed Desktop Clock. Face image in ~/.config/linux-desktop-clock was left in place."
