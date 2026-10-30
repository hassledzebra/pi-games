"""Headless checks: motion detection, a long CPU-vs-CPU run, screenshots and a timing estimate.

    python tests/test_game.py          (screenshots go to tests/out/)
"""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from engine.app import App  # noqa: E402
from engine.sfx import Sfx  # noqa: E402
from games.fighter import scenes, sounds  # noqa: E402
from games.fighter.data import DP, QCB, QCF  # noqa: E402
from games.fighter.fighter import HEIGHT, WIDTH, motion_in  # noqa: E402

OUT = os.path.join(ROOT, "tests", "out")


def test_motions():
    assert motion_in([5, 5, 2, 3, 6], QCF)
    assert motion_in([2, 2, 3, 3, 6, 5, 5], QCF)
    assert not motion_in([6, 3, 2], QCF)
    assert motion_in([6, 5, 2, 3], DP)
    assert motion_in([2, 1, 4], QCB)
    assert not motion_in([2, 3, 6] + [5] * 20, QCF)  # too old
    print("motions ok")


def run():
    os.makedirs(OUT, exist_ok=True)
    app = App("test", (WIDTH, HEIGHT))
    app.settings["cpu_level"] = 2
    app.sfx = Sfx()
    sounds.build(app.sfx)

    for name, scene in (("title", scenes.TitleScene(app)), ("select", scenes.SelectScene(app, True)),
                        ("controls", scenes.ControlsScene(app))):
        app.scene = scene
        for _ in range(30):
            app.frame()
        pygame.image.save(app.screen, os.path.join(OUT, name + ".png"))

    app.settings["demo_loop"] = True
    fight = scenes.FightScene.demo(app, seed=3)
    app.scene = fight
    totals = {"hits": 0, "blocks": 0, "specials": 0, "rounds": 0, "matches": 0}
    shots = {150, 400, 900, 1600, 2600}
    frames, work = 12000, 0.0
    for i in range(frames):
        t0 = time.perf_counter()
        app.frame()
        work += time.perf_counter() - t0
        if app._next_scene is not None:  # demo match ended, a new one starts
            for k in totals:
                totals[k] += app.scene.stats[k]
        if i in shots:
            pygame.image.save(app.screen, os.path.join(OUT, "fight_%04d.png" % i))
    for k in totals:
        totals[k] += app.scene.stats[k]
    print("cpu vs cpu over %d frames:" % frames, totals)
    print("avg frame (update+draw+flip) on this PC: %.2f ms" % (work / frames * 1000))
    assert totals["hits"] > 20 and totals["rounds"] >= 2, totals


if __name__ == "__main__":
    test_motions()
    run()
    print("all good")
