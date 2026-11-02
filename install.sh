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
install -m 644 "$ROOT/paim.desktop" "$APPS/paim.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
printf '%s\n' "paim installed to $BIN/paim"
printf '%s\n' "Desktop entry: $APPS/paim.desktop"
printf '%s\n' "Make sure $BIN is in PATH, then run: paim"
