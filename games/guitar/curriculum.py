"""The learning path: stages of exercises from open strings to classical tunes.

Every exercise is written out as a MIDI file by ``write_all`` so the song loader and the backing
track renderer treat it like any downloaded song. Fingering is encoded as MIDI channel = string
number (0 = low E), which the loader understands. Tunes are traditional or public domain; riffs
and drills are original.
"""
import os
import random
import re

import mido

from .song import STANDARD_TUNING

# General MIDI programs (1-based, as in the GM tables)
GUITAR, STEEL, DIST_GUITAR, BASS, PICK_BASS, PIANO, EPIANO, STRINGS = 25, 26, 31, 34, 35, 1, 5, 49
KICK, SNARE, STICK, HAT, OPEN_HAT, RIDE, CRASH = 36, 38, 37, 42, 46, 51, 49
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# open-position voicings written like a chord chart, low E to high e ("x" = don't play)
VOICINGS = {"C": "x32010", "D": "xx0232", "E": "022100", "F": "133211", "G": "320003", "A": "x02220",
            "Am": "x02210", "Em": "022000", "Dm": "xx0231", "A7": "x02020", "D7": "xx0212", "E7": "020100",
            "G7": "320001", "C7": "x32310", "B7": "x21202"}


def voicing(name):
    """[(string, fret)] for a chord, low to high."""
    return [(s, int(f)) for s, f in enumerate(VOICINGS[name]) if f != "x"]


SHAPES = {k: tuple(STANDARD_TUNING[s] + f for s, f in voicing(k)) for k in VOICINGS}
CHORDS = {k: tuple(m for m in v if 48 <= m <= 67)[:3] for k, v in SHAPES.items()}   # compact triads for pads
ROOTS = {k: (v[0] - 12 if v[0] >= 43 else v[0]) for k, v in SHAPES.items()}          # bass root, E1..B1 range
TPB = 480


def n(name):
    """'F#4' -> 66"""
    m = re.fullmatch(r"([A-G])([#b]?)(-?\d)", name)
    midi = 12 * (int(m.group(3)) + 1) + NAMES[m.group(1)]
    return midi + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)


class Ex:
    def __init__(self, id, title, bpm, build, tip="", beats_per_bar=4, vel=100):
        self.id, self.title, self.bpm, self.build, self.tip = id, title, bpm, build, tip
        self.beats_per_bar, self.vel = beats_per_bar, vel

    @property
    def filename(self):
        return "%s %s.mid" % (self.id, self.title)


class Stage:
    def __init__(self, title, blurb, exercises):
        self.title, self.blurb, self.exercises = title, blurb, exercises


# ------------------------------------------------------------------ MIDI writing

def _track(name, program, channel, events, tpb, markers=()):
    """events: (start_beats, length_beats, midi, velocity[, channel]); markers: (beat, text)"""
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("track_name", name=name, time=0))
    used = sorted({(e[4] if len(e) > 4 else channel) for e in events} | {channel})
    for ch in used:
        if ch != 9:
            tr.append(mido.Message("program_change", program=program - 1, channel=ch, time=0))
    msgs = []
    for e in events:
        start, length, midi, vel = e[:4]
        ch = e[4] if len(e) > 4 else channel
        on, off = int(round(start * tpb)), int(round((start + length) * tpb)) - 2
        msgs.append((on, 1, mido.Message("note_on", note=midi, velocity=vel, channel=ch)))
        msgs.append((off, 0, mido.Message("note_off", note=midi, velocity=0, channel=ch)))
    for beat, text in markers:
        msgs.append((int(round(beat * tpb)), -1, mido.MetaMessage("marker", text=text)))
    msgs.sort(key=lambda m: (m[0], m[1]))
    last = 0
    for tick, _, msg in msgs:
        msg.time = tick - last
        tr.append(msg)
        last = tick
    tr.append(mido.MetaMessage("end_of_track", time=0))
    return tr


def midi_file(bpm, tracks, beats_per_bar=4):
    mid = mido.MidiFile(ticks_per_beat=480)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=beats_per_bar, denominator=4, time=0))
    meta.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(meta)
    for tr in tracks:
        name, program, channel, events = tr[:4]
        markers = tr[4] if len(tr) > 4 else ()
        if events:
            mid.tracks.append(_track(name, program, channel, events, 480, markers))
    return mid


