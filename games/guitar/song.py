"""Songs: what the player is supposed to play.

A song is a list of notes (MIDI pitch, start and end in seconds) plus a backing track. Songs are
loaded from standard MIDI files; a song *package* is a folder with ``song.json`` next to the MIDI
and an optional pre-rendered ``backing.wav``. If the MIDI carries no tab information the string
and fret are chosen automatically (``assign_fingering``), so any MIDI melody shows up as a tab.
"""
import json
import os
import re

import mido

STANDARD_TUNING = (40, 45, 50, 55, 59, 64)   # E2 A2 D3 G3 B3 E4, string 0 = low E
MAX_FRET = 17


class Note:
    __slots__ = ("midi", "start", "end", "string", "fret", "velocity")

    def __init__(self, midi, start, end, string=None, fret=None, velocity=96):
        self.midi, self.start, self.end = int(midi), float(start), float(end)
        self.string, self.fret, self.velocity = string, fret, velocity

    @property
    def duration(self):
        return self.end - self.start

    def __repr__(self):
        return "Note(%d, %.3f-%.3f, s%s f%s)" % (self.midi, self.start, self.end, self.string, self.fret)


class Song:
    def __init__(self, title, notes, bpm=120.0, artist="", path=None, backing=None, midi_path=None,
                 guitar_track=0, beats_per_bar=4, offset=0.0):
        self.title, self.artist, self.bpm = title, artist, bpm
        self.notes = sorted(notes, key=lambda n: (n.start, n.midi))
        self.path, self.backing, self.midi_path = path, backing, midi_path
        self.guitar_track, self.beats_per_bar, self.offset = guitar_track, beats_per_bar, offset

    @property
    def duration(self):
        return max((n.end for n in self.notes), default=0.0)

    @property
    def beat(self):
        return 60.0 / self.bpm

    def __repr__(self):
        return "Song(%r, %d notes, %.0f bpm)" % (self.title, len(self.notes), self.bpm)


# ---------------------------------------------------------------- MIDI reading

def _tempo_map(mid):
    """Sorted (abs_tick, tempo_us_per_beat) from every track."""
    events = []
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                events.append((tick, msg.tempo))
    events.sort()
    if not events or events[0][0] > 0:
        events.insert(0, (0, 500000))
    return events


def _tick_to_seconds(tempos, tpb):
    """Returns f(tick) -> seconds, honouring tempo changes."""
    starts = [0.0]
    for i in range(1, len(tempos)):
        dt = tempos[i][0] - tempos[i - 1][0]
        starts.append(starts[-1] + dt * tempos[i - 1][1] / 1e6 / tpb)

    def f(tick):
        i = 0
        for j in range(len(tempos)):
            if tempos[j][0] <= tick:
                i = j
            else:
                break
        return starts[i] + (tick - tempos[i][0]) * tempos[i][1] / 1e6 / tpb
    return f


def track_notes(mid, index):
    """Notes of one track as (midi, start_tick, end_tick, velocity, channel)."""
    track = mid.tracks[index]
    tick, open_notes, out = 0, {}, []
    for msg in track:
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_notes.setdefault((msg.channel, msg.note), []).append((tick, msg.velocity))
        elif msg.type in ("note_off", "note_on"):
            key = (msg.channel, msg.note)
            if open_notes.get(key):
                start, vel = open_notes[key].pop(0)
                out.append((msg.note, start, max(tick, start + 1), vel, msg.channel))
    return out


def channels_are_strings(raw, tuning=STANDARD_TUNING):
    """Guitar MIDI often puts each string on its own channel (0 = low E). Use that as the
    fingering when every note is playable on its channel's string."""
    chans = {ch for _, _, _, _, ch in raw}
    if not raw or not chans <= set(range(len(tuning))):
        return False
    return all(0 <= midi - tuning[ch] <= MAX_FRET for midi, _, _, _, ch in raw)


def is_drum_track(mid, index):
    return any(getattr(m, "channel", None) == 9 for m in mid.tracks[index] if m.type == "note_on")


