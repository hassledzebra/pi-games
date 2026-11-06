#!/bin/sh
# Switch the Pi's system speaker (PipeWire), remembered across reboots. No sudo.
#   ./deploy/audio_out.sh list           show the outputs, * marks the current one
#   ./deploy/audio_out.sh hdmi           monitor speakers over HDMI
#   ./deploy/audio_out.sh jack           3.5 mm headphone jack
#   ./deploy/audio_out.sh respeaker      ReSpeaker USB speaker
#   ./deploy/audio_out.sh umc            Behringer UMC202HD (its headphone / line outputs)
#   ./deploy/audio_out.sh <any part of an output's name>
# Undo / back to automatic: rm ~/.local/state/wireplumber/default-nodes && systemctl --user restart wireplumber
sinks() { wpctl status | sed -n '/Sinks:/,/Sources:/p' | grep -E '^ *│? *\*? *[0-9]+\.'; }
case "$1" in
    ""|list) sinks; exit 0 ;;
    hdmi) want="HDMI" ;;
    jack|headphones|3.5) want="Built-in Audio Stereo" ;;
    respeaker) want="reSpeaker" ;;
    umc) want="UMC" ;;
    *) want="$1" ;;
esac
id=$(sinks | grep -i -- "$want" | grep -oE '[0-9]+\.' | head -1 | tr -d .)
if [ -z "$id" ]; then
    echo "No output matches '$want'. Plugged in now:"; sinks; exit 1
fi
wpctl set-default "$id" && wpctl set-mute "$id" 0
echo "Speaker is now:"; sinks | grep -E '^ *│? *\*'