class Arranger:
    """Builds the band from one chord per bar: drums, bass and a strummed acoustic guitar,
    with small random velocity and timing differences so it doesn't sound like a machine.
    Styles: pop (4/4 tunes), waltz (3/4), pad (scales), rock (riffs), blues (shuffle feel)."""

    def __init__(self, chords, beats_per_bar=4, style="pop", seed=1, rhythm=True):
        self.chords, self.bpb, self.style = chords, beats_per_bar, style
        self.rng = random.Random(seed)
        self.rhythm = rhythm
        self.bass, self.strum, self.pad, self.drums = [], [], [], []

    # -- helpers
    def v(self, base, spread=8):
        return max(1, min(127, base + self.rng.randint(-spread, spread)))

    def t(self, beats, jitter=0.012):
        """Beat position with a few milliseconds of human timing (never early on beat 1)."""
        off = self.rng.uniform(-jitter, jitter) if beats % self.bpb else self.rng.uniform(0, jitter / 2)
        return beats + off

    def hit(self, beat, note, vel, length=0.25):
        self.drums.append((self.t(beat, 0.006), length, note, self.v(vel, 6), 9))

    def chord(self, beat, shape, vel, length, up=False):
        """One strum: strings 12 ms apart, downstroke low to high, upstroke the other way."""
        notes = list(shape) if not up else list(reversed(shape))
        t0 = self.t(beat)
        for k, m in enumerate(notes):
            self.strum.append((t0 + k * 0.012 * self.bpb / 4, length - k * 0.012, m, self.v(vel - 4 * (k if not up else 0))))

    # -- styles
    def build(self):
        for bar, ch in enumerate(self.chords):
            t = bar * self.bpb
            if ch:
                getattr(self, "bar_" + self.style)(t, ch, bar, bar == len(self.chords) - 1)
        if self.chords and self.chords[0] and self.style != "pad":
            self.hit(0, CRASH, 90, 1.0)
        return self

    def bar_pop(self, t, ch, bar, last):
        root, shape = ROOTS[ch], SHAPES[ch]
        # drums: kick 1 and 3 (+ "and" of 3 every other bar), snare 2 and 4, hats in eighths
        for b in (0, 2):
            self.hit(t + b, KICK, 105)
        if bar % 2:
            self.hit(t + 2.5, KICK, 80)
        for b in (1, 3):
            self.hit(t + b, SNARE, 100)
        for k in range(self.bpb * 2):
            self.hit(t + k * 0.5, HAT, 78 if k % 2 == 0 else 58)
        # bass: root on 1 and 3, fifth on 2 and 4, octave pickup into the next bar
        for b in range(self.bpb):
            self.bass.append((self.t(t + b), 0.9, root if b % 2 == 0 else root + 7, self.v(96 if b % 2 == 0 else 84)))
        if not last:
            self.bass.append((self.t(t + 3.5), 0.45, root + 12, self.v(72)))
        # strum: D . D U . U D U
        pattern = ((0, 1.0, False, 92), (1, 0.5, False, 84), (1.5, 0.5, True, 70), (2.5, 0.5, True, 72), (3, 0.5, False, 84), (3.5, 0.5, True, 70))
        if last:
            pattern = ((0, 3.5, False, 96),)
        for beat, length, up, vel in pattern:
            self.chord(t + beat, shape, vel, length, up)

    def bar_waltz(self, t, ch, bar, last):
        root, shape = ROOTS[ch], SHAPES[ch]
        self.hit(t, KICK, 96)
        self.hit(t + 1, STICK, 70)
        self.hit(t + 2, STICK, 64)
        for b in range(3):
            self.hit(t + b, HAT, 60)
        self.bass.append((self.t(t), 1.8, root, self.v(96)))
        self.bass.append((self.t(t + 2), 0.9, root + 7 if bar % 2 == 0 else root + 12, self.v(78)))
        if last:
            self.chord(t, shape, 94, 2.8)
        else:
            self.chord(t + 1, shape, 82, 0.9)
            self.chord(t + 2, shape, 74, 0.9, up=True)

    def bar_pad(self, t, ch, bar, last):
        root, triad = ROOTS[ch], CHORDS[ch]
        for m in triad:
            self.pad.append((t, float(self.bpb), m, 64))
        self.bass.append((self.t(t), self.bpb - 0.2, root, self.v(90)))
        for b in range(self.bpb):
            self.hit(t + b, HAT, 52 if b else 66)
        self.hit(t, KICK, 70)

    def bar_rock(self, t, ch, bar, last):
        root = ROOTS[ch]
        for b in (0, 2):
            self.hit(t + b, KICK, 110)
        self.hit(t + 1.5, KICK, 90)
        for b in (1, 3):
            self.hit(t + b, SNARE, 108)
        for k in range(self.bpb * 2):
            self.hit(t + k * 0.5, HAT if k % 2 == 0 else OPEN_HAT if k == 7 else HAT, 88 if k % 2 == 0 else 66)
        for k in range(self.bpb * 2):
            self.bass.append((self.t(t + k * 0.5), 0.45, root, self.v(104 if k % 2 == 0 else 92)))
        if last:
            self.strum.append((t, 3.5, root + 12, 100))
            self.strum.append((t, 3.5, root + 19, 96))

    def bar_blues(self, t, ch, bar, last):
        root = ROOTS[ch]
        swing = 0.67                                 # the "and" lands late: a shuffle
        self.hit(t, KICK, 104)
        self.hit(t + 2, KICK, 100)
        for b in (1, 3):
            self.hit(t + b, SNARE, 98)
        for b in range(self.bpb):
            self.hit(t + b, RIDE, 82)
            self.hit(t + b + swing, RIDE, 60)
        walk = (root, root + 4, root + 7, root + 9) if bar % 2 == 0 else (root + 10, root + 9, root + 7, root + 4)
        for b, m in enumerate(walk):
            self.bass.append((self.t(t + b), 0.9, m, self.v(98)))
        if last:
            self.strum.append((t, 3.5, root + 12, 96))
            self.strum.append((t, 3.5, root + 16, 90))
            self.strum.append((t, 3.5, root + 22, 90))

    def tracks(self):
        self.build()
        out = []
        if self.drums:
            out.append(("Drums", 1, 9, self.drums))
        if self.bass:
            out.append(("Bass", PICK_BASS if self.style in ("rock", "blues") else BASS, 1, self.bass))
        if self.strum and self.rhythm:
            out.append(("Rhythm", DIST_GUITAR if self.style == "rock" else STEEL, 2, self.strum))
        if self.pad:
            out.append(("Strings", STRINGS, 3, self.pad))
        return out


