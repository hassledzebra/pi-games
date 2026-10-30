"""Chord recognition for strummed chords.

Single notes are tracked by YIN in ``pitch.py``; a strummed chord has several fundamentals at
once, so here the frame's spectrum is folded into a 12-bin *chroma* (energy per pitch class) and
compared with the template of the chord the song expects. The judge only asks "does this sound
like the expected chord?", which is far easier than naming an unknown chord, so open-chord
strumming on a direct input is recognised reliably.
"""
import math

import numpy as np

from .pitch import RATE

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
             "sus4": (0, 5, 7), "sus2": (0, 2, 7), "5": (0, 7), "dim": (0, 3, 6)}


def parse_chord(name):
    """'Am7' -> (root_pc, quality). Returns None for '' or unknown names."""
    if not name:
        return None
    root = name[0].upper()
    i = 1
    if i < len(name) and name[i] in "#b":
        root += name[i]
        i += 1
    pc = PITCH_CLASSES.index(root.replace("Db", "C#").replace("Eb", "D#").replace("Gb", "F#").replace("Ab", "G#").replace("Bb", "A#"))
    quality = name[i:]
    if quality not in QUALITIES:
        quality = "m" if quality.startswith("m") and not quality.startswith("maj") else ""
    return pc, quality


def template(name):
    """12-bin weights for a chord: root strongest, fifth next, then thirds and sevenths."""
    parsed = parse_chord(name)
    if parsed is None:
        return None
    pc, quality = parsed
    t = np.zeros(12)
    for k, interval in enumerate(QUALITIES[quality]):
        t[(pc + interval) % 12] = 1.0 if k == 0 else 0.8 if interval == 7 else 0.7
    return t / np.linalg.norm(t)


class ChromaAnalyser:
    """Chroma of an audio frame, with harmonics folded down so a guitar's overtones don't vote
    for the wrong pitch class."""

    FRAME = 8192        # 186 ms at 44.1 kHz: enough to tell low-string semitones apart

    def __init__(self, rate=RATE, frame=FRAME, fmin=75.0, fmax=1500.0, tol_cents=40.0):
        self.rate, self.frame = rate, frame
        self.window = np.hanning(frame)
        freqs = np.fft.rfftfreq(frame, 1.0 / rate)
        self.bins = []
        for h, weight in ((1, 1.0), (2, 0.6), (3, 0.4), (4, 0.25)):   # fold harmonics 2-4 onto their fundamental
            sel = (freqs >= fmin * h) & (freqs <= fmax * h)
            midi = 69.0 + 12.0 * np.log2(freqs[sel] / h / 440.0)
            nearest = np.round(midi)
            cents = np.abs(midi - nearest) * 100.0
            keep = cents <= tol_cents                   # bins between two notes don't vote
            idx = np.flatnonzero(sel)[keep]
            pcs = nearest[keep].astype(int) % 12
            w = weight * (1.0 - cents[keep] / tol_cents)
            self.bins.append((idx, pcs, w))

    def chroma(self, x):
        x = np.asarray(x, dtype=np.float64)
        if len(x) < self.frame:
            x = np.concatenate((np.zeros(self.frame - len(x)), x))
        spec = np.abs(np.fft.rfft(x[-self.frame:] * self.window))
        chroma = np.zeros(12)
        for idx, pcs, w in self.bins:
            np.add.at(chroma, pcs, w * spec[idx] ** 2)
        chroma = np.sqrt(chroma)
        n = np.linalg.norm(chroma)
        return chroma / n if n > 1e-9 else chroma

    def match(self, x, name):
        """How much the frame sounds like chord ``name``: cosine similarity 0..1."""
        t = template(name)
        if t is None:
            return 0.0
        return float(np.dot(self.chroma(x), t))

    def best(self, x, names):
        c = self.chroma(x)
        scored = [(float(np.dot(c, template(n))), n) for n in names if template(n) is not None]
        return max(scored) if scored else (0.0, None)


def chord_name(pc, quality):
    return PITCH_CLASSES[pc] + quality


def midi_notes(name, shapes):
    """The voicing to display/synthesise for a chord, from the SHAPES table in curriculum."""
    return shapes.get(name, ())
