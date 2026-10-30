#!/bin/sh
# Arcade mode: start Pi Brawl automatically on boot (console autologin on tty1).
# Run once on the Pi:  ./deploy/autostart.sh      Undo: delete the block from ~/.bash_profile
set -e
GAME_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if grep -q "pi-brawl autostart" ~/.bash_profile 2>/dev/null; then
    echo "Already set up in ~/.bash_profile"
    exit 0
fi
cat >> ~/.bash_profile <<PROFILE
# pi-brawl autostart
if [ "\$(tty)" = "/dev/tty1" ] && [ -z "\$DISPLAY" ] && [ -z "\$WAYLAND_DISPLAY" ]; then
    cd "$GAME_DIR" && SDL_VIDEODRIVER=kmsdrm .venv/bin/python main.py --fullscreen
fi
PROFILE
echo "Added to ~/.bash_profile."
echo "Now enable console autologin:  sudo raspi-config  ->  System Options -> Boot / Auto Login -> Console Autologin"