def guess_guitar_track(mid):
    """The track to play: a track named guitar/lead/melody, else the first with notes (no drums)."""
    candidates = [i for i in range(len(mid.tracks)) if track_notes(mid, i) and not is_drum_track(mid, i)]
    if not candidates:
        return None
    for i in candidates:
        name = " ".join(m.name for m in mid.tracks[i] if m.type in ("track_name", "instrument_name")).lower()
        if re.search(r"guitar|lead|melody|solo|gtr", name):
            return i
    return candidates[0]


def load_midi(path, track=None, title=None):
    mid = mido.MidiFile(path)
    if track is None:
        track = guess_guitar_track(mid)
    if track is None:
        raise ValueError("%s has no note tracks" % path)
    tempos = _tempo_map(mid)
    secs = _tick_to_seconds(tempos, mid.ticks_per_beat)
    raw = track_notes(mid, track)
    by_channel = channels_are_strings(raw)
    notes = []
    for midi, s, e, vel, ch in raw:
        note = Note(midi, secs(s), secs(e), velocity=vel)
        if by_channel:
            note.string, note.fret = ch, midi - STANDARD_TUNING[ch]
        notes.append(note)
    notes = monophonic(notes)
    assign_fingering(notes)
    beats = 4
    for t in mid.tracks:
        for m in t:
            if m.type == "time_signature":
                beats = m.numerator
                break
    name = title or os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    return Song(name, notes, bpm=60e6 / tempos[0][1], path=path, midi_path=path, guitar_track=track,
                beats_per_bar=beats)


def monophonic(notes):
    """Keep one note at a time (the highest of any chord) and trim overlaps. Chord scoring is
    for a later version; this keeps the pitch tracker's job well defined."""
    notes = sorted(notes, key=lambda n: (n.start, -n.midi))
    out = []
    for n in notes:
        if out and n.start - out[-1].start < 0.03:
            continue                                  # same chord: keep the top note
        if out and out[-1].end > n.start:
            out[-1].end = n.start
        out.append(n)
    return out


def assign_fingering(notes, tuning=STANDARD_TUNING, max_fret=MAX_FRET):
    """Choose string/fret for notes that have none: stay close to the previous hand position and
    prefer lower frets. Simple, but it gives readable tabs for melodies."""
    pos = 0
    for n in notes:
        if n.string is not None:
            pos = n.fret
            continue
        best = None
        for s, open_midi in enumerate(tuning):
            fret = n.midi - open_midi
            if 0 <= fret <= max_fret:
                cost = abs(fret - pos) + 0.3 * fret + (0 if fret else -1.5)
                if best is None or cost < best[0]:
                    best = (cost, s, fret)
        if best is None:          # outside the guitar's range: show it on the nearest string
            s = 0 if n.midi < tuning[0] else len(tuning) - 1
            best = (0, s, max(0, min(max_fret, n.midi - tuning[s])))
        n.string, n.fret = best[1], best[2]
        if n.fret:
            pos = n.fret
    return notes


# ---------------------------------------------------------------- packages

def load_song(path):
    """``path`` is a .mid file or a folder containing song.json."""
    if os.path.isdir(path):
        meta_path = os.path.join(path, "song.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        midi = os.path.join(path, meta.get("midi", "notes.mid"))
        song = load_midi(midi, meta.get("track"), meta.get("title"))
        song.artist = meta.get("artist", "")
        song.path = path
        song.offset = float(meta.get("offset", 0.0))
        if meta.get("bpm"):
            song.bpm = float(meta["bpm"])
        backing = os.path.join(path, meta.get("backing", "backing.wav"))
        song.backing = backing if os.path.exists(backing) else None
        return song
    song = load_midi(path)
    wav = os.path.splitext(path)[0] + ".wav"
    song.backing = wav if os.path.exists(wav) else None
    return song


def find_songs(folder):
    """All songs in a folder: packages (sub-folders with song.json) and bare .mid files."""
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "song.json")):
            out.append(p)
        elif name.lower().endswith((".mid", ".midi")):
            out.append(p)
    return out
