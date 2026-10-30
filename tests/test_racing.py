"""Headless checks for Pi Rush: a scripted lap (lap counting, position), items,
power-ups, airtime over a crest, a long CPU-only race, screenshots and a timing estimate.

    python tests/test_racing.py          (screenshots go to tests/out/)
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
from engine.input import VirtualInput  # noqa: E402
from engine.sfx import Sfx  # noqa: E402
from games.racing import scenes, sounds  # noqa: E402
from games.racing.ai import Driver  # noqa: E402
from games.racing.data import HEIGHT, LAPS, ROSTER, TRACKS, WIDTH  # noqa: E402
from games.racing.items import ItemSystem  # noqa: E402
from games.racing.kart import Kart  # noqa: E402
from games.racing.world import World  # noqa: E402

OUT = os.path.join(ROOT, "tests", "out")


class ScriptedInput(VirtualInput):
    """Stands in for a human player's PlayerInput inside the App loop."""

    def poll(self, keys):
        pass

    def handle_event(self, event):
        pass


def show(app, scene):
    """Make `scene` current, dropping any switch a previous scene left pending."""
    app.scene = scene
    app._next_scene = None


def make_kart(world, racer=0, idx=0, lateral=0):
    x, y = world.offset(idx, lateral)
    import math
    heading = math.degrees(math.atan2(world.dirs[idx][1], world.dirs[idx][0])) + 90
    return Kart(ROSTER[racer], world, x, y, heading, idx, racer)


def drive(kart, frames, items=None, karts=None):
    """Let the CPU driver steer a kart for a while (optionally through an item system)."""
    d = Driver(kart, 2, seed=1)
    karts = karts or [kart]
    for _ in range(frames):
        d.update(karts, items.items if items else [], kart.prog)
        kart.control(d.input)
        kart.update()
        if items:
            items.update({k: i for i, k in enumerate(karts)})
        kart.events.clear()


def test_lap_counting():
    world = World(TRACKS[0])
    k = make_kart(world, idx=world.n - 5)
    assert k.lap == 1 and k.prog < 0
    d = Driver(k, 2, seed=1)
    laps_seen, frames = [], 0
    while len(k.laps_done) < 2 and frames < 60 * 90:
        d.update([k], [], k.prog)
        k.control(d.input)
        k.update()
        if "lap" in k.events:
            laps_seen.append(frames)
        k.events.clear()
        frames += 1
    assert len(k.laps_done) == 2, (k.laps_done, frames)
    assert k.lap == 3
    assert 600 < k.laps_done[0] < 60 * 40, k.laps_done
    # driving backwards over the line un-counts the lap; progress ordering works
    other = make_kart(world, racer=1, idx=10)
    assert k.prog > other.prog
    print("lap counting ok: laps at frames", laps_seen)


def test_items():
    world = World(TRACKS[4])
    a = make_kart(world, racer=0, idx=20)
    b = make_kart(world, racer=1, idx=24)
    karts = [a, b]
    items = ItemSystem(world, karts, seed=1)
    items.crates = []
    # a banana dropped on the road: a kart drives over it and spins out
    a.item = "banana"
    a.fire, a.fire_back = True, True
    items.update({a: 0, b: 1})
    assert a.item is None and len(items.items) == 1 and items.items[0].state == "ground"
    victim = make_kart(world, racer=2, idx=14)
    items.karts = [a, b, victim]
    inp = VirtualInput()
    inp.set({"a"})
    for _ in range(240):
        victim.control(inp)
        victim.update()
        items.update({a: 0, b: 1, victim: 2})
        if victim.spin:
            break
    assert victim.spin > 0 and victim.expr == "hit", "banana did not spin the victim"
    assert not items.items, "banana should be used up"
    # a thrown chicken hits the kart ahead
    b.speed = 0
    a.item = "chicken"
    a.fire, a.fire_back = True, False
    items.update({a: 0, b: 1, victim: 2})
    a.fire = False
    assert items.items and items.items[0].kind == "chicken"
    for _ in range(80):
        items.update({a: 0, b: 1, victim: 2})
        if b.spin:
            break
    assert b.spin > 0, "chicken did not hit the kart ahead"
    # a cream pie splats the view
    b.spin = 0
    a.item, a.fire = "pie", True
    items.update({a: 0, b: 1, victim: 2})
    a.fire = False
    for _ in range(80):
        items.update({a: 0, b: 1, victim: 2})
        if b.pie:
            break
    assert b.pie > 0, "pie did not splat"
    # position-weighted rolls: the leader never gets a pepper, the tail often does
    rolls = [items.roll(0) for _ in range(200)]
    assert "pepper" not in rolls and "banana" in rolls
    tail = [items.roll(5) for _ in range(200)]
    assert tail.count("pepper") > 30 and "banana" not in tail
    print("items ok")


