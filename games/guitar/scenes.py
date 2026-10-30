"""Screens: song list with a live tuner, the note highway, and the result sheet."""
import math
import os
import queue
import threading
import time

import pygame

from engine import text
from engine.app import Scene

from . import backing
from .curriculum import EXERCISES, STAGES, PATH_DIR
from .progress import STARS_TO_UNLOCK, Progress
from .pitch import PitchFrame, PitchTracker, midi_to_freq, note_name
from .scoring import HIT, MISS, PENDING, Judge
from .song import find_songs, load_song

WIDTH, HEIGHT = 640, 360
NOW_X = 120                    # x of the "play it now" line
PPS = 150.0                    # pixels per second of song time
LANE_TOP, LANE_GAP = 70, 34    # string lanes: high E at the top like a tab
STRING_COLORS = [(235, 80, 80), (240, 150, 60), (235, 220, 70), (90, 210, 110), (80, 160, 240), (190, 110, 240)]
STRING_NAMES = ["E", "A", "D", "G", "B", "e"]
BG = (18, 20, 28)
PANEL = (30, 34, 46)
WHITE, GREY, DIM = (240, 240, 240), (150, 155, 170), (70, 75, 90)
GREEN, RED, GOLD = (90, 230, 120), (240, 80, 80), (255, 210, 60)


def lane_y(string):
    return LANE_TOP + (5 - string) * LANE_GAP


class Ear:
    """The microphone/interface plus the pitch tracker, shared by every scene.

    Analysis runs on its own thread (numpy's FFT releases the GIL), so a 60 fps frame never waits
    for a pitch estimate and a slow frame never delays the audio queue.
    """

    def __init__(self, device=None, enabled=True, log=print):
        self.tracker = PitchTracker()
        self.input = None
        self.error = None
        self.frames = queue.Queue()
        self.thread = None
        self._stop = False
        if not enabled:
            return
        try:
            from .pitch import AudioInput
            if device is None:
                device = AudioInput.pick_device()
            self.input = AudioInput(device)
            log("Listening on: %s" % self.input.name)
        except Exception as e:  # no PortAudio, no device, device busy...
            self.error = str(e).strip().splitlines()[-1] if str(e).strip() else type(e).__name__
            log("No audio input (%s) - demo mode" % self.error)
            return
        self.thread = threading.Thread(target=self._work, name="pitch", daemon=True)
        self.thread.start()

    @property
    def live(self):
        return self.input is not None

    def _work(self):
        q = self.input.q
        while not self._stop:
            try:
                samples, t_end = q.get(timeout=0.2)
            except queue.Empty:
                continue
            for fr in self.tracker.feed(samples, t_end):
                self.frames.put(fr)

    def poll(self):
        """PitchFrames analysed since the last call (oldest first)."""
        out = []
        while True:
            try:
                out.append(self.frames.get_nowait())
            except queue.Empty:
                return out

    def close(self):
        self._stop = True
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.input is not None:
            self.input.close()
            self.input = None