def accompaniment(chords, beats_per_bar=4, style="pop", seed=1, rhythm=True):
    """Bass, drums and rhythm guitar from one chord name per bar ('' = silence that bar)."""
    return Arranger(chords, beats_per_bar, style, seed, rhythm).tracks()


HARMONICA, FLUTE, VIOLIN = 23, 74, 41

PATTERNS = {                       # strum patterns per bar as (beat, upstroke)
    "1": [(0, False)],
    "1-3": [(0, False), (2, False)],
    "beats": [(0, False), (1, False), (2, False), (3, False)],
    "D-DU-DU": [(0, False), (1, False), (2, False), (2.5, True), (3, False), (3.5, True)],
    "pop": [(0, False), (1, False), (1.5, True), (2.5, True), (3, False), (3.5, True)],
    "blues": [(0, False), (1, False), (1.5, True), (2, False), (2.5, True), (3, False), (3.5, True)],
    "waltz": [(0, False), (1, False), (1.5, True), (2, False), (2.5, True)],
    "waltz-1": [(0, False), (2, False)],
}


def chord_part(bars, pattern, bpm, beats_per_bar=4, vel=96):
    """The player's strummed part: a "Chords" track with one marker per chord and the strums as
    notes (12 ms apart, low to high on a downstroke). bars: one chord name per bar, or
    (name, beats) pairs for chords shorter than a bar."""
    events, markers, beat = [], [], 0.0
    for item in bars:
        name, length = (item, float(beats_per_bar)) if isinstance(item, str) else item
        if name:
            markers.append((beat, "chord:" + name))
            strums = [(b, up) for b, up in PATTERNS[pattern] if b < length]
            for k, (b, up) in enumerate(strums):
                nxt = strums[k + 1][0] if k + 1 < len(strums) else length
                notes = voicing(name) if not up else list(reversed(voicing(name)))
                for j, (string, fret) in enumerate(notes):
                    t = beat + b + j * 0.012 * bpm / 60.0    # strings 12 ms apart
                    events.append((t, max(0.1, nxt - b - j * 0.02), STANDARD_TUNING[string] + fret, vel - 3 * j, string))
        beat += length
    return ("Chords", GUITAR, 0, events, markers)


def lead(seq, program=HARMONICA, channel=4, vel=88, start=0.0):
    """The tune on a lead instrument, so a chord exercise still sounds like the song."""
    ev = [(t, l, m, vel, channel) for (t, l, m, _v, *rest) in melody(seq, vel, start)]
    return ("Lead", program, channel, ev)


def drums(bars, beats_per_bar=4, roots=None, style="rock"):
    """Drums and bass for a riff: ``roots`` is one chord name per bar (default E)."""
    return Arranger(roots or ["E"] * bars, beats_per_bar, style).tracks()


def melody(seq, vel=100, start=0.0):
    """seq: (note_name | midi | None for a rest, beats[, string]) -> guitar events."""
    ev, b = [], start
    for item in seq:
        name, length = item[0], item[1]
        if name is not None:
            midi = n(name) if isinstance(name, str) else name
            e = [b, length, midi, vel]
            if len(item) > 2:
                e.append(item[2])
            ev.append(tuple(e))
        b += length
    return ev


def frets(seq, length=1.0, vel=100):
    """seq of (string, fret) -> guitar events, one per beat; string encoded as the channel."""
    return [(i * length, length, STANDARD_TUNING[s] + f, vel, s) for i, (s, f) in enumerate(seq)]


