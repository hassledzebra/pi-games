"""Backing tracks and the metronome.

``render_backing`` writes a stereo 44.1 kHz WAV of every MIDI track except the guitar's, using
the first renderer that works:

1. tinysoundfont (pip package, no system install) with a General MIDI soundfont,
2. the FluidSynth command (``apt install fluidsynth``) with the same soundfont,
3. a small numpy synthesiser, so the song still has bass and chords to play along to.

The soundfont is GeneralUser GS (free, ~32 MB). ``ensure_soundfont`` downloads it into
``soundfonts/`` on first use; a system soundfont is used if one is already installed.
"""
import os
import shutil
import subprocess
import tempfile
import urllib.request
import wave

import mido
import numpy as np

from .song import _tempo_map, _tick_to_seconds, track_notes

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOUNDFONT_DIR = os.path.join(ROOT, "soundfonts")
GENERALUSER_URL = "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2"
GENERALUSER_MIN_BYTES = 30_000_000
RATE = 44100
SOUNDFONTS = [
    os.path.join(SOUNDFONT_DIR, "GeneralUser-GS.sf2"),
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
]


def find_soundfont():
    for p in [os.environ.get("SOUNDFONT", "")] + SOUNDFONTS:
        if p and os.path.exists(p):
            return p
    return None


def ensure_soundfont(log=print):
    """The best soundfont available, downloading GeneralUser GS if there is none."""
    sf = find_soundfont()
    if sf:
        return sf
    target = SOUNDFONTS[0]
    os.makedirs(SOUNDFONT_DIR, exist_ok=True)
    tmp = target + ".part"
    try:
        log("Downloading GeneralUser GS soundfont (32 MB)...")
        urllib.request.urlretrieve(GENERALUSER_URL, tmp)
        if os.path.getsize(tmp) < GENERALUSER_MIN_BYTES:
            raise OSError("download too small")
        os.replace(tmp, target)
        return target
    except Exception as e:
        log("Soundfont download failed (%s); using the built-in synth" % e)
        if os.path.exists(tmp):
            os.unlink(tmp)
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


def ensure_backing(song, rate=RATE, force=False, speed=1.0):
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


def render_backing(midi_path, out_wav, mute_track, rate=RATE, speed=1.0):
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
    sf = ensure_soundfont()
    if sf:
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            stripped.save(tmp)
            audio = render_tinysoundfont(tmp, sf, rate)
            if audio is not None:
                write_wav(out_wav, audio, rate)
                return "tinysoundfont"
            if render_fluidsynth(tmp, sf, out_wav, rate):
                return "fluidsynth"
        finally:
            os.unlink(tmp)
    audio = synth_midi(stripped, rate)
    write_wav(out_wav, audio, rate)
    return "numpy"


def render_tinysoundfont(midi_path, soundfont, rate):
    """Offline render with the tinysoundfont package. Returns float32 (n, 2) or None."""
    try:
        import tinysoundfont
    except ImportError:
        return None
    try:
        synth = tinysoundfont.Synth(gain=-6.0, samplerate=rate)
        synth.sfload(soundfont)
        seq = tinysoundfont.Sequencer(synth)
        seq.midi_load(midi_path)
        chunks, block, tail = [], 2048, 0
        while True:
            buf = synth.generate(block)
            a = np.frombuffer(buf, dtype=np.float32).reshape(-1, 2).copy()
            chunks.append(a)
            if seq.is_empty():
                tail += 1
                if tail * block > rate * 2.0 or np.max(np.abs(a)) < 1e-4 and tail * block > rate * 0.5:
                    break
            if len(chunks) * block > rate * 1800:          # 30 minutes: something is wrong
                break
        return _normalise(np.concatenate(chunks))
    except Exception as e:  # a broken soundfont, an API change...
        print("tinysoundfont failed: %s" % e)
        return None


def render_fluidsynth(midi_path, soundfont, out_wav, rate):
    exe = shutil.which("fluidsynth")
    if not exe:
        return False
    cmd = [exe, "-ni", "-q", "-g", "0.7", "-r", str(rate), "-O", "s16", "-R", "1", "-C", "1", "-F", out_wav, soundfont, midi_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return False
    with wave.open(out_wav, "rb") as w:
        ch, n = w.getnchannels(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32767.0
    write_wav(out_wav, _normalise(a.reshape(-1, ch)), rate)
    return True


def _normalise(audio, peak_db=-1.0):
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1e-6:
        audio = audio * (10 ** (peak_db / 20.0) / peak)
    return audio


def write_wav(path, audio, rate):
    audio = np.asarray(audio, dtype=np.float32)
    channels = 1 if audio.ndim == 1 else audio.shape[1]
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def synth_midi(mid, rate=RATE):
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


def click(rate=RATE, accent=False, channels=1):
    """One metronome tick as a mono int16 buffer."""
    n = int(rate * 0.03)
    t = np.arange(n) / rate
    f = 1800.0 if accent else 1200.0
    tone = np.sin(2 * np.pi * f * t) * np.exp(-t * 120.0) * 0.6
    pcm = (tone * 32767).astype("<i2")
    return np.repeat(pcm, channels).tobytes()
