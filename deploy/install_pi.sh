#!/bin/sh
# Run once on the Raspberry Pi, inside the project folder:  ./deploy/install_pi.sh
set -e
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
if .venv/bin/pip install -r requirements.txt; then
    echo "pygame-ce installed in .venv"
else
    echo "No pygame-ce wheel for this Pi - falling back to Raspberry Pi OS's pygame package."
    sudo apt-get install -y python3-pygame
    rm -rf .venv
    python3 -m venv --system-site-packages .venv
fi
.venv/bin/python -c "import pygame; print('pygame', pygame.version.ver)"
echo "Run it with:  .venv/bin/python main.py"
