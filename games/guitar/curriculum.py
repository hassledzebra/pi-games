"""The learning path: stages of exercises from open strings to classical tunes.

Every exercise is written out as a MIDI file by ``write_all`` so the song loader and the backing
track renderer treat it like any downloaded song. Fingering is encoded as MIDI channel = string
number (0 = low E), which the loader understands. Tunes are traditional or public domain; riffs
and drills are original.
"""
import os
import re

import mido

from .song import STANDARD_TUNING

GUITAR, BASS, PIANO = 25, 33, 1          # General MIDI programs
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = {"C": (48, 52, 55), "D": (50, 54, 57), "E": (52, 56, 59), "F": (53, 57, 60), "G": (43, 47, 50),
          "A": (45, 49, 52), "Am": (45, 48, 52), "Em": (52, 55, 59), "Dm": (50, 53, 57)}
ROOTS = {"C": 36, "D": 38, "E": 40, "F": 41, "G": 31, "A": 33, "Am": 33, "Em": 40, "Dm": 38}


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

def _track(name, program, channel, events, tpb):
    """events: (start_beats, length_beats, midi, velocity[, channel])"""
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
    for name, program, channel, events in tracks:
        if events:
            mid.tracks.append(_track(name, program, channel, events, 480))
    return mid


def accompaniment(chords, beats_per_bar=4, style="pop"):
    """Bass + piano from one chord name per bar ('' = silence that bar)."""
    bass, piano = [], []
    for bar, ch in enumerate(chords):
        if not ch:
            continue
        t = bar * beats_per_bar
        root, triad = ROOTS[ch], CHORDS[ch]
        if style == "waltz":
            bass.append((t, 1.0, root, 90))
            piano += [(t + 1, 1.0, m, 65) for m in triad] + [(t + 2, 1.0, m, 65) for m in triad]
        elif style == "pad":
            bass.append((t, float(beats_per_bar), root, 85))
            piano += [(t, float(beats_per_bar), m, 60) for m in triad]
        else:
            for beat in range(beats_per_bar):
                bass.append((t + beat, 1.0, root if beat % 2 == 0 else root + 7, 88 if beat % 2 == 0 else 78))
            for beat in range(0, beats_per_bar, 2):
                piano += [(t + beat, 2.0, m, 65) for m in triad]
    return [("Bass", BASS, 1, bass), ("Piano", PIANO, 2, piano)]


def drums(bars, beats_per_bar=4):
    ev = []
    for bar in range(bars):
        t = bar * beats_per_bar
        for beat in range(beats_per_bar):
            ev.append((t + beat, 0.25, 36 if beat % 2 == 0 else 38, 100, 9))     # kick / snare
            ev.append((t + beat, 0.25, 42, 60, 9))                               # closed hat
            ev.append((t + beat + 0.5, 0.25, 42, 50, 9))
    return [("Drums", 1, 9, ev)]


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
    chords = ["C", "G", "C", "G", "C", "G", "C", "G"]
    tracks = accompaniment(chords[:-1]) 
    # last bar: G for two beats, then C
    t = 7 * 4
    tracks[0][3].extend([(t, 2.0, ROOTS["G"], 90), (t + 2, 2.0, ROOTS["C"], 90)])
    tracks[1][3].extend([(t, 2.0, x, 65) for x in CHORDS["G"]] + [(t + 2, 2.0, x, 65) for x in CHORDS["C"]])
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + tracks)


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
    return midi_file(100, [("Guitar", GUITAR, 0, melody(m))] + drums(8))


def blues_shuffle():
    pat = {"A": [("A2", 1), ("E3", 2), ("A2", 1), ("E3", 2), ("A2", 1), ("F#3", 2), ("A2", 1), ("F#3", 2)],
           "D": [("D3", 2), ("A3", 3), ("D3", 2), ("A3", 3), ("D3", 2), ("B3", 3), ("D3", 2), ("B3", 3)],
           "E": [("E2", 0), ("B2", 1), ("E2", 0), ("B2", 1), ("E2", 0), ("C#3", 1), ("E2", 0), ("C#3", 1)]}
    form = ["A", "A", "A", "A", "D", "D", "A", "A", "E", "D", "A", "E"]
    m = []
    for ch in form:
        m += [(name, 0.5, s) for name, s in pat[ch]]
    return midi_file(96, [("Guitar", GUITAR, 0, melody(m))] + drums(12))


def em_groove():
    bar1 = [("E2", 0.5, 0), (None, 0.5), ("E2", 0.5, 0), (None, 0.5), ("G2", 0.5, 0), ("G2", 0.5, 0), ("A2", 0.5, 1), (None, 0.5)]
    bar2 = [("E2", 0.5, 0), (None, 0.5), ("E2", 0.5, 0), (None, 0.5), ("B2", 0.5, 1), ("A2", 0.5, 1), ("G2", 0.5, 0), (None, 0.5)]
    m = (bar1 + bar2) * 4
    return midi_file(110, [("Guitar", GUITAR, 0, melody(m))] + drums(8))


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
    Stage("First tunes", "Melodies on the top two strings.", [
        Ex("3-1", "Mary Had a Little Lamb", 90, mary, "Only frets 0, 1 and 3 on the B and e strings."),
        Ex("3-2", "Twinkle Twinkle", 90, twinkle, "Watch for the jump from the B string to the e string."),
        Ex("3-3", "Ode to Joy", 100, ode_to_joy, "The dotted rhythm at the end of each half: long-short-long."),
        Ex("3-4", "Jingle Bells", 110, jingle_bells, "Repeated notes need a fresh pick stroke each time."),
        Ex("3-5", "Happy Birthday", 100, happy_birthday, "In 3/4 time. The tune starts on beat 3 of the first bar.", beats_per_bar=3),
    ]),
    Stage("Scales", "Fingers in position, every note even.", [
        Ex("4-1", "C Major Scale", 100, c_major, "Open position: fret 1 = index, fret 2 = middle, fret 3 = ring."),
        Ex("4-2", "G Major Scale", 100, g_major, "Same shape idea. Fret 4 is the pinky."),
        Ex("4-3", "E Minor Pentatonic", 90, e_minor_pentatonic, "Eighth notes now: two notes per click."),
        Ex("4-4", "A Minor Pentatonic Box", 90, a_minor_pentatonic, "Fifth fret position: index on 5, ring on 7, pinky on 8."),
    ]),
    Stage("Riffs and rhythm", "Low strings, drums, and rests that matter.", [
        Ex("5-1", "Power Riff in E", 100, power_riff, "All on the low E string. Mute with your palm for punch."),
        Ex("5-2", "Blues Shuffle in A", 96, blues_shuffle, "Twelve bars. The pattern moves to D and E, follow the lanes."),
        Ex("5-3", "E Minor Groove", 110, em_groove, "Silence is part of the riff: stop the string on the rests."),
    ]),
    Stage("Classics", "Longer tunes, faster notes, higher frets.", [
        Ex("6-1", "Greensleeves", 110, greensleeves, "Waltz time. Count 1-2-3, 1-2-3.", beats_per_bar=3),
        Ex("6-2", "Minuet in G", 100, minuet_in_g, "Petzold's minuet. Eighth-note runs between the long notes.", beats_per_bar=3),
        Ex("6-3", "Fur Elise", 120, fur_elise, "Frets 11 and 12 on the e string. Start slow with the speed setting.", beats_per_bar=3),
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
