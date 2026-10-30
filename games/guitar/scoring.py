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
