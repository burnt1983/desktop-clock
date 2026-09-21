#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="${HOME}/.local/bin"
SHARE="${HOME}/.local/share/desktop-clock"
APPS="${HOME}/.local/share/applications"
AUTO="${HOME}/.config/autostart"

mkdir -p "$BIN" "$SHARE" "$APPS" "$AUTO"
install -m 0755 "$ROOT/clock.py" "$SHARE/clock.py"
install -m 0644 "$ROOT/linux_widget.py" "$SHARE/linux_widget.py"
ln -sfn "$SHARE/clock.py" "$BIN/desktop-clock"

sed "s|^Exec=desktop-clock --desklet$|Exec=${BIN}/desktop-clock --desklet|" \
    "$ROOT/data/desktop-clock.desktop" > "$APPS/desktop-clock.desktop"
cp "$APPS/desktop-clock.desktop" "$AUTO/desktop-clock.desktop"
chmod 0755 "$APPS/desktop-clock.desktop" "$AUTO/desktop-clock.desktop"

if [ -d "$ROOT/cinnamon" ]; then
  mkdir -p "${HOME}/.local/share/cinnamon/desklets" "${HOME}/.local/share/cinnamon/applets"
  cp -a "$ROOT/cinnamon/desklets/." "${HOME}/.local/share/cinnamon/desklets/"
  cp -a "$ROOT/cinnamon/applets/." "${HOME}/.local/share/cinnamon/applets/"
fi

echo "Installed Desktop Clock."
echo "  Desklet:  desktop-clock --desklet"
echo "  Panel:    desktop-clock --panel"
echo "Right-click: seconds, digital time, transparent face, choose PNG/logo."
echo "Scroll to resize. On Cinnamon: Desklets → Desktop Clock."
