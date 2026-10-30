#!/bin/sh
# Copy Pi Brawl from this Mac/Linux machine to a Raspberry Pi over SSH.
# Usage (from the project folder):
#   ./deploy/deploy.sh                       # uses pi@raspberrypi.local
#   ./deploy/deploy.sh zheng@192.168.1.50 [dir]
#   SSH_OPTS=-6 ./deploy/deploy.sh alexhan@alexhan.local   # Wi-Fi that blocks IPv4 between clients
set -e
TARGET="${1:-pi@raspberrypi.local}"
DIR="${2:-pi-brawl}"
cd "$(dirname "$0")/.."

# one archive = fewer password prompts; skips the venv and caches.
# COPYFILE_DISABLE and --no-mac-metadata stop macOS tar adding ._* files and xattrs.
COPYFILE_DISABLE=1 tar -czf - --no-mac-metadata --no-xattrs --exclude=__pycache__ --exclude=tests/out --exclude=.DS_Store --exclude="*.wav" --exclude=songs/progress.json \
    main.py racing.py guitar.py requirements.txt README.md engine games songs deploy tests |
    ssh $SSH_OPTS "$TARGET" "mkdir -p ~/$DIR && cd ~/$DIR && tar -xzf - && chmod +x deploy/*.sh"
echo "Copied to $TARGET:~/$DIR"
echo "First time on the Pi:  cd ~/$DIR && ./deploy/install_pi.sh"