# ------------------------------------------------------------------ stage 1: open strings

def open_strings():
    seq = [(s, 0) for s in range(6)] + [(s, 0) for s in reversed(range(6))]
    return midi_file(60, [("Guitar", GUITAR, 0, frets(seq, 2.0))])


def string_pairs():
    seq = [(0, 0), (1, 0)] * 2 + [(2, 0), (3, 0)] * 2 + [(4, 0), (5, 0)] * 2 + [(3, 0), (2, 0)] * 2 + [(1, 0), (0, 0)] * 2
    return midi_file(70, [("Guitar", GUITAR, 0, frets(seq))])


def string_skips():
    seq = [(0, 0), (2, 0), (1, 0), (3, 0), (2, 0), (4, 0), (3, 0), (5, 0),
           (5, 0), (3, 0), (4, 0), (2, 0), (3, 0), (1, 0), (2, 0), (0, 0)]
    return midi_file(70, [("Guitar", GUITAR, 0, frets(seq))])


# ------------------------------------------------------------------ stage 2: first frets

def first_frets():
    seq = []
    for s in (5, 4):
        seq += [(s, 0), (s, 1), (s, 3), (s, 1)] * 2
    for s in (3, 2):
        seq += [(s, 0), (s, 2), (s, 0), (s, 2), (s, 0), (s, 2), (s, 3), (s, 2)]
    return midi_file(70, [("Guitar", GUITAR, 0, frets(seq))])


def chromatic():
    seq = [(s, f) for s in range(6) for f in (1, 2, 3, 4)] + [(s, f) for s in reversed(range(6)) for f in (4, 3, 2, 1)]
    return midi_file(80, [("Guitar", GUITAR, 0, frets(seq))])


def spider():
    seq = [(s, f) for s in range(6) for f in (1, 3, 2, 4)] + [(s, f) for s in reversed(range(6)) for f in (4, 2, 3, 1)]
    return midi_file(80, [("Guitar", GUITAR, 0, frets(seq))])


# ------------------------------------------------------------------ stage 3: first tunes

def mary():
    m = [("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2),
         ("D4", 1), ("D4", 1), ("D4", 2), ("E4", 1), ("G4", 1), ("G4", 2),
         ("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 1), ("E4", 1),
         ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 1), ("C4", 4)]
    return midi_file(90, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(["C", "C", "G", "C", "C", "C", "G", "C"]))


def twinkle():
    a = [("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
         ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2)]
    b = [("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2)]
    m = a + b + b + a
    chords = ["C", "C", "F", "G", "C", "G", "C", "G", "C", "C", "F", "G"]
    return midi_file(90, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords))


def ode_to_joy():
    a = [("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
         ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1)]
    m = a + [("E4", 1.5), ("D4", 0.5), ("D4", 2)] + a + [("D4", 1.5), ("C4", 0.5), ("C4", 2)]
    chords = ["C", "G", "C", "G", "C", "G", "C", "C"]
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords))


def jingle_bells():
    half = [("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("E4", 1), ("E4", 2),
            ("E4", 1), ("G4", 1), ("C4", 1.5), ("D4", 0.5), ("E4", 4),
            ("F4", 1), ("F4", 1), ("F4", 1.5), ("F4", 0.5), ("F4", 1), ("E4", 1), ("E4", 1), ("E4", 0.5), ("E4", 0.5)]
    m = half + [("E4", 1), ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 2), ("G4", 2)]
    m += half + [("G4", 1), ("G4", 1), ("F4", 1), ("D4", 1), ("C4", 4)]
    chords = ["C", "C", "C", "C", "F", "C", "G", "G", "C", "C", "C", "C", "F", "C", "G", "C"]
    return midi_file(110, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords))


def happy_birthday():
    m = [(None, 2), ("D4", 0.75), ("D4", 0.25), ("E4", 1), ("D4", 1), ("G4", 1), ("F#4", 2), ("D4", 0.75), ("D4", 0.25),
         ("E4", 1), ("D4", 1), ("A4", 1), ("G4", 2), ("D4", 0.75), ("D4", 0.25), ("D5", 1), ("B4", 1), ("G4", 1),
         ("F#4", 1), ("E4", 1), ("C5", 0.75), ("C5", 0.25), ("B4", 1), ("G4", 1), ("A4", 1), ("G4", 2)]
    chords = ["G", "G", "D", "D", "G", "G", "C", "D", "G"]
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords, 3, "waltz"), beats_per_bar=3)


# ------------------------------------------------------------------ stage 4: scales