def test_powerups():
    world = World(TRACKS[4])
    a = make_kart(world, racer=1, idx=120)                # a pad-free stretch of the oval
    karts = [a]
    items = ItemSystem(world, karts, seed=2)
    items.crates = []
    d = Driver(a, 0, seed=1)                              # easy driver: no drift boosts

    def cruise(frames):
        for _ in range(frames):
            d.update(karts, items.items, a.prog)
            a.control(d.input)
            a.update()
            a.events.clear()
    cruise(240)                                           # reach cruising speed
    base = a.speed
    assert base > 0.8 * a.top, (base, a.top)
    a.item, a.fire = "pepper", True
    items.update({a: 0})
    a.fire = False
    assert a.pepper > 0 and a.expr == "pepper"
    cruise(60)
    assert a.speed > base * 1.2, (a.speed, base)
    # shield absorbs one banana
    a.item, a.fire = "shield", True
    items.update({a: 0})
    a.fire = False
    assert a.shield > 0
    from games.racing.items import Item
    it = Item("banana", a.x, a.y, owner=None, state="ground")
    items.items.append(it)
    items.update({a: 0})
    assert a.shield == 0 and a.spin == 0 and not items.items, "shield should pop and absorb the banana"
    items.items.append(Item("banana", a.x, a.y, owner=None, state="ground"))
    items.update({a: 0})
    assert a.spin > 0, "second banana should hit"
    # pogo: a big jump (from the ground)
    while a.air:
        a.update()
    a.spin = a.hit_t = a.pepper = 0
    a.item, a.fire = "pogo", True
    items.update({a: 0})
    assert a.air and a.pogo_air and a.expr == "flail"
    print("power-ups ok")


def test_airtime():
    """Cinder Pass has a sharp jump crest at 47% of the lap: a fast kart leaves the ground."""
    world = World(TRACKS[1])
    crest = max(range(world.n), key=lambda i: world.heights[i] if 0.42 < i / world.n < 0.52 else -1)
    k = make_kart(world, racer=0, idx=crest - 30)
    k.speed = k.top
    inp = VirtualInput()
    inp.set({"a"})
    d = Driver(k, 2, seed=3)
    best_air, max_z = 0, 0.0
    for _ in range(300):
        d.update([k], [], k.prog)
        k.control(d.input)
        k.update()
        best_air = max(best_air, k.air)
        max_z = max(max_z, k.z)
    assert best_air >= 6 and max_z > 1.0, (best_air, max_z)
    flat = World(TRACKS[1], with_hills=False)
    assert max(flat.heights) == 0
    print("airtime ok: %d frames in the air, %.1f px high" % (best_air, max_z))


