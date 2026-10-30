"""Profile a 6-kart split-screen race frame headless (for tuning on the Pi).

    python tests/profile_racing.py [frames]
"""
import cProfile
import os
import pstats
import statistics
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from engine.app import App  # noqa: E402
from engine.sfx import Sfx  # noqa: E402
from games.racing import scenes, sounds  # noqa: E402
from games.racing.data import HEIGHT, WIDTH  # noqa: E402


def main():
    frames = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    app = App("profile", (WIDTH, HEIGHT))
    app.settings["cpu_level"] = 2
    app.settings["camera"] = 0
    if len(sys.argv) > 2:
        app.settings["lod"] = int(sys.argv[2])   # force a detail level (the valve then leaves it alone)
    if len(sys.argv) > 3:
        app.settings["ground_q"] = float(sys.argv[3])   # ground buffer resolution: 1 full, 0.5 half
    if len(sys.argv) > 4:
        app.settings["smooth"] = bool(int(sys.argv[4]))  # 1: average far strips, 0: nearest texel
    app.sfx = Sfx()
    sounds.build(app.sfx)
    race = scenes.RaceScene(app, {"mode": "split", "track": 1, "humans": [0, 1], "players": 2}, seed=4)
    app.scene = race
    for _ in range(400):
        app.frame()
    print("lod after warm-up:", race.lod)
    tu, td, tf = [], [], []
    for _ in range(frames):
        t0 = time.perf_counter()
        app.input.update()
        app.scene.update()
        t1 = time.perf_counter()
        app.scene.draw(app.screen)
        t2 = time.perf_counter()
        pygame.display.flip()
        t3 = time.perf_counter()
        tu.append(t1 - t0)
        td.append(t2 - t1)
        tf.append(t3 - t2)
    print("median: update %.2f ms  draw %.2f ms  flip %.2f ms  total %.2f ms" % tuple(
        statistics.median(x) * 1000 for x in (tu, td, tf, [a + b + c for a, b, c in zip(tu, td, tf)])))
    print("lod now:", race.lod)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(frames):
        app.frame()
    pr.disable()
    pstats.Stats(pr).sort_stats("tottime").print_stats(18)


if __name__ == "__main__":
    main()