def c_major():
    up = [(0, 0), (0, 1), (0, 3), (1, 0), (1, 2), (1, 3), (2, 0), (2, 2), (2, 3), (3, 0), (3, 2), (4, 0), (4, 1), (4, 3), (5, 0), (5, 1), (5, 3)]
    seq = up + up[-2::-1]
    bars = (len(seq) + 3) // 4
    return midi_file(100, [("Guitar", GUITAR, 0, frets(seq))] + accompaniment(["C"] * bars, 4, "pad"))


def g_major():
    up = [(0, 3), (1, 0), (1, 2), (1, 3), (2, 0), (2, 2), (2, 4), (3, 0), (3, 2), (4, 0), (4, 1), (4, 3), (5, 0), (5, 2), (5, 3)]
    seq = up + up[-2::-1]
    bars = (len(seq) + 3) // 4
    return midi_file(100, [("Guitar", GUITAR, 0, frets(seq))] + accompaniment(["G"] * bars, 4, "pad"))


def e_minor_pentatonic():
    up = [(0, 0), (0, 3), (1, 0), (1, 2), (2, 0), (2, 2), (3, 0), (3, 2), (4, 0), (4, 3), (5, 0), (5, 3)]
    seq = up + up[-2::-1]
    bars = (len(seq) + 7) // 8
    return midi_file(90, [("Guitar", GUITAR, 0, frets(seq, 0.5))] + accompaniment(["Em"] * bars, 4, "pad"))


def a_minor_pentatonic():
    up = [(0, 5), (0, 8), (1, 5), (1, 7), (2, 5), (2, 7), (3, 5), (3, 7), (4, 5), (4, 8), (5, 5), (5, 8)]
    seq = up + up[-2::-1]
    bars = (len(seq) + 7) // 8
    return midi_file(90, [("Guitar", GUITAR, 0, frets(seq, 0.5))] + accompaniment(["Am"] * bars, 4, "pad"))


# ------------------------------------------------------------------ stage 5: riffs

def power_riff():
    bar_a = [("E2", 1, 0), ("E2", 1, 0), ("G2", 1, 0), ("A2", 1, 0)]
    bar_b = [("E2", 1, 0), ("E2", 1, 0), ("Bb2", 0.5, 0), ("A2", 1.5, 0)]
    m = (bar_a + bar_b) * 4
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + drums(8, roots=["E"] * 8))


def blues_shuffle():
    pat = {"A": [("A2", 1), ("E3", 2), ("A2", 1), ("E3", 2), ("A2", 1), ("F#3", 2), ("A2", 1), ("F#3", 2)],
           "D": [("D3", 2), ("A3", 3), ("D3", 2), ("A3", 3), ("D3", 2), ("B3", 3), ("D3", 2), ("B3", 3)],
           "E": [("E2", 0), ("B2", 1), ("E2", 0), ("B2", 1), ("E2", 0), ("C#3", 1), ("E2", 0), ("C#3", 1)]}
    form = ["A", "A", "A", "A", "D", "D", "A", "A", "E", "D", "A", "E"]
    m = []
    for ch in form:
        m += [(name, 0.5, s) for name, s in pat[ch]]
    return midi_file(96, [("Guitar", GUITAR, 0, melody(m))] + drums(12, roots=form, style="blues"))


def em_groove():
    bar1 = [("E2", 0.5, 0), (None, 0.5), ("E2", 0.5, 0), (None, 0.5), ("G2", 0.5, 0), ("G2", 0.5, 0), ("A2", 0.5, 1), (None, 0.5)]
    bar2 = [("E2", 0.5, 0), (None, 0.5), ("E2", 0.5, 0), (None, 0.5), ("B2", 0.5, 1), ("A2", 0.5, 1), ("G2", 0.5, 0), (None, 0.5)]
    m = (bar1 + bar2) * 4
    return midi_file(110, [("Guitar", GUITAR, 0, melody(m))] + drums(8, roots=["Em"] * 8))


# ------------------------------------------------------------------ stage 6: classics

def greensleeves():
    e = 0.5
    bars = [[(None, 4 * e), ("A4", 2 * e)], [("C5", 4 * e), ("D5", 2 * e)], [("E5", 3 * e), ("F5", e), ("E5", 2 * e)],
            [("D5", 4 * e), ("B4", 2 * e)], [("G4", 3 * e), ("A4", e), ("B4", 2 * e)], [("C5", 4 * e), ("A4", 2 * e)],
            [("A4", 3 * e), ("G#4", e), ("A4", 2 * e)], [("B4", 4 * e), ("G#4", 2 * e)], [("E4", 4 * e), ("A4", 2 * e)],
            [("C5", 4 * e), ("D5", 2 * e)], [("E5", 3 * e), ("F5", e), ("E5", 2 * e)], [("D5", 4 * e), ("B4", 2 * e)],
            [("G4", 3 * e), ("A4", e), ("B4", 2 * e)], [("C5", 3 * e), ("B4", e), ("A4", 2 * e)],
            [("G#4", 3 * e), ("F#4", e), ("G#4", 2 * e)], [("A4", 6 * e)], [("A4", 6 * e)]]
    chords = ["Am", "C", "C", "G", "G", "Am", "Am", "E", "Am", "C", "C", "G", "G", "Am", "E", "Am", "Am"]
    m = [x for bar in bars for x in bar]
    return midi_file(110, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords, 3, "waltz"), beats_per_bar=3)


