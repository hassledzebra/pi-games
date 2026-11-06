"""Which speaker and which input the games use.

Default: the system default (PipeWire/ALSA decides). To pick one device for the games only, any of:

    --output "HDMI"            (Pi Strum command line; --input "UMC" for the input)
    PI_AUDIO_OUT=HDMI  PI_AUDIO_IN=UMC           environment variables
    ~/.config/pi-games/audio.json                {"output": "HDMI", "input": "UMC202HD"}

A device is given by part of its name (case-insensitive), or an input by its index. Command line beats
environment beats the file. A name that matches nothing is reported and the system default is used.
"""
import json
import os

CONFIG = os.path.expanduser("~/.config/pi-games/audio.json")
_output = None


def _file_setting(key):
    try:
        with open(CONFIG) as f:
            value = json.load(f).get(key)
    except (OSError, ValueError, AttributeError):
        return None
    return str(value) if value else None


def configure(output=None):
    """Set the output name from the command line (None keeps the other sources)."""
    global _output
    _output = output or None


def wanted_output():
    return _output or os.environ.get("PI_AUDIO_OUT") or _file_setting("output")


def wanted_input():
    return os.environ.get("PI_AUDIO_IN") or _file_setting("input")


def output_names():
    """Names of the playback devices SDL can see (needs the pygame audio subsystem)."""
    try:
        import pygame
        import pygame._sdl2.audio as sdl_audio
        if not pygame.mixer.get_init() and not pygame.get_init():
            pygame.mixer.init()
        return list(sdl_audio.get_audio_device_names(False))
    except Exception:
        return []


def match(want, names):
    """The one name that best fits ``want``: exact first, then a part of the name. None if no fit."""
    low = want.strip().lower()
    for pick in ([n for n in names if n.lower() == low], [n for n in names if low in n.lower()]):
        if pick:
            return pick[0]
    return None


def resolve_output(want=None, names=None, log=print):
    want = want or wanted_output()
    if not want:
        return None
    names = output_names() if names is None else names
    name = match(want, names)
    if name is None:
        log("audio: no output matches %r (have: %s); using the system default" % (want, ", ".join(names) or "none"))
    return name


def open_mixer(frequency=22050, size=-16, channels=1, buffer=512):
    """(Re)open the pygame mixer on the chosen output, or the system default. Raises pygame.error."""
    import pygame
    name = resolve_output()
    if pygame.mixer.get_init():
        pygame.mixer.quit()
    if name:
        try:
            pygame.mixer.init(frequency, size, channels, buffer, devicename=name)
            return name
        except pygame.error as e:
            print("audio: could not open %r (%s); using the system default" % (name, e))
    pygame.mixer.init(frequency, size, channels, buffer)
    return None
