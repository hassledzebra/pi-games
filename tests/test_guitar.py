"""Headless checks for Pi Strum: pitch detection on synthetic guitar tones, MIDI loading,
fingering, judging a perfect and a silent performance, backing-track rendering, screenshots
and a per-frame timing estimate.

    python tests/test_guitar.py          (screenshots go to tests/out/)
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from engine.app import App  # noqa: E402
from engine.sfx import Sfx  # noqa: E402
from games.guitar import backing, curriculum, scenes  # noqa: E402
from games.guitar.progress import Progress  # noqa: E402
from games.guitar.pitch import FRAME, HOP, RATE, PitchFrame, PitchTracker, freq_to_midi, midi_to_freq, yin  # noqa: E402
from games.guitar.scoring import HIT, MISS, Judge  # noqa: E402
from games.guitar.song import STANDARD_TUNING, assign_fingering, load_song  # noqa: E402

OUT = os.path.join(ROOT, "tests", "out")


def guitar_tone(freq, seconds, rate=RATE, attack=0.005):
    """A plucked-string-ish tone: strong harmonics, fast attack, slow decay."""
    t = np.arange(int(rate * seconds)) / rate
    x = np.zeros_like(t)
    for k, a in enumerate((1.0, 0.7, 0.45, 0.3, 0.2, 0.1), start=1):
        x += a * np.sin(2 * np.pi * freq * k * t + k)
    env = np.minimum(1.0, t / attack) * np.exp(-t * 1.2)
    return x * env * 0.3


def test_yin():
    worst = 0.0
    for midi in range(40, 77):                       # E2 .. E5
        f = midi_to_freq(midi)
        x = guitar_tone(f, FRAME / RATE + 0.01)[:FRAME]
        est, conf = yin(x)
        assert est > 0, "no pitch for midi %d" % midi
        cents = abs(freq_to_midi(est) - midi) * 100
        worst = max(worst, cents)
        assert cents < 10, "midi %d: %.1f cents off (got %.1f Hz)" % (midi, cents, est)
        assert conf > 0.8, "midi %d: low confidence %.2f" % (midi, conf)
    noise = np.random.default_rng(1).normal(0, 0.1, FRAME)
    est, conf = yin(noise)
    assert est == 0.0 or conf < 0.7, "noise should not look like a note (conf %.2f)" % conf
    print("yin ok, worst error %.1f cents" % worst)


def test_tracker():
    tr = PitchTracker()
    rate = RATE
    silence = np.zeros(int(rate * 0.2))
    tone = guitar_tone(midi_to_freq(45), 0.6)          # A2
    tone2 = guitar_tone(midi_to_freq(45), 0.6)         # same note plucked again at 0.8 s
    audio = np.concatenate((silence, tone, tone2, silence))
    frames, t = [], 0.0
    for i in range(0, len(audio) - HOP, HOP):
        t += HOP / rate
        frames.extend(tr.feed(audio[i:i + HOP], t))
    onsets = [f.time for f in frames if f.onset]
    assert len(onsets) == 2, "expected 2 plucks, got %d at %s" % (len(onsets), onsets)
    assert abs(onsets[0] - 0.2) < 0.06 and abs(onsets[1] - 0.8) < 0.06, onsets
    mids = [f.midi for f in frames if f.midi is not None and 0.25 < f.time < 0.75]
    assert mids and all(abs(m - 45) < 0.15 for m in mids), "pitch drifted: %s" % mids[:5]
    print("tracker ok, %d frames, onsets at %.3f and %.3f" % (len(frames), onsets[0], onsets[1]))


def test_songs(folder):
    paths = curriculum.write_all(folder)
    assert len(paths) == sum(len(st.exercises) for st in curriculum.STAGES) == 21
    songs = {}
    for ex_id, p in paths.items():
        s = load_song(p)
        ex = curriculum.EXERCISES[ex_id]
        assert s.notes, s
        for n in s.notes:
            assert STANDARD_TUNING[n.string] + n.fret == n.midi, n
            assert 0 <= n.fret <= 17, (ex_id, n)
            assert n.end > n.start
        assert abs(s.bpm - ex.bpm) < 0.01 and s.beats_per_bar == ex.beats_per_bar, (ex_id, s.bpm, s.beats_per_bar)
        assert s.guitar_track == 1, (ex_id, s.guitar_track)
        songs[ex_id] = s
    ode = songs["3-3"]
    assert len(ode.notes) == 30, len(ode.notes)
    assert abs(ode.notes[0].start) < 1e-6 and abs(ode.notes[1].start - 0.6) < 1e-3
    assert ode.notes[0].midi == 64 and ode.notes[0].string == 5 and ode.notes[0].fret == 0
    assert all(n.string >= 4 for n in ode.notes), "Ode to Joy should sit on the B and e strings"
    # explicit fingering via channels: the A minor pentatonic box stays at the 5th fret
    box = songs["4-4"]
    assert all(5 <= n.fret <= 8 for n in box.notes), [(n.string, n.fret) for n in box.notes]
    assert box.notes[0].string == 0 and box.notes[0].fret == 5
    # riffs carry drums, which the loader must not pick as the guitar part
    assert songs["5-1"].notes[0].midi == 40 and songs["5-1"].notes[0].string == 0
    assert songs["3-5"].notes[0].start > 1.0, "Happy Birthday starts after a two-beat rest"
    hardest = max(songs.values(), key=lambda s: max(n.fret for n in s.notes))
    print("songs ok: %d exercises, highest fret %d in %s" % (len(songs), max(n.fret for n in hardest.notes), hardest.title))
    return songs


def test_progress(folder):
    pr = Progress(folder)
    assert pr.unlocked(0) and not pr.unlocked(1)
    assert pr.first_open() == (0, 0)
    for ex in curriculum.STAGES[0].exercises:
        pr.record(ex.id, 3, 0.8, 1000, 0.7)                 # slow runs don't unlock
    assert not pr.unlocked(1) and pr.stars("1-1") == 0 and pr.stars("1-1", full=False) == 3
    for ex in curriculum.STAGES[0].exercises:
        pr.record(ex.id, 2, 0.75, 900, 1.0)
    assert pr.unlocked(1) and not pr.unlocked(2)
    assert pr.first_open() == (1, 0)
    pr.record("1-1", 1, 0.3, 100, 1.0)                      # a worse run never lowers the best
    assert pr.stars("1-1") == 2
    again = Progress(folder)
    assert again.unlocked(1) and again.stars("1-2") == 2, "progress must persist"
    assert Progress(folder, unlock_all=True).unlocked(5)
    assert Progress(folder).unlocked(5), "unlock-all must be remembered"
    assert not Progress(folder, unlock_all=False).unlocked(5) and not Progress(folder).unlocked(5)
    Progress(folder, unlock_all=True)
    print("progress ok")


def test_fingering():
    from games.guitar.song import Note
    notes = [Note(m, i * 0.5, i * 0.5 + 0.5) for i, m in enumerate((40, 45, 50, 55, 59, 64, 65, 67))]
    assign_fingering(notes)
    assert [(n.string, n.fret) for n in notes[:6]] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]
    assert notes[6].string == 5 and notes[6].fret == 1
    print("fingering ok")


def perform(song, judge, play=True, pitch_error=0.0, late=0.0, drop=()):
    """Feed the judge a synthetic performance at 86 frames/s and return it."""
    notes = song.notes
    t, dt, i, last = -0.5, HOP / RATE, 0, None
    end = song.duration + 1.0
    while t < end:
        midi, onset = None, False
        while i < len(notes) and notes[i].end + late < t:
            i += 1
        if play and i < len(notes) and i not in drop and notes[i].start + late <= t <= notes[i].end + late:
            midi = notes[i].midi + pitch_error
            if last != i:
                onset, last = True, i
        fr = PitchFrame(t, midi_to_freq(midi) if midi else 0.0, 0.9 if midi else 0.0, -20 if midi else -80, onset)
        judge.feed(fr)
        t += dt
    judge.finish(t)
    return judge


def test_judge(songs):
    ode = songs["3-3"]
    j = perform(ode, Judge(ode.notes))
    assert j.hits == len(ode.notes) and j.misses == 0, (j.hits, j.misses)
    mean, spread = j.timing_stats()
    assert abs(mean) < 0.02, mean
    assert j.stars() == 5
    j = perform(ode, Judge(ode.notes), play=False)
    assert j.hits == 0 and j.misses == len(ode.notes)
    j = perform(ode, Judge(ode.notes), pitch_error=1.0)       # a semitone sharp: everything wrong
    assert j.hits == 0, j.hits
    j = perform(ode, Judge(ode.notes), pitch_error=0.3)       # 30 cents sharp: still accepted
    assert j.hits == len(ode.notes), j.hits
    j = perform(ode, Judge(ode.notes), late=0.08)             # a bit behind: hits, flagged as dragging
    assert j.hits == len(ode.notes), (j.hits, j.misses)
    assert 0.05 < j.timing_stats()[0] < 0.12, j.timing_stats()
    j = perform(ode, Judge(ode.notes), drop=(3, 4, 5))
    assert j.misses == 3 and j.hits == len(ode.notes) - 3, (j.hits, j.misses)
    assert j.best_combo == len(ode.notes) - 6
    # repeated notes need separate plucks: one long E must not clear four E's
    opens = songs["1-1"]
    j = Judge(opens.notes)
    t = -0.2
    while t < opens.duration + 1:
        fr = PitchFrame(t, midi_to_freq(64), 0.9, -20, onset=(abs(t) < 0.01))
        j.feed(fr)
        t += 0.0116
    j.finish(t)
    assert j.hits == 0 and j.misses == len(opens.notes), (j.hits, j.misses)   # 64 is high E, note 0 is low E
    chrom = songs["2-2"]
    j = Judge(chrom.notes)
    t = -0.2
    while t < chrom.duration + 1:
        j.feed(PitchFrame(t, midi_to_freq(41), 0.9, -20, onset=(abs(t) < 0.01)))   # F2 held forever
        t += 0.0116
    j.finish(t)
    assert j.hits == 1, "one long note should clear only the first F, got %d" % j.hits
    print("judge ok")


def test_backing(songs):
    ode = songs["3-3"]
    t0 = time.perf_counter()
    wav = backing.ensure_backing(ode, force=True)
    assert wav and os.path.exists(wav)
    import wave
    with wave.open(wav) as w:
        secs = w.getnframes() / w.getframerate()
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
    assert ode.duration - 0.5 < secs < ode.duration + 5, (secs, ode.duration)
    assert backing.ensure_backing(songs["1-1"], force=True) is None
    slow = backing.ensure_backing(ode, force=True, speed=0.7)
    assert slow.endswith("@70.wav")
    with wave.open(slow) as w:
        slow_secs = w.getnframes() / w.getframerate()
    assert abs(slow_secs - secs / 0.7) < 2.0, (slow_secs, secs)
    print("backing ok: %s (%.1f s, rendered in %.2f s, soundfont=%s)" % (os.path.basename(wav), secs,
                                                                           time.perf_counter() - t0, backing.find_soundfont()))


def test_screens(folder):
    os.makedirs(OUT, exist_ok=True)
    app = App("test", (scenes.WIDTH, scenes.HEIGHT))
    app.settings.update(songs_dir=folder, song=None, demo=True, latency=0.0, metronome=True, speed=1.0)
    app.settings["paths"] = curriculum.write_all(folder)
    app.settings["progress"] = Progress(folder, unlock_all=True)
    app.sfx = Sfx()
    app.settings["ear"] = scenes.Ear(enabled=False)
    app.scene = scenes.TitleScene(app)
    for _ in range(10):
        app.frame()
    pygame.image.save(app.screen, os.path.join(OUT, "strum_title.png"))
    app.scene = scenes.TitleScene(app, 2, 1)                # stage 3, second row
    app.frame()
    app.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))      # Ode to Joy
    app.scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    app.frame()
    play = app.scene
    assert isinstance(play, scenes.PlayScene) and play.song.title == "Ode to Joy", play.song.title
    work, frames = 0.0, 0
    shot = False
    while isinstance(app.scene, scenes.PlayScene):
        t0 = time.perf_counter()
        app.frame()
        work += time.perf_counter() - t0
        frames += 1
        if not shot and play.song_time > 4.0:
            pygame.image.save(app.screen, os.path.join(OUT, "strum_play.png"))
            shot = True
        play.t0 -= 0.05                              # fast-forward: 50 ms of song per frame
        if frames > 5000:
            raise AssertionError("song never ended")
    assert isinstance(app.scene, scenes.ResultScene)
    j = play.judge
    assert j.hits == len(play.notes), "demo should be perfect: %d/%d" % (j.hits, len(play.notes))
    for _ in range(5):
        app.frame()
    pygame.image.save(app.screen, os.path.join(OUT, "strum_result.png"))
    print("screens ok: %d play frames, %.2f ms per frame on this machine" % (frames, work / frames * 1000))
    pygame.quit()


if __name__ == "__main__":
    test_yin()
    test_tracker()
    test_fingering()
    with tempfile.TemporaryDirectory() as tmp:
        songs = test_songs(tmp)
        test_progress(tmp)
        test_judge(songs)
        test_backing(songs)
        test_screens(tmp)
    print("all guitar tests passed")