def minuet_in_g():
    m = [("D5", 1), ("G4", 0.5), ("A4", 0.5), ("B4", 0.5), ("C5", 0.5), ("D5", 1), ("G4", 1), ("G4", 1),
         ("E5", 1), ("C5", 0.5), ("D5", 0.5), ("E5", 0.5), ("F#5", 0.5), ("G5", 1), ("G4", 1), ("G4", 1),
         ("C5", 1), ("D5", 0.5), ("C5", 0.5), ("B4", 0.5), ("A4", 0.5), ("B4", 1), ("C5", 0.5), ("B4", 0.5), ("A4", 0.5), ("G4", 0.5),
         ("F#4", 1), ("G4", 0.5), ("A4", 0.5), ("B4", 0.5), ("G4", 0.5), ("A4", 3)]
    chords = ["G", "G", "C", "G", "C", "G", "D", "D"]
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords, 3, "waltz"), beats_per_bar=3)


def fur_elise():
    e = 0.5
    m = [(None, 2 * e), ("E5", e), ("D#5", e),
         ("E5", e), ("D#5", e), ("E5", e), ("B4", e), ("D5", e), ("C5", e),
         ("A4", 3 * e), ("C4", e), ("E4", e), ("A4", e),
         ("B4", 3 * e), ("E4", e), ("G#4", e), ("B4", e),
         ("C5", 3 * e), ("E4", e), ("E5", e), ("D#5", e),
         ("E5", e), ("D#5", e), ("E5", e), ("B4", e), ("D5", e), ("C5", e),
         ("A4", 3 * e), ("C4", e), ("E4", e), ("A4", e),
         ("B4", 3 * e), ("E4", e), ("C5", e), ("B4", e),
         ("A4", 6 * e)]
    chords = ["", "", "Am", "E", "Am", "", "Am", "E", "Am"]
    return midi_file(120, [("Guitar", GUITAR, 0, melody(m))] + accompaniment(chords, 3, "waltz"), beats_per_bar=3)


# ------------------------------------------------------------------ chords

def chord_drill(bars, pattern, bpm, style="pop", beats_per_bar=4):
    return midi_file(bpm, [chord_part(bars, pattern, bpm, beats_per_bar)]
                     + accompaniment(bars, beats_per_bar, style, rhythm=False), beats_per_bar)


def em_am():
    return chord_drill(["Em", "Em", "Am", "Am"] * 2, "1", 70)


def d_g():
    return chord_drill(["D", "D", "G", "G"] * 2, "1", 70)


def g_c_d():
    return chord_drill(["G", "C", "D", "G"] * 2, "1-3", 80)


def four_chords():
    return chord_drill(["Em", "Am", "D", "G"] * 2, "beats", 80)


def down_up():
    return chord_drill(["G", "Em", "C", "D"] * 2, "D-DU-DU", 90)


def pop_strum():
    return chord_drill(["G", "D", "Em", "C"] * 2, "pop", 96)


def blues_chords():
    return chord_drill(["A7", "A7", "A7", "A7", "D7", "D7", "A7", "A7", "E7", "D7", "A7", "E7"], "blues", 96, "blues")


def waltz_strum():
    return chord_drill(["Am", "Dm", "G", "C"] * 2, "waltz", 100, "waltz", 3)


def chord_song(melody_seq, bars, pattern, bpm, style="pop", beats_per_bar=4, instrument=HARMONICA, start=0.0):
    return midi_file(bpm, [chord_part(bars, pattern, bpm, beats_per_bar), lead(melody_seq, instrument, start=start)]
                     + accompaniment(bars, beats_per_bar, style, rhythm=False), beats_per_bar)


