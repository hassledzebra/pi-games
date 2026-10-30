"""Backing tracks and the metronome.

``render_backing`` writes a WAV of every MIDI track except the guitar's. It uses FluidSynth with a
General MIDI soundfont when both are installed (``apt install fluidsynth fluid-soundfont-gm``),
otherwise a small numpy synthesiser so the song still has bass and chords to play along to.
"""
import os
import shutil
import subprocess
import tempfile
import wave

import mido
import numpy as np

from .song import _tempo_map, _tick_to_seconds, track_notes

SOUNDFONTS = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/opt/homebrew/share/soundfonts/default.sf2",
    "/usr/local/share/soundfonts/default.sf2",
]


def find_soundfont():
    for p in SOUNDFONTS + [os.environ.get("SOUNDFONT", "")]:
        if p and os.path.exists(p):
            return p
    return None


def backing_path(song, speed=1.0):
    """Where the rendered backing track lives (next to the MIDI); slowed copies get a suffix."""
    if song.backing and speed >= 0.999:
        return song.backing
    base = os.path.splitext(song.backing or song.midi_path)[0]
    return base + ("" if speed >= 0.999 else "@%d" % round(speed * 100)) + ".wav"


def has_accompaniment(song):
    mid = mido.MidiFile(song.midi_path)
    return any(i != song.guitar_track and track_notes(mid, i) for i in range(len(mid.tracks)))


def ensure_backing(song, rate=22050, force=False, speed=1.0):
    """Render the backing track if it is missing. Returns the WAV path, or None if the song has
    no accompaniment tracks (metronome only). ``speed`` < 1 renders a slowed-down practice copy."""
    out = backing_path(song, speed)
    if os.path.exists(out) and not force:
        return out
    if not has_accompaniment(song):
        return None
    render_backing(song.midi_path, out, song.guitar_track, rate, speed)
    if speed >= 0.999:
        song.backing = out
    return out


def render_backing(midi_path, out_wav, mute_track, rate=22050, speed=1.0):
    mid = mido.MidiFile(midi_path)
    stripped = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat, type=1)
    for i, tr in enumerate(mid.tracks):
        if i == mute_track:
            tr = mido.MidiTrack([m for m in tr if m.is_meta])   # tempo/time-sig live here too
        if speed < 0.999:
            tr = mido.MidiTrack([m.copy(tempo=min(0xFFFFFF, int(m.tempo / speed))) if m.type == "set_tempo" else m for m in tr])
        stripped.tracks.append(tr)
    if speed < 0.999 and not any(m.type == "set_tempo" for t in stripped.tracks for m in t):
        stripped.tracks[0].insert(0, mido.MetaMessage("set_tempo", tempo=int(500000 / speed), time=0))
    sf = find_soundfont()
    exe = shutil.which("fluidsynth")
    if exe and sf:
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            stripped.save(tmp)
            cmd = [exe, "-ni", "-q", "-g", "0.8", "-r", str(rate), "-O", "s16", "-F", out_wav, sf, tmp]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _to_mono(out_wav)
            return "fluidsynth"
        except (subprocess.CalledProcessError, OSError):
            pass
        finally:
            os.unlink(tmp)
    audio = synth_midi(stripped, rate)
    write_wav(out_wav, audio, rate)
    return "numpy"


def _to_mono(path):
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    if ch == 1 and width == 2:
        return
    a = np.frombuffer(data, dtype=np.int16).reshape(-1, ch).astype(np.float32).mean(axis=1)
    write_wav(path, a / 32767.0, rate)


def write_wav(path, audio, rate):
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def synth_midi(mid, rate=22050):
    """A plain additive synth: enough to hear the chords and the groove."""
    tempos = _tempo_map(mid)
    secs = _tick_to_seconds(tempos, mid.ticks_per_beat)
    notes = []
    for i in range(len(mid.tracks)):
        for midi, s, e, vel, ch in track_notes(mid, i):
            notes.append((secs(s), secs(e), midi, vel, ch))
    if not notes:
        return np.zeros(rate, dtype=np.float32)
    length = max(e for _, e, _, _, _ in notes) + 1.0
    out = np.zeros(int(length * rate) + 1, dtype=np.float32)
    for s, e, midi, vel, ch in notes:
        a, b = int(s * rate), int(min(e + 0.3, length) * rate)
        if b <= a:
            continue
        t = np.arange(b - a) / rate
        amp = vel / 127.0 * 0.25
        if ch == 9:                                        # drums: a short noise burst
            tone = np.random.uniform(-1, 1, b - a) * np.exp(-t * 40.0) * amp
        else:
            f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
            env = np.minimum(1.0, t * 200.0) * np.exp(-t * (1.5 if midi < 48 else 2.5))
            env[int((e - s) * rate):] *= np.exp(-np.arange(len(env) - int((e - s) * rate)) / rate * 20.0)
            tone = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)) * env * amp
        out[a:b] += tone.astype(np.float32)
    peak = float(np.max(np.abs(out)))
    if peak > 0.9:
        out *= 0.9 / peak
    return out


def click(rate=22050, accent=False):
    """One metronome tick as a mono int16 buffer."""
    n = int(rate * 0.03)
    t = np.arange(n) / rate
    f = 1800.0 if accent else 1200.0
    tone = np.sin(2 * np.pi * f * t) * np.exp(-t * 120.0) * 0.6
    return (tone * 32767).astype("<i2").tobytes()
