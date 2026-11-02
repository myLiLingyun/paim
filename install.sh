#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Install paim for the current user.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$BIN" "$APPS" "$ICONS"
ln -sf "$ROOT/paim" "$BIN/paim"
install -m 644 "$ROOT/assets/paim.png" "$ICONS/paim.png"

# GUI sessions often do not include ~/.local/bin in PATH.  Write an absolute
# Exec path (and an absolute icon path) into the installed desktop entry.
TMP_DESKTOP=$(mktemp)
trap 'rm -f "$TMP_DESKTOP"' EXIT HUP INT TERM
awk -v exec_line="Exec=\"$BIN/paim\" %F" -v icon_line="Icon=$ICONS/paim.png" '
  /^Exec=/ { print exec_line; next }
  /^Icon=/ { print icon_line; next }
  { print }
' "$ROOT/paim.desktop" > "$TMP_DESKTOP"
install -m 644 "$TMP_DESKTOP" "$APPS/paim.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
printf '%s\n' "paim installed to $BIN/paim"
printf '%s\n' "Desktop entry: $APPS/paim.desktop"
printf '%s\n' "The desktop entry uses an absolute Exec path; no PATH setup is required."