def run():
    os.makedirs(OUT, exist_ok=True)
    app = App("test", (WIDTH, HEIGHT))
    app.settings["cpu_level"] = 2
    app.settings["camera"] = 0
    app.sfx = Sfx()
    sounds.build(app.sfx)

    for name, scene in (("r_title", scenes.TitleScene(app)),
                        ("r_select", scenes.SelectScene(app, {"mode": "split", "players": 2})),
                        ("r_tracks", scenes.TrackSelectScene(app, {"mode": "quick", "players": 1, "humans": [0]})),
                        ("r_controls", scenes.ControlsScene(app))):
        show(app, scene)
        for _ in range(30):
            app.frame()
        pygame.image.save(app.screen, os.path.join(OUT, name + ".png"))

    # each track in split view (2 humans + 4 CPU), a few hundred frames in
    for ti, tr in enumerate(TRACKS):
        race = scenes.RaceScene(app, {"mode": "split", "track": ti, "humans": [0, 1], "players": 2}, seed=ti)
        show(app, race)
        for _ in range(400):
            app.frame()
        pygame.image.save(app.screen, os.path.join(OUT, "r_track%d_%s.png" % (ti, tr.theme)))
        if ti == 1:
            # crest / dip screenshots: park the first view's kart on the hill
            k = race.cam_karts[0]
            crest = max(range(race.world.n), key=lambda i: race.world.heights[i])
            for label, idx in (("crest", crest - 6), ("dip", crest + 22)):
                k.x, k.y = race.world.path[idx % race.world.n]
                k.seg, k.prog = idx % race.world.n, float(idx)
                k.alt = race.world.height_at(k.prog)
                import math
                k.heading = math.degrees(math.atan2(race.world.dirs[k.seg][1], race.world.dirs[k.seg][0])) + 90
                app.frame()
                pygame.image.save(app.screen, os.path.join(OUT, "r_hill_%s.png" % label))
    # overhead camera too
    app.settings["camera"] = 1
    race = scenes.RaceScene(app, {"mode": "split", "track": 0, "humans": [0, 1], "players": 2}, seed=9)
    show(app, race)
    for _ in range(300):
        app.frame()
    pygame.image.save(app.screen, os.path.join(OUT, "r_overhead.png"))
    app.settings["camera"] = 0

    # a long CPU-only race (demo mode) with timing
    app.settings["demo_loop"] = False
    race = scenes.RaceScene.demo(app, seed=3)
    race.track_idx = 1
    race.track = TRACKS[1]
    show(app, race)
    frames, work, hills_work = 0, 0.0, 0.0
    results = None
    while frames < 12000:
        t0 = time.perf_counter()
        app.frame()
        work += time.perf_counter() - t0
        frames += 1
        if frames == 600:
            pygame.image.save(app.screen, os.path.join(OUT, "r_demo.png"))
        if race.results is not None:
            results = race.results
            break
    assert results is not None, "the CPU race did not finish in %d frames" % frames
    finished = [k for k, t in results if t is not None]
    assert len(finished) >= 3, results
    print("cpu race: %d frames, order %s, stats %s" % (frames, [k.racer.name for k, _ in results], race.stats))
    print("avg frame (update+draw+flip) on this PC: %.2f ms" % (work / frames * 1000))
    # cost of the hills: the same split race frame with a flat world
    flat = World(TRACKS[1], with_hills=False)
    for label, world in (("hills", app.settings["worlds"][1]), ("flat", flat)):
        app.settings["worlds"][1] = world
        r = scenes.RaceScene(app, {"mode": "split", "track": 1, "humans": [0, 1], "players": 2}, seed=4)
        show(app, r)
        for _ in range(300):
            app.frame()
        t0 = time.perf_counter()
        for _ in range(300):
            app.frame()
        print("split-screen race frame, %s: %.3f ms" % (label, (time.perf_counter() - t0) / 300 * 1000))

    # pause menu: start pauses, accelerate on RESUME resumes
    race = scenes.RaceScene(app, {"mode": "quick", "track": 0, "humans": [0], "players": 1}, seed=7)
    show(app, race)
    vi = ScriptedInput()
    app.input.players[0] = vi
    for _ in range(5):
        app.frame()
    vi.set(set(), {"start"})
    app.frame()
    vi.set(set())
    assert race.pause_menu is not None, "start should pause"
    app.frame()
    vi.set(set(), {"a"})
    app.frame()
    vi.set(set())
    assert race.pause_menu is None, "RESUME should unpause"
    pygame.image.save(app.screen, os.path.join(OUT, "r_quick.png"))

    # time trial: a CPU-driven "human" sets a record, then races its own ghost
    from games.racing import records
    records.PATH = os.path.join(OUT, "records_test.json")
    records._data = None
    if os.path.exists(records.PATH):
        os.remove(records.PATH)
    for attempt in range(2):
        race = scenes.RaceScene(app, {"mode": "time", "track": 4, "humans": [4], "players": 1}, seed=6)
        show(app, race)
        drv, saw_ghost = None, False
        for i in range(6000):
            if race.phase != "loading" and drv is None:
                drv = Driver(race.human_karts[0], 2, seed=2)
            if drv:
                drv.update(race.karts, race.items.items, race.human_karts[0].prog)
                vi.set(drv.input.held, drv.input.pressed)
            app.frame()
            if race.ghost is not None:
                saw_ghost = True
                if attempt == 1 and i == 900:
                    pygame.image.save(app.screen, os.path.join(OUT, "r_timetrial.png"))
            if app._next_scene is not None:
                break
        assert race.human_karts[0].finished is not None, "time trial did not finish"
        rec = records.get(TRACKS[4].name)
        assert rec and len(rec["ghost"]) > 100 and rec["racer"] == ROSTER[4].name, rec
        if attempt == 1:
            assert saw_ghost, "the ghost should drive on the second attempt"
    print("time trial ok: best lap", rec["best_lap"], "frames")
    vi.set(set())

    # grand prix flow: NEXT RACE goes to the second GP track
    gp = {"mode": "gp", "track": 0, "humans": [2], "players": 1, "gp": {"round": 0, "points": {}}}
    race = scenes.RaceScene(app, gp, seed=8)
    show(app, race)
    for _ in range(3):
        app.frame()
    for k in race.karts:
        k.finished = k.frame + race.karts.index(k)
    race.go_frame = 0
    race.end_race()
    app.frame()
    assert isinstance(app.scene, scenes.ResultsScene) and gp["gp"]["points"]
    vi.set(set(), {"a"})
    app.frame()
    vi.set(set())
    assert isinstance(app._next_scene, scenes.RaceScene) and app._next_scene.track_idx == 1, "NEXT RACE"

    # results screen (quick race, 1 human) and the GP podium
    race = scenes.RaceScene(app, {"mode": "quick", "track": 4, "humans": [2], "players": 1}, seed=5)
    show(app, race)
    for _ in range(3):
        app.frame()
    for k in race.karts:                                 # fake a finished race
        k.finished = k.frame + race.karts.index(k)
    race.go_frame = 0
    race.end_race()
    app.frame()
    for _ in range(10):
        app.frame()
    pygame.image.save(app.screen, os.path.join(OUT, "r_results.png"))
    gp = {"mode": "gp", "track": 3, "humans": [2], "players": 1, "gp": {"round": 3, "points": {2: 31, 0: 25, 5: 18, 1: 10}}}
    show(app, scenes.ResultsScene(app, gp, race.results))
    for _ in range(10):
        app.frame()
    pygame.image.save(app.screen, os.path.join(OUT, "r_podium.png"))


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT))
    test_lap_counting()
    test_items()
    test_powerups()
    test_airtime()
    run()
    print("all good")
