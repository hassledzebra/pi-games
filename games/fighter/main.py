import argparse

from engine.app import App, on_pi
from engine.sfx import Sfx

from . import sounds
from .fighter import HEIGHT, WIDTH
from .scenes import FightScene, TitleScene


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pi Brawl - 2D versus fighting game")
    ap.add_argument("--fullscreen", dest="fullscreen", action="store_true", help="default on a Raspberry Pi")
    ap.add_argument("--windowed", dest="fullscreen", action="store_false", help="default elsewhere")
    ap.add_argument("--demo", action="store_true", help="CPU vs CPU attract mode")
    ap.add_argument("--mute", action="store_true", help="no sound")
    ap.add_argument("--fps", action="store_true", help="show the frame rate (toggle with F3)")
    ap.add_argument("--level", type=int, choices=(0, 1, 2), default=1, help="CPU level: 0 easy, 1 normal, 2 hard")
    ap.set_defaults(fullscreen=None)
    args = ap.parse_args(argv)

    app = App("Pi Brawl", (WIDTH, HEIGHT), fullscreen=on_pi() if args.fullscreen is None else args.fullscreen)
    app.show_fps = args.fps
    app.settings["cpu_level"] = args.level
    app.sfx = Sfx(enabled=not args.mute)
    sounds.build(app.sfx)
    app.run(FightScene.demo(app) if args.demo else TitleScene(app))