def draw_tuner(surface, tracker, y, live):
    """Detected note, cents bar and input level."""
    pygame.draw.rect(surface, PANEL, (0, y, WIDTH, HEIGHT - y))
    if not live:
        text.draw(surface, "NO AUDIO INPUT - plug in the USB interface, or watch the demo", 16, GREY, (WIDTH // 2, y + 22))
        return
    midi = tracker.current
    cx = WIDTH // 2
    pygame.draw.rect(surface, DIM, (cx - 150, y + 30, 300, 6))
    pygame.draw.rect(surface, GREY, (cx - 1, y + 26, 2, 14))
    if midi is None:
        text.draw(surface, "--", 28, GREY, (cx, y + 12))
    else:
        cents = (midi - round(midi)) * 100.0
        text.draw(surface, "%s  %.1f Hz" % (note_name(midi), midi_to_freq(midi)), 28, WHITE, (cx, y + 12))
        col = GREEN if abs(cents) < 10 else GOLD if abs(cents) < 25 else RED
        px = cx + int(cents * 3)
        pygame.draw.rect(surface, col, (px - 3, y + 26, 6, 14))
        text.draw(surface, "%+d cents" % round(cents), 14, col, (cx + 220, y + 30))
    db = tracker.levels[-1] if tracker.levels else -90.0
    lvl = max(0.0, min(1.0, (db + 60.0) / 60.0))
    pygame.draw.rect(surface, DIM, (20, y + 30, 100, 6))
    pygame.draw.rect(surface, GREEN if db < -6 else RED, (20, y + 30, int(100 * lvl), 6))
    text.draw(surface, "input", 14, GREY, (20, y + 12), align="left")


SPEEDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def draw_stars(surface, x, y, stars, size=5, total=5):
    for k in range(total):
        pygame.draw.circle(surface, GOLD if k < stars else DIM, (x + k * (size * 2 + 3), y), size)


class TitleScene(Scene):
    """The learning path: stages on the left, the chosen stage's exercises on the right."""

    def __init__(self, app, stage=None, index=None):
        super().__init__(app)
        self.songs_dir = app.settings["songs_dir"]
        self.progress = app.settings["progress"]
        self.ear = app.settings["ear"]
        self.paths = app.settings["paths"]                 # ex.id -> midi path
        self.user_songs = [p for p in find_songs(self.songs_dir)]
        extra = app.settings.get("song")
        if extra and extra not in self.user_songs:
            self.user_songs.insert(0, extra)
        self.n_stages = len(STAGES) + (1 if self.user_songs else 0)
        if stage is None:
            stage, index = self.progress.first_open()
            if extra:
                stage, index = len(STAGES), 0
            start = app.settings.pop("start", None)
            for k, st in enumerate(STAGES):
                for i, ex in enumerate(st.exercises):
                    if start and ex.id == start:
                        stage, index = k, i
        self.stage, self.index = stage, index
        self.speed_i = SPEEDS.index(app.settings.get("speed", 1.0))

    # ------------------------------------------------------------ data
    def items(self, k):
        """(label, path, ex or None) rows of stage k."""
        if k < len(STAGES):
            return [(ex.title, self.paths[ex.id], ex) for ex in STAGES[k].exercises]
        return [(os.path.splitext(os.path.basename(p))[0], p, None) for p in self.user_songs]

    def unlocked(self, k):
        return k >= len(STAGES) or self.progress.unlocked(k)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        rows = self.items(self.stage)
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            self.app.quit()
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % max(1, len(rows))
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.index = (self.index + 1) % max(1, len(rows))
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.stage, self.index = (self.stage - 1) % self.n_stages, 0
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.stage, self.index = (self.stage + 1) % self.n_stages, 0
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_LEFTBRACKET):
            self.speed_i = max(0, self.speed_i - 1)
            self.app.settings["speed"] = SPEEDS[self.speed_i]
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_RIGHTBRACKET):
            self.speed_i = min(len(SPEEDS) - 1, self.speed_i + 1)
            self.app.settings["speed"] = SPEEDS[self.speed_i]
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and rows and self.unlocked(self.stage):
            label, path, ex = rows[self.index]
            self.app.switch(PlayScene(self.app, path, ex, (self.stage, self.index)))
        elif event.key == pygame.K_m:
            self.app.settings["metronome"] = not self.app.settings.get("metronome", True)

    def update(self):
        self.ear.poll()

    def draw(self, surface):
        surface.fill(BG)
        text.draw(surface, "PI STRUM", 40, GOLD, (110, 8), align="left")
        text.draw(surface, "learning path", 16, GREY, (112, 40), align="left")
        # stages column
        for k in range(self.n_stages):
            y = 64 + k * 30
            title = STAGES[k].title if k < len(STAGES) else "Your songs"
            open_ = self.unlocked(k)
            sel = k == self.stage
            if sel:
                pygame.draw.rect(surface, DIM, (8, y - 3, 200, 28), border_radius=4)
            col = WHITE if (sel and open_) else GREY if open_ else (90, 90, 100)
            text.draw(surface, "%d  %s" % (k + 1, title) if k < len(STAGES) else title, 18, col, (16, y), align="left")
            if k < len(STAGES):
                done = sum(1 for ex in STAGES[k].exercises if self.progress.stars(ex.id) >= STARS_TO_UNLOCK)
                text.draw(surface, "%d/%d" % (done, len(STAGES[k].exercises)) if open_ else "locked", 14,
                          GREEN if done == len(STAGES[k].exercises) else GREY, (200, y + 4), align="right")
        # exercises panel
        px, py = 224, 60
        pygame.draw.rect(surface, PANEL, (px, py, WIDTH - px - 10, 220), border_radius=6)
        rows = self.items(self.stage)
        if self.stage < len(STAGES):
            text.draw(surface, STAGES[self.stage].blurb, 14, GREY, (px + 10, py + 6), align="left")
        else:
            text.draw(surface, "MIDI files you dropped into songs/", 14, GREY, (px + 10, py + 6), align="left")
        if not self.unlocked(self.stage):
            text.draw(surface, "LOCKED", 28, RED, (px + 200, py + 80))
            text.draw(surface, "get %d stars on every exercise of stage %d" % (STARS_TO_UNLOCK, self.stage), 16, GREY, (px + 200, py + 110))
        else:
            for i, (label, path, ex) in enumerate(rows[:9]):
                y = py + 28 + i * 20
                if i == self.index:
                    pygame.draw.rect(surface, DIM, (px + 4, y - 2, WIDTH - px - 18, 20), border_radius=3)
                text.draw(surface, label, 18, WHITE if i == self.index else GREY, (px + 12, y), align="left")
                if ex:
                    text.draw(surface, "%d bpm" % ex.bpm, 14, DIM if i != self.index else GREY, (px + 250, y + 3), align="left")
                    draw_stars(surface, px + 320, y + 8, self.progress.stars(ex.id))
                    if self.progress.stars(ex.id, full=False) > self.progress.stars(ex.id):
                        text.draw(surface, "slow", 12, GOLD, (px + 385, y + 3), align="left")
            if rows and rows[self.index][2] is not None:
                tip = rows[self.index][2].tip
                text.draw(surface, tip, 14, GOLD, (px + 10, py + 206), align="left")
        # bottom controls
        text.draw(surface, "Left/Right stage   Up/Down exercise   Enter play   -/+ speed %d%%   M metronome %s   Esc quit" %
                  (round(SPEEDS[self.speed_i] * 100), "on" if self.app.settings.get("metronome", True) else "off"), 14, GREY, (WIDTH // 2 + 90, 285))
        if self.ear.live:
            text.draw(surface, "input: " + self.ear.input.name[:24], 14, GREEN, (16, 285), align="left")
        draw_tuner(surface, self.ear.tracker, 300, self.ear.live)


class PlayScene(Scene):
    COUNT_IN_BARS = 1

    def __init__(self, app, path, ex=None, origin=None):
        super().__init__(app)
        self.ear = app.settings["ear"]
        self.ex, self.origin = ex, origin
        self.demo = app.settings.get("demo", False) or not self.ear.live
        self.latency = app.settings.get("latency", 0.04)
        self.speed = app.settings.get("speed", 1.0)
        self.song = load_song(path)
        if self.speed < 0.999:
            for n in self.song.notes:
                n.start, n.end = n.start / self.speed, n.end / self.speed
            self.song.bpm *= self.speed
        if ex is not None:
            self.song.title = ex.title
        self.notes = self.song.notes
        self.judge = Judge(self.notes)
        self.count_in = self.song.beat * self.song.beats_per_bar * self.COUNT_IN_BARS
        self.metronome = app.settings.get("metronome", True)
        self.backing = None
        self.backing_channel = None
        self.mixer = bool(pygame.mixer.get_init())
        if self.mixer:
            try:
                wav = backing.ensure_backing(self.song, rate=pygame.mixer.get_init()[0], speed=self.speed)
                if wav:
                    self.backing = pygame.mixer.Sound(file=wav)
            except Exception as e:
                print("backing track failed: %s" % e)
            rate, _, channels = pygame.mixer.get_init()
            self.click = pygame.mixer.Sound(buffer=backing.click(rate, channels=channels))
            self.click_accent = pygame.mixer.Sound(buffer=backing.click(rate, accent=True, channels=channels))
        self.t0 = time.monotonic()
        self.song_time = -self.count_in
        self.paused = False
        self.pause_at = 0.0
        self.last_beat = -10 ** 9
        self.backing_started = False
        self.flash = None
        self.end_time = self.song.duration + 1.5
        self.demo_next = 0           # demo mode: index of the next note to "play"
        self.demo_last = None

    # ------------------------------------------------------------ control
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self._stop_audio()
            self.app.switch(TitleScene(self.app, *self.origin) if self.origin else TitleScene(self.app))
        elif event.key == pygame.K_SPACE:
            self._toggle_pause()
        elif event.key == pygame.K_r:
            self._stop_audio()
            self.app.switch(PlayScene(self.app, self.song.path, self.ex, self.origin))
        elif event.key == pygame.K_m:
            self.metronome = not self.metronome
            self.app.settings["metronome"] = self.metronome

    def _toggle_pause(self):
        if self.paused:
            self.t0 += time.monotonic() - self.pause_at
            self.paused = False
            if self.backing_channel is not None:
                self.backing_channel.unpause()
        else:
            self.paused = True
            self.pause_at = time.monotonic()
            if self.backing_channel is not None:
                self.backing_channel.pause()

    def _stop_audio(self):
        if self.backing_channel is not None:
            self.backing_channel.stop()

    # ------------------------------------------------------------ update
    def update(self):
        if self.paused:
            self.ear.poll()
            return
        now = time.monotonic()
        self.song_time = now - self.t0 - self.count_in
        if not self.backing_started and self.song_time >= 0.0 and self.backing is not None and self.mixer:
            self.backing_channel = self.backing.play()
            self.backing_started = True
        self._tick_metronome()

        if self.demo:
            frames = self._demo_frames()
        else:
            frames = self.ear.poll()
            for fr in frames:
                fr.time = fr.time - self.t0 - self.count_in - self.latency
        for fr in frames:
            for i, verdict in self.judge.feed(fr):
                self.flash = (self.song_time, i, verdict)
                self.app.play("hit" if verdict == HIT else "miss")
        if self.song_time > self.end_time:
            self.judge.finish(self.song_time)
            self._stop_audio()
            self.app.switch(ResultScene(self.app, self))

    def _tick_metronome(self):
        beat_no = math.floor(self.song_time / self.song.beat + 1e-6)
        if beat_no != self.last_beat:
            self.last_beat = beat_no
            in_count_in = self.song_time < 0
            if self.mixer and (self.metronome or in_count_in) and self.song_time < self.song.duration:
                (self.click_accent if beat_no % self.song.beats_per_bar == 0 else self.click).play()

    def _demo_frames(self):
        """Pretend a flawless player: synthesise pitch frames from the song itself."""
        t = self.song_time
        notes = self.notes
        midi = None
        while self.demo_next < len(notes) and notes[self.demo_next].end < t - 0.05:
            self.demo_next += 1
        onset = False
        if self.demo_next < len(notes):
            n = notes[self.demo_next]
            if n.start + 0.01 <= t <= n.end:
                midi = n.midi
                if self.demo_last != self.demo_next:
                    onset = True
                    self.demo_last = self.demo_next
        freq = midi_to_freq(midi) if midi is not None else 0.0
        fr = PitchFrame(t, freq, 0.95 if midi else 0.0, -20.0 if midi else -80.0, onset)
        self.ear.tracker.history.append(fr.midi)
        if len(self.ear.tracker.history) > 3:
            self.ear.tracker.history.pop(0)
        self.ear.tracker.current = float(midi) if midi is not None else None
        self.ear.tracker.levels = [fr.db]
        return [fr]

    # ------------------------------------------------------------ draw
    def draw(self, surface):
        surface.fill(BG)
        t = self.song_time
        self._draw_header(surface)
        # lanes
        for s in range(6):
            y = lane_y(s)
            pygame.draw.line(surface, DIM, (0, y), (WIDTH, y), 1 + (s < 3))
            text.draw(surface, STRING_NAMES[s], 16, STRING_COLORS[s], (12, y - 8))
        # beat grid
        beat = self.song.beat
        first = math.floor((t - NOW_X / PPS) / beat)
        for b in range(first, first + int(WIDTH / PPS / beat) + 2):
            x = NOW_X + int((b * beat - t) * PPS)
            if 24 <= x < WIDTH:
                bar = b % self.song.beats_per_bar == 0
                pygame.draw.line(surface, (50, 55, 70) if bar else (34, 38, 50), (x, LANE_TOP - 20), (x, lane_y(0) + 16))
        # notes
        for i, n in enumerate(self.notes):
            x0 = NOW_X + (n.start - t) * PPS
            x1 = NOW_X + (n.end - t) * PPS
            if x1 < 24 or x0 > WIDTH:
                continue
            y = lane_y(n.string)
            st = self.judge.state[i]
            col = GREEN if st == HIT else RED if st == MISS else STRING_COLORS[n.string]
            if st == PENDING and t > n.start + 0.02:
                col = tuple(min(255, c + 60) for c in col)
            w = max(16, int(x1 - x0) - 2)
            pygame.draw.rect(surface, tuple(c // 2 for c in col), (int(x0), y - 6, w, 12), border_radius=4)
            pygame.draw.circle(surface, col, (int(x0), y), 11)
            text.draw(surface, str(n.fret), 18, (20, 20, 20), (int(x0), y - 7), shadow=None)
        # now line
        pygame.draw.line(surface, WHITE, (NOW_X, LANE_TOP - 24), (NOW_X, lane_y(0) + 20), 2)
        # hit/miss flash
        if self.flash and t - self.flash[0] < 0.35:
            _, i, verdict = self.flash
            n = self.notes[i]
            text.draw(surface, "HIT" if verdict == HIT else "MISS", 20, GREEN if verdict == HIT else RED,
                      (NOW_X + 30, lane_y(n.string) - 26))
        # count-in / pause
        if t < 0:
            text.draw(surface, str(int(-t / beat) + 1), 64, GOLD, (WIDTH // 2, HEIGHT // 2 - 40))
        if self.paused:
            text.draw(surface, "PAUSED - Space to resume", 28, GOLD, (WIDTH // 2, HEIGHT // 2 - 20))
        draw_tuner(surface, self.ear.tracker, 300, self.ear.live or self.demo)
        if self.demo:
            text.draw(surface, "DEMO", 16, GOLD, (WIDTH - 10, 306), align="right")

    def _draw_header(self, surface):
        pygame.draw.rect(surface, PANEL, (0, 0, WIDTH, 40))
        text.draw(surface, self.song.title, 22, WHITE, (10, 6), align="left")
        text.draw(surface, "%d bpm%s" % (round(self.song.bpm), "" if self.speed >= 0.999 else "  (%d%% speed)" % round(self.speed * 100)), 14, GREY, (10, 26), align="left")
        j = self.judge
        text.draw(surface, "%d" % j.score, 28, GOLD, (WIDTH - 10, 4), align="right")
        text.draw(surface, "combo %d   %d/%d" % (j.combo, j.hits, j.done), 14, GREY, (WIDTH - 10, 26), align="right")
        acc = j.hits / j.done if j.done else 1.0
        text.draw(surface, "%d%%" % round(acc * 100), 22, GREEN if acc >= 0.8 else GOLD if acc >= 0.5 else RED, (WIDTH // 2, 8))
        prog = max(0.0, min(1.0, self.song_time / max(0.01, self.song.duration)))
        pygame.draw.rect(surface, DIM, (0, 40, WIDTH, 3))
        pygame.draw.rect(surface, GOLD, (0, 40, int(WIDTH * prog), 3))
        text.draw(surface, "Space pause   R restart   M metronome %s   Esc back" % ("on" if self.metronome else "off"),
                  14, DIM, (WIDTH // 2, 46))


class ResultScene(Scene):
    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        self.song, self.judge, self.demo = play.song, play.judge, play.demo
        self.ear = app.settings["ear"]
        self.unlocked_msg = None
        if play.ex is not None and not self.demo:
            prog = app.settings["progress"]
            k = next(i for i, st in enumerate(STAGES) if play.ex in st.exercises)
            before = prog.unlocked(k + 1) if k + 1 < len(STAGES) else True
            prog.record(play.ex.id, self.judge.stars(), self.judge.accuracy, self.judge.score, play.speed)
            if k + 1 < len(STAGES) and not before and prog.unlocked(k + 1):
                self.unlocked_msg = "Stage %d unlocked: %s" % (k + 2, STAGES[k + 1].title)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
            o = self.play.origin
            self.app.switch(TitleScene(self.app, *o) if o else TitleScene(self.app))
        elif event.key == pygame.K_r:
            self.app.switch(PlayScene(self.app, self.song.path, self.play.ex, self.play.origin))

    def update(self):
        self.ear.poll()

    def draw(self, surface):
        surface.fill(BG)
        j = self.judge
        text.draw(surface, self.song.title, 30, WHITE, (WIDTH // 2, 30))
        for k in range(5):
            pygame.draw.circle(surface, GOLD if k < j.stars() else DIM, (WIDTH // 2 - 100 + k * 50, 90), 18)
        text.draw(surface, "%d%%  accuracy" % round(j.accuracy * 100), 36, GOLD, (WIDTH // 2, 125))
        lines = ["score %d" % j.score, "hit %d   missed %d   of %d notes" % (j.hits, j.misses, len(j.notes)),
                 "best combo %d" % j.best_combo]
        mean, spread = j.timing_stats()
        if j.hits:
            feel = "rushing" if mean < -0.03 else "dragging" if mean > 0.05 else "on the beat"
            lines.append("timing: %s (avg %+d ms, spread %d ms)" % (feel, round(mean * 1000), round(spread * 1000)))
        if self.play.speed < 0.999:
            lines.append("played at %d%% speed - stars count for unlocking at 100%%" % round(self.play.speed * 100))
        if self.demo:
            lines.append("(demo run - no guitar input, nothing saved)")
        if self.unlocked_msg:
            lines.append(self.unlocked_msg)
        for k, line in enumerate(lines):
            text.draw(surface, line, 20, GOLD if line == self.unlocked_msg else GREY, (WIDTH // 2, 170 + k * 24))
        text.draw(surface, "Enter  back to the path      R  play again", 18, WHITE, (WIDTH // 2, 330))
