#!/bin/sh
# Extra setup for Pi Strum (the guitar trainer). Run once on the Pi, inside the project folder,
# after ./deploy/install_pi.sh:   ./deploy/install_guitar.sh
#
# - libportaudio2: audio capture for the USB interface (python sounddevice)
# - fluidsynth + fluid-soundfont-gm: realistic backing tracks rendered from the song MIDI
#   (without them the game falls back to a simple built-in synth)
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || ./deploy/install_pi.sh
sudo apt-get update
sudo apt-get install -y libportaudio2 fluidsynth fluid-soundfont-gm
if ! .venv/bin/python -c "import numpy, mido, sounddevice" 2>/dev/null; then
    if ! .venv/bin/pip install numpy mido sounddevice; then
        echo "pip wheels unavailable - using Raspberry Pi OS packages"
        sudo apt-get install -y python3-numpy python3-mido python3-sounddevice
        rm -rf .venv
        python3 -m venv --system-site-packages .venv
        .venv/bin/pip install -r requirements.txt || true
    fi
fi
.venv/bin/python -c "import numpy, mido, sounddevice, pygame; print('guitar deps ok')"
echo "Audio inputs:"
.venv/bin/python guitar.py --list-devices || true
echo "Rendering backing tracks..."
.venv/bin/python guitar.py --render
echo
echo "Tuner test:   .venv/bin/python guitar.py --tuner"
echo "Play:         .venv/bin/python guitar.py"
