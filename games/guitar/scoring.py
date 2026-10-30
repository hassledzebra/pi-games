"""Judges the played pitch stream against the song's notes.

A note counts as HIT when the tracker reports the right pitch and that pitch was attacked
(pluck onset or pitch change) within ``early`` before to ``late`` after the note's start. The timing
offset is attack time minus note start, so the result screen can say "you rush" or "you drag".
"""
from .pitch import freq_to_midi  # noqa: F401  (re-exported for callers)

PENDING, HIT, MISS = 0, 1, 2


class Judge:
    def __init__(self, notes, early=0.12, late=0.25, cents_tol=60.0, min_window=0.30):
        self.notes = notes
        self.early, self.late = early, late
        self.tol = cents_tol / 100.0
        self.min_window = min_window
        self.state = [PENDING] * len(notes)
        self.offset = [None] * len(notes)
        self.next_idx = 0            # first note that can still be hit
        self.hits = self.misses = 0
        self.combo = self.best_combo = 0
        self.score = 0
        self.attack_time = -1.0
        self.last_midi = None
        self.last_event = None       # (time, index, HIT/MISS) for the UI flash

    def feed(self, frame):
        """frame: PitchFrame. Returns a list of (index, HIT/MISS) decided on this frame."""
        t = frame.time
        events = []
        midi = frame.midi
        if midi is not None:
            if frame.onset or self.last_midi is None or abs(midi - self.last_midi) > 0.5:
                self.attack_time = t
        elif frame.onset:
            self.attack_time = t
        self.last_midi = midi

        # expire notes whose window has passed
        while self.next_idx < len(self.notes):
            n = self.notes[self.next_idx]
            if self.state[self.next_idx] == PENDING and t > self._window_end(n):
                self._miss(self.next_idx, t, events)
            if self.state[self.next_idx] != PENDING:
                self.next_idx += 1
            else:
                break

        if midi is None:
            return events
        i = self.next_idx
        while i < len(self.notes) and self.notes[i].start - self.early <= t:
            n = self.notes[i]
            if (self.state[i] == PENDING and abs(midi - n.midi) <= self.tol
                    and n.start - self.early <= self.attack_time <= n.start + self.late):
                self._hit(i, self.attack_time - n.start, t, events)
                break
            i += 1
        return events

    def _window_end(self, n):
        # the pluck must land by start+late; the pitch estimate trails the pluck by ~0.1 s
        return max(n.end, n.start + self.min_window, n.start + self.late + 0.1)

    def _hit(self, i, offset, t, events):
        self.state[i], self.offset[i] = HIT, offset
        self.hits += 1
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.score += 100 + min(self.combo, 10) * 10
        self.last_event = (t, i, HIT)
        events.append((i, HIT))

    def _miss(self, i, t, events):
        self.state[i] = MISS
        self.misses += 1
        self.combo = 0
        self.last_event = (t, i, MISS)
        events.append((i, MISS))

    def finish(self, t):
        """Call at the end of the song so the remaining notes are judged."""
        events = []
        for i in range(self.next_idx, len(self.notes)):
            if self.state[i] == PENDING:
                self._miss(i, t, events)
        self.next_idx = len(self.notes)
        return events

    @property
    def done(self):
        return self.hits + self.misses

    @property
    def accuracy(self):
        return self.hits / len(self.notes) if self.notes else 0.0

    def timing_stats(self):
        offs = [o for o in self.offset if o is not None]
        if not offs:
            return 0.0, 0.0
        mean = sum(offs) / len(offs)
        spread = (sum((o - mean) ** 2 for o in offs) / len(offs)) ** 0.5
        return mean, spread

    def stars(self):
        a = self.accuracy
        return 5 if a >= 0.97 else 4 if a >= 0.9 else 3 if a >= 0.75 else 2 if a >= 0.5 else 1 if a >= 0.25 else 0


class ChordJudge:
    """Judges strummed chords. Each strum in the song is HIT when a pluck onset lands in its
    timing window and the chroma heard right after it matches the expected chord better than
    the other chords in the exercise."""

    def __init__(self, song, early=0.10, late=0.18, min_match=0.5, margin=-0.03):
        import numpy as np
        from .chords import template
        self.np = np
        self.strums = song.strums
        self.names = sorted({c.name for c in song.chords})
        self.templates = {n: template(n) for n in self.names}
        self.early, self.late, self.min_match, self.margin = early, late, min_match, margin
        self.state = [PENDING] * len(self.strums)
        self.offset = [None] * len(self.strums)
        self.next_idx = 0
        self.hits = self.misses = 0
        self.combo = self.best_combo = 0
        self.score = 0
        self.onset_time = None        # the pluck we are currently listening to
        self.onset_target = None      # strum index it was assigned to
        self.heard = (None, 0.0)      # best-matching chord name and its score, for the display
        self.last_event = None
        self.notes = self.strums      # so the result screen can treat both judges alike

    def feed(self, frame):
        t = frame.time
        events = []
        while self.next_idx < len(self.strums) and self.state[self.next_idx] != PENDING:
            self.next_idx += 1
        # expire strums whose window has passed
        i = self.next_idx
        while i < len(self.strums) and self.strums[i].time + self.late < t:
            if self.state[i] == PENDING:
                self._miss(i, t, events)
            i += 1
        while self.next_idx < len(self.strums) and self.state[self.next_idx] != PENDING:
            self.next_idx += 1
        if frame.onset:
            self.onset_time, self.onset_target = t, self._nearest_pending(t)
        if frame.chroma is not None and self.onset_target is not None and self.state[self.onset_target] == PENDING:
            scores = {n: float(self.np.dot(frame.chroma, tpl)) for n, tpl in self.templates.items()}
            want = self.strums[self.onset_target].chord
            best = max(scores, key=scores.get)
            self.heard = (best, scores[best])
            others = max((v for n, v in scores.items() if n != want), default=0.0)
            if scores[want] >= self.min_match and scores[want] - others >= self.margin:
                self._hit(self.onset_target, self.onset_time - self.strums[self.onset_target].time, t, events)
                self.onset_target = None
        return events

    def _nearest_pending(self, t):
        best = None
        for i in range(self.next_idx, len(self.strums)):
            st = self.strums[i]
            if st.time - self.early > t:
                break
            if self.state[i] == PENDING and st.time - self.early <= t <= st.time + self.late:
                if best is None or abs(st.time - t) < abs(self.strums[best].time - t):
                    best = i
        return best

    def _hit(self, i, offset, t, events):
        self.state[i], self.offset[i] = HIT, offset
        self.hits += 1
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.score += 100 + min(self.combo, 10) * 10
        self.last_event = (t, i, HIT)
        events.append((i, HIT))

    def _miss(self, i, t, events):
        self.state[i] = MISS
        self.misses += 1
        self.combo = 0
        self.last_event = (t, i, MISS)
        events.append((i, MISS))

    def finish(self, t):
        events = []
        for i in range(len(self.strums)):
            if self.state[i] == PENDING:
                self._miss(i, t, events)
        self.next_idx = len(self.strums)
        return events

    @property
    def done(self):
        return self.hits + self.misses

    @property
    def accuracy(self):
        return self.hits / len(self.strums) if self.strums else 0.0

    def timing_stats(self):
        offs = [o for o in self.offset if o is not None]
        if not offs:
            return 0.0, 0.0
        mean = sum(offs) / len(offs)
        return mean, (sum((o - mean) ** 2 for o in offs) / len(offs)) ** 0.5

    stars = Judge.stars