def twinkle_chords():
    a = [("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
         ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2)]
    b = [("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2)]
    chords = ["C", "C", "F", "G", "C", "G", "C", "G", "C", "C", "F", "G"]
    return chord_song(a + b + b + a, chords, "D-DU-DU", 90)


def ode_chords():
    a = [("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
         ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1)]
    m = a + [("E4", 1.5), ("D4", 0.5), ("D4", 2)] + a + [("D4", 1.5), ("C4", 0.5), ("C4", 2)]
    return chord_song(m, ["C", "G", "C", "G", "C", "G", "C", "C"], "pop", 100, instrument=FLUTE)


def jingle_chords():
    half = [("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("E4", 1), ("E4", 2),
            ("E4", 1), ("G4", 1), ("C4", 1.5), ("D4", 0.5), ("E4", 4),
            ("F4", 1), ("F4", 1), ("F4", 1.5), ("F4", 0.5), ("F4", 1), ("E4", 1), ("E4", 1), ("E4", 0.5), ("E4", 0.5)]
    m = half + [("E4", 1), ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 2), ("G4", 2)]
    m += half + [("G4", 1), ("G4", 1), ("F4", 1), ("D4", 1), ("C4", 4)]
    chords = ["C", "C", "C", "C", "F", "C", "G", "G", "C", "C", "C", "C", "F", "C", "G", "C"]
    return chord_song(m, chords, "pop", 110)


def birthday_chords():
    m = [(None, 2), ("D4", 0.75), ("D4", 0.25), ("E4", 1), ("D4", 1), ("G4", 1), ("F#4", 2), ("D4", 0.75), ("D4", 0.25),
         ("E4", 1), ("D4", 1), ("A4", 1), ("G4", 2), ("D4", 0.75), ("D4", 0.25), ("D5", 1), ("B4", 1), ("G4", 1),
         ("F#4", 1), ("E4", 1), ("C5", 0.75), ("C5", 0.25), ("B4", 1), ("G4", 1), ("A4", 1), ("G4", 2)]
    return chord_song(m, ["G", "G", "D", "D", "G", "G", "C", "D", "G"], "waltz", 100, "waltz", 3, VIOLIN)


def greensleeves_chords():
    e = 0.5
    bars = [[(None, 4 * e), ("A4", 2 * e)], [("C5", 4 * e), ("D5", 2 * e)], [("E5", 3 * e), ("F5", e), ("E5", 2 * e)],
            [("D5", 4 * e), ("B4", 2 * e)], [("G4", 3 * e), ("A4", e), ("B4", 2 * e)], [("C5", 4 * e), ("A4", 2 * e)],
            [("A4", 3 * e), ("G#4", e), ("A4", 2 * e)], [("B4", 4 * e), ("G#4", 2 * e)], [("E4", 4 * e), ("A4", 2 * e)],
            [("C5", 4 * e), ("D5", 2 * e)], [("E5", 3 * e), ("F5", e), ("E5", 2 * e)], [("D5", 4 * e), ("B4", 2 * e)],
            [("G4", 3 * e), ("A4", e), ("B4", 2 * e)], [("C5", 3 * e), ("B4", e), ("A4", 2 * e)],
            [("G#4", 3 * e), ("F#4", e), ("G#4", 2 * e)], [("A4", 6 * e)], [("A4", 6 * e)]]
    chords = ["Am", "C", "C", "G", "G", "Am", "Am", "E", "Am", "C", "C", "G", "G", "Am", "E", "Am", "Am"]
    m = [x for bar in bars for x in bar]
    return chord_song(m, chords, "waltz", 110, "waltz", 3, FLUTE)


def rising_sun():
    """House of the Rising Sun (traditional): the classic Am C D F / Am C E progression, in 3/4."""
    chords = ["Am", "C", "D", "F", "Am", "C", "E", "E", "Am", "C", "D", "F", "Am", "E", "Am", "Am"]
    return chord_drill(chords, "waltz", 110, "waltz", 3)


STAGES = [
    Stage("Open strings", "Get a clean sound from every string and hit the beat.", [
        Ex("1-1", "Open Strings", 60, open_strings, "Pick each string once. Let it ring for the whole note."),
        Ex("1-2", "String Pairs", 70, string_pairs, "Keep the pick moving the same way on every string."),
        Ex("1-3", "String Skips", 70, string_skips, "Look at the lane, not your pick hand."),
    ]),
    Stage("First frets", "One finger per fret, right behind the fret wire.", [
        Ex("2-1", "First Frets", 70, first_frets, "Index on fret 1, ring on fret 3. Press just hard enough for a clean note."),
        Ex("2-2", "Chromatic Warm-up", 80, chromatic, "Frets 1-2-3-4 with fingers 1-2-3-4. Keep fingers close to the strings."),
        Ex("2-3", "Spider Walk", 80, spider, "1-3-2-4: this builds finger independence."),
    ]),
    Stage("First chords", "Two-finger chords first, then the big open shapes.", [
        Ex("3-1", "Em and Am", 70, em_am, "Em is fingers 2 and 3 on the A and D strings. Slide the same shape down a string for Am, and add finger 1."),
        Ex("3-2", "D and G", 70, d_g, "D is a triangle on the top three strings. G stretches across all six: strum them all."),
        Ex("3-3", "G, C and D Changes", 80, g_c_d, "Move the fingers together, not one at a time. Strum on beats 1 and 3."),
        Ex("3-4", "Em Am D G", 80, four_chords, "One strum per beat. Start the change on the last beat of each bar."),
    ]),
    Stage("First tunes", "Melodies on the top two strings.", [
        Ex("4-1", "Mary Had a Little Lamb", 90, mary, "Only frets 0, 1 and 3 on the B and e strings."),
        Ex("4-2", "Twinkle Twinkle", 90, twinkle, "Watch for the jump from the B string to the e string."),
        Ex("4-3", "Ode to Joy", 100, ode_to_joy, "The dotted rhythm at the end of each half: long-short-long."),
        Ex("4-4", "Jingle Bells", 110, jingle_bells, "Repeated notes need a fresh pick stroke each time."),
        Ex("4-5", "Happy Birthday", 100, happy_birthday, "In 3/4 time. The tune starts on beat 3 of the first bar.", beats_per_bar=3),
    ]),
    Stage("Strumming", "Patterns that make four chords sound like a song.", [
        Ex("5-1", "Down, Down-Up", 90, down_up, "D D DU DU. Keep the hand swinging even when it misses the strings."),
        Ex("5-2", "The Pop Pattern", 96, pop_strum, "D DU UDU: skip the downstroke on beat 3. G D Em C is the sound of a thousand songs."),
        Ex("5-3", "12-Bar Blues", 96, blues_chords, "A7, D7 and E7 over the twelve-bar form. Count the bars: four, two, two, one, one, two."),
        Ex("5-4", "Waltz Strum", 100, waltz_strum, "D DU DU in 3/4. Am, Dm, G, C.", beats_per_bar=3),
    ]),
    Stage("Scales", "Fingers in position, every note even.", [
        Ex("6-1", "C Major Scale", 100, c_major, "Open position: fret 1 = index, fret 2 = middle, fret 3 = ring."),
        Ex("6-2", "G Major Scale", 100, g_major, "Same shape idea. Fret 4 is the pinky."),
        Ex("6-3", "E Minor Pentatonic", 90, e_minor_pentatonic, "Eighth notes now: two notes per click."),
        Ex("6-4", "A Minor Pentatonic Box", 90, a_minor_pentatonic, "Fifth fret position: index on 5, ring on 7, pinky on 8."),
    ]),
    Stage("Chord songs", "Strum the chords while the band plays the tune.", [
        Ex("7-1", "Twinkle Twinkle", 90, twinkle_chords, "C, F and G. F is the hard one: barre strings 1 and 2 with the index finger, or play just the top four strings."),
        Ex("7-2", "Ode to Joy", 100, ode_chords, "Only C and G, but the pop pattern all the way through."),
        Ex("7-3", "Jingle Bells", 110, jingle_chords, "Watch for the F in bar 5 and bar 13."),
        Ex("7-4", "Happy Birthday", 100, birthday_chords, "G, D and C in waltz time.", beats_per_bar=3),
        Ex("7-5", "Greensleeves", 110, greensleeves_chords, "Am, C, G and E. The E major chord is the colour of this tune.", beats_per_bar=3),
        Ex("7-6", "House of the Rising Sun", 110, rising_sun, "The famous Am C D F progression. Traditional song, public domain.", beats_per_bar=3),
    ]),
    Stage("Riffs and rhythm", "Low strings, drums, and rests that matter.", [
        Ex("8-1", "Power Riff in E", 100, power_riff, "All on the low E string. Mute with your palm for punch."),
        Ex("8-2", "Blues Shuffle in A", 96, blues_shuffle, "Twelve bars. The pattern moves to D and E, follow the lanes."),
        Ex("8-3", "E Minor Groove", 110, em_groove, "Silence is part of the riff: stop the string on the rests."),
    ]),
    Stage("Classics", "Longer tunes, faster notes, higher frets.", [
        Ex("9-1", "Greensleeves", 110, greensleeves, "Waltz time. Count 1-2-3, 1-2-3.", beats_per_bar=3),
        Ex("9-2", "Minuet in G", 100, minuet_in_g, "Petzold's minuet. Eighth-note runs between the long notes.", beats_per_bar=3),
        Ex("9-3", "Fur Elise", 120, fur_elise, "Frets 11 and 12 on the e string. Start slow with the speed setting.", beats_per_bar=3),
    ]),
]

EXERCISES = {ex.id: ex for st in STAGES for ex in st.exercises}
PATH_DIR = "path"


def write_all(songs_dir):
    """Write every exercise MIDI (if missing) under songs/path/. Returns {ex.id: path}."""
    folder = os.path.join(songs_dir, PATH_DIR)
    os.makedirs(folder, exist_ok=True)
    out = {}
    for st in STAGES:
        for ex in st.exercises:
            p = os.path.join(folder, ex.filename)
            if not os.path.exists(p):
                ex.build().save(p)
            out[ex.id] = p
    return out
