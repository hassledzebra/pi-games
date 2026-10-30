#!/bin/sh
# Put launchers with their own icons on the Pi's desktop: Pi Brawl, Pi Rush and Pi Strum.
# Run once on the Pi (after install_pi.sh):  ./deploy/desktop_shortcut.sh
# Undo: delete ~/Desktop/pi-brawl.desktop, ~/Desktop/pi-rush.desktop and ~/Desktop/pi-strum.desktop
set -e
GAME_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
mkdir -p "$DESKTOP_DIR"

shortcut() {  # id, name, comment, entry script, icon script
    "$GAME_DIR/.venv/bin/python" "$GAME_DIR/deploy/$5" "$GAME_DIR/deploy/$1.png"
    TMP="$DESKTOP_DIR/.$1.desktop.tmp"
    cat > "$TMP" <<ENTRY
[Desktop Entry]
Type=Application
Name=$2
Comment=$3
Path=$GAME_DIR
Exec=$GAME_DIR/.venv/bin/python $GAME_DIR/$4
Icon=$GAME_DIR/deploy/$1.png
Terminal=false
Categories=Game;
ENTRY
    # the desktop only trusts executable .desktop files, and judges a file the moment it
    # appears, so make it executable first and then move it into place in one step
    chmod +x "$TMP"
    rm -f "$DESKTOP_DIR/$1.desktop"
    mv "$TMP" "$DESKTOP_DIR/$1.desktop"
    echo "Added $DESKTOP_DIR/$1.desktop"
}

shortcut pi-brawl "Pi Brawl" "2D versus fighting game" main.py make_icon.py
shortcut pi-rush "Pi Rush" "Split-screen cartoon kart racer" racing.py make_icon_rush.py
shortcut pi-strum "Pi Strum" "Guitar trainer: plug in, play along, get scored" guitar.py make_icon_strum.py
