"""Title, controls, racer select, track select, the race itself and the results."""
import math
import random
import time

import pygame

from engine import text
from engine.app import Scene
from engine.input import NEUTRAL

from . import art, records
from .ai import LEVELS, Driver
from .data import GP_POINTS, GP_TRACKS, HEIGHT, ITEMS, LAPS, ROSTER, TRACKS, WIDTH
from .items import ItemSystem
from .kart import Kart, collide, slipstreams
from .render import Mode7View, TopDownView, draw_hud, draw_minimap, fmt_time
from .world import World, catmull

WHITE = (255, 255, 255)
YELLOW = (255, 220, 60)
RED = (230, 60, 50)
P_COLORS = ((235, 70, 60), (60, 140, 255))
CAMERAS = ("CHASE", "OVERHEAD")


def get_world(app, track_idx):
    """Worlds are built once and kept (about 4 MB each)."""
    worlds = app.settings.setdefault("worlds", {})
    w = worlds.get(track_idx)
    if w is None:
        w = worlds[track_idx] = World(TRACKS[track_idx])
    return w


class Menu:
    def __init__(self, items, y, size=18, gap=16):
        self.items = items
        self.index = 0
        self.y = y
        self.size = size
        self.gap = gap

    def update(self, app, inp):
        """Returns the chosen index or None."""
        if "up" in inp.pressed:
            self.index = (self.index - 1) % len(self.items)
            app.play("select")
        elif "down" in inp.pressed:
            self.index = (self.index + 1) % len(self.items)
            app.play("select")
        elif "a" in inp.pressed or "start" in inp.pressed:
            app.play("confirm")
            return self.index
        return None

    def draw(self, surf, labels=None, blink=0, x=WIDTH // 2):
        for i, item in enumerate(labels or self.items):
            sel = i == self.index
            color = YELLOW if sel else (200, 200, 220)
            y = self.y + i * self.gap
            text.draw(surf, item, self.size, color, (x, y))
            if sel and (blink // 15) % 2 == 0:
                w = text.render(item, self.size, color).get_width()
                text.draw(surf, ">", self.size, color, (x - w // 2 - 10, y))


def darken(surf, alpha=140):
    shade = pygame.Surface(surf.get_size())
    shade.set_alpha(alpha)
    surf.blit(shade, (0, 0))


class Backdrop:
    """A CPU kart lapping Harbor Loop behind the menus, seen through the chase camera."""

    def __init__(self, app):
        self.world = get_world(app, 0)
        x, y, h, seg = self.world.start_positions(1)[0]
        self.kart = Kart(ROSTER[3], self.world, x, y, h, seg, 0)
        self.driver = Driver(self.kart, 1, seed=5)
        self.view = Mode7View(WIDTH, HEIGHT, self.world, angles=16)   # a background: coarse is fine
        self.cache = pygame.Surface((WIDTH, HEIGHT)).convert()

    def update(self):
        self.driver.update([self.kart], [], self.kart.prog)
        self.kart.control(self.driver.input)
        self.kart.update()
        self.kart.events.clear()

    def draw(self, surf, alpha=110):
        self.view.draw(self.cache, self.kart, [self.kart], [], self.world.crates)
        surf.blit(self.cache, (0, 0))
        darken(surf, alpha)


def backdrop(app):
    b = app.settings.get("backdrop")
    if b is None:
        b = app.settings["backdrop"] = Backdrop(app)
    return b


# ---------------------------------------------------------------------- title
class TitleScene(Scene):
    ITEMS = ["2P SPLIT SCREEN", "QUICK RACE", "GRAND PRIX", "TIME TRIAL", "CPU LEVEL", "CAMERA", "CONTROLS", "QUIT"]

    def __init__(self, app):
        super().__init__(app)
        self.menu = Menu(self.ITEMS, 84, 15, 14)
        self.t = 0
        self.idle = 0
        self.back = backdrop(app)

    def update(self):
        inp = self.app.input.any
        self.t += 1
        self.back.update()
        self.idle = 0 if inp.pressed or inp.held else self.idle + 1
        level = self.app.settings["cpu_level"]
        cam = self.app.settings["camera"]
        if self.menu.index == 4 and inp.pressed & {"left", "right"}:
            self.app.settings["cpu_level"] = (level + (1 if "right" in inp.pressed else -1)) % 3
            self.app.play("select")
        elif self.menu.index == 5 and inp.pressed & {"left", "right"}:
            self.app.settings["camera"] = 1 - cam
            self.app.play("select")
        choice = self.menu.update(self.app, inp)
        if choice == 0:
            self.app.switch(SelectScene(self.app, {"mode": "split", "players": 2}))
        elif choice == 1:
            self.app.switch(SelectScene(self.app, {"mode": "quick", "players": 1}))
        elif choice == 2:
            self.app.switch(SelectScene(self.app, {"mode": "gp", "players": 1}))
        elif choice == 3:
            self.app.switch(SelectScene(self.app, {"mode": "time", "players": 1}))
        elif choice == 4:
            self.app.settings["cpu_level"] = (level + 1) % 3
        elif choice == 5:
            self.app.settings["camera"] = 1 - cam
        elif choice == 6:
            self.app.switch(ControlsScene(self.app))
        elif choice == 7:
            self.app.quit()
        if self.idle > 60 * 20:
            self.app.switch(RaceScene.demo(self.app))

    def draw(self, surf):
        self.back.draw(surf, 100)
        bounce = round(math.sin(self.t * 0.05) * 2)
        text.draw(surf, "PI RUSH", 60, (40, 20, 60), (WIDTH // 2 + 3, 10 + bounce + 3), shadow=None)
        text.draw(surf, "PI RUSH", 60, YELLOW, (WIDTH // 2, 10 + bounce), shadow=RED)
        text.draw(surf, "a Raspberry Pi kart racer", 14, (230, 220, 255), (WIDTH // 2, 60))
        panel = pygame.Surface((200, 118), pygame.SRCALPHA)
        panel.fill((20, 14, 40, 170))
        surf.blit(panel, (WIDTH // 2 - 100, 78))
        labels = list(self.ITEMS)
        labels[4] = "CPU LEVEL: < %s >" % LEVELS[self.app.settings["cpu_level"]]["name"]
        labels[5] = "CAMERA: < %s >" % CAMERAS[self.app.settings["camera"]]
        self.menu.draw(surf, labels, self.t)
        for i, r in enumerate(ROSTER):                   # the roster waving along the bottom
            x = 24 + i * 60
            exp = "win" if (self.t // 40 + i) % 6 == 0 else "normal"
            surf.blit(art.portrait(r, exp, 28), (x, HEIGHT - 32 + round(math.sin(self.t * 0.1 + i) * 2)))
        text.draw(surf, "F11 fullscreen   F3 fps", 11, (180, 170, 200), (WIDTH - 4, HEIGHT - 12), align="right")


class ControlsScene(Scene):
    LINES = [
        ("", "PLAYER 1", "PLAYER 2"),
        ("Steer", "A / D", "Left / Right"),
        ("Accelerate", "F", "K  or  Num1"),
        ("Brake / reverse", "G", "L  or  Num2"),
        ("Drift", "tap G while steering", "tap L while steering"),
        ("Use item", "W", "Up"),
        ("Item backwards", "S + W", "Down + Up"),
        ("Look behind", "S", "Down"),
        ("Pause", "Esc", "Enter"),
        ("Gamepad", "1st pad: A gas, B brake", "2nd pad: d-pad / stick"),
    ]

    def update(self):
        backdrop(self.app).update()
        if self.app.input.any.pressed & {"a", "b", "start"}:
            self.app.play("confirm")
            self.app.switch(TitleScene(self.app))

    def draw(self, surf):
        backdrop(self.app).draw(surf, 170)
        text.draw(surf, "CONTROLS", 26, YELLOW, (WIDTH // 2, 4))
        for i, (a, b, c) in enumerate(self.LINES):
            y = 30 + i * 13
            col = YELLOW if i == 0 else WHITE
            text.draw(surf, a, 13, col, (10, y), align="left")
            text.draw(surf, b, 13, col, (190, y))
            text.draw(surf, c, 13, col, (310, y))
        tips = ["Hold a drift for a boost: orange, then blue, then white sparks.",
                "Boost pads and slipstreams are free speed. Crates give items."]
        for i, line in enumerate(tips):
            text.draw(surf, line, 12, (210, 210, 230), (WIDTH // 2, 166 + i * 12))
        text.draw(surf, "press a button to go back", 12, YELLOW, (WIDTH // 2, HEIGHT - 14))


# ---------------------------------------------------------------------- racer select
class SelectScene(Scene):
    def __init__(self, app, cfg):
        super().__init__(app)
        self.cfg = cfg
        self.players = cfg["players"]
        self.cursor = [0, 1]
        self.done = [False, self.players < 2]
        self.t = 0
        self.ready_t = 0

    def update(self):
        self.t += 1
        backdrop(self.app).update()
        if all(self.done):
            self.ready_t += 1
            if self.ready_t > 30:
                self.cfg["humans"] = [self.cursor[i] for i in range(self.players)]
                if self.cfg["mode"] == "gp":
                    self.cfg["gp"] = {"round": 0, "points": {}}
                    self.cfg["track"] = GP_TRACKS[0]
                    self.app.switch(RaceScene(self.app, self.cfg))
                else:
                    self.app.switch(TrackSelectScene(self.app, self.cfg))
            return
        if self.players == 1:
            self._control(0, self.app.input.any)
        else:
            for slot in (0, 1):
                self._control(slot, self.app.input.players[slot])

    def _control(self, slot, inp):
        if "b" in inp.pressed:
            self.app.play("select")
            if self.done[slot]:
                self.done[slot] = False
            else:
                self.app.switch(TitleScene(self.app))
            return
        if self.done[slot]:
            return
        n = len(ROSTER)
        if "left" in inp.pressed:
            self.cursor[slot] = (self.cursor[slot] - 1) % n
            self.app.play("select")
        elif "right" in inp.pressed:
            self.cursor[slot] = (self.cursor[slot] + 1) % n
            self.app.play("select")
        elif "up" in inp.pressed or "down" in inp.pressed:
            self.cursor[slot] = (self.cursor[slot] + 3) % n
            self.app.play("select")
        elif inp.pressed & {"a", "start"}:
            if self.players == 2 and self.done[1 - slot] and self.cursor[1 - slot] == self.cursor[slot]:
                return                                    # no two of the same racer
            self.done[slot] = True
            self.app.play("confirm")

    def draw(self, surf):
        backdrop(self.app).draw(surf, 150)
        text.draw(surf, "CHOOSE YOUR RACER", 22, YELLOW, (WIDTH // 2, 3))
        cw, ch = 118, 84
        for i, r in enumerate(ROSTER):
            x, y = 12 + (i % 3) * 124, 24 + (i // 3) * 90
            pygame.draw.rect(surf, (30, 24, 50), (x, y, cw, ch), border_radius=4)
            pygame.draw.rect(surf, (90, 80, 130), (x, y, cw, ch), 1, border_radius=4)
            picked = [s for s in range(self.players) if self.cursor[s] == i]
            exp = "win" if picked and self.done[picked[0]] else ("hit" if False else "normal")
            surf.blit(art.portrait(r, exp, 32), (x + 4, y + 4))
            text.draw(surf, r.name, 16, r.body, (x + 40, y + 4), align="left")
            text.draw(surf, r.vehicle, 11, (210, 200, 230), (x + 40, y + 18), align="left")
            surf.blit(art.kart_rear(r), (x + 60, y + 32))
            frame = art.kart_top_rotations(r)[(self.t // 6 + i * 5) % 32]
            surf.blit(frame, (x + 24 - frame.get_width() // 2, y + 50 - frame.get_height() // 2))
            for j, (lab, val) in enumerate((("SPD", r.speed), ("ACC", r.accel), ("HND", r.handling), ("WGT", r.weight))):
                yy = y + 38 + j * 9
                text.draw(surf, lab, 10, (200, 200, 220), (x + 4, yy - 1), align="left")
                for k in range(5):
                    surf.fill(art.OUT, (x + 24 + k * 6, yy, 5, 4))
                    surf.fill(r.body if k < val else (70, 64, 100), (x + 25 + k * 6, yy + 1, 3, 2))
        for slot in range(self.players - 1, -1, -1):
            i = self.cursor[slot]
            x, y = 12 + (i % 3) * 124, 24 + (i // 3) * 90
            inset = 2 + slot * 3
            col = P_COLORS[slot] if not self.done[slot] or (self.t // 4) % 2 else WHITE
            pygame.draw.rect(surf, col, (x - inset, y - inset, cw + inset * 2, ch + inset * 2), 2, border_radius=5)
            text.draw(surf, "%dP" % (slot + 1), 14, P_COLORS[slot], (x + cw - 4 - slot * 18, y + ch - 14), align="right")
        if all(self.done):
            msg = "GET READY!"
        else:
            msg = ROSTER[self.cursor[0]].blurb + "   (accelerate = pick, brake = back)"
        text.draw(surf, msg, 13, YELLOW, (WIDTH // 2, HEIGHT - 14))


# ---------------------------------------------------------------------- track select
class TrackSelectScene(Scene):
    def __init__(self, app, cfg):
        super().__init__(app)
        self.cfg = cfg
        self.index = cfg.get("track", 0)
        self.t = 0
        self.previews = []
        for tr in TRACKS:                                 # cheap outline previews from the control points
            s = pygame.Surface((64, 64), pygame.SRCALPHA)
            pts = [(4 + p[0] * 56 / 1024, 4 + p[1] * 56 / 1024) for p in catmull(tr.points, 8)]
            pygame.draw.lines(s, art.OUT, True, pts, 5)
            pygame.draw.lines(s, (200, 200, 210), True, pts, 2)
            self.previews.append(s)

    def update(self):
        self.t += 1
        backdrop(self.app).update()
        inp = self.app.input.any
        if "b" in inp.pressed:
            self.app.play("select")
            self.app.switch(SelectScene(self.app, self.cfg))
            return
        if "left" in inp.pressed or "up" in inp.pressed:
            self.index = (self.index - 1) % len(TRACKS)
            self.app.play("select")
        elif "right" in inp.pressed or "down" in inp.pressed:
            self.index = (self.index + 1) % len(TRACKS)
            self.app.play("select")
        elif inp.pressed & {"a", "start"}:
            self.app.play("confirm")
            self.cfg["track"] = self.index
            self.app.switch(RaceScene(self.app, self.cfg))

    def draw(self, surf):
        backdrop(self.app).draw(surf, 150)
        text.draw(surf, "CHOOSE A TRACK", 22, YELLOW, (WIDTH // 2, 3))
        for i, tr in enumerate(TRACKS):
            x = 8 + i * 75
            sel = i == self.index
            pygame.draw.rect(surf, (30, 24, 50), (x, 28, 70, 100), border_radius=4)
            pygame.draw.rect(surf, YELLOW if sel else (90, 80, 130), (x, 28, 70, 100), 2 if sel else 1, border_radius=4)
            surf.blit(self.previews[i], (x + 3, 32))
            for j, word in enumerate(tr.name.split()):
                text.draw(surf, word, 12, WHITE if sel else (200, 200, 220), (x + 35, 98 + j * 12))
        tr = TRACKS[self.index]
        text.draw(surf, tr.blurb, 14, WHITE, (WIDTH // 2, 140))
        rec = records.get(tr.name)
        if rec:
            text.draw(surf, "Best lap %s by %s" % (fmt_time(rec["best_lap"]), rec["racer"]), 13, (200, 230, 255), (WIDTH // 2, 158))
        text.draw(surf, "%d laps   accelerate = race, brake = back" % LAPS, 13, YELLOW, (WIDTH // 2, HEIGHT - 14))


# ---------------------------------------------------------------------- race
class RaceScene(Scene):
    COUNTDOWN = 220

    def __init__(self, app, cfg, seed=None):
        super().__init__(app)
        self.cfg = cfg
        self.mode = cfg["mode"]
        self.track_idx = cfg["track"]
        self.track = TRACKS[self.track_idx]
        self.rng = random.Random(seed)
        self.phase = "loading"
        self.loading_shown = False
        self.t = 0
        self.pause_menu = None
        self.count = self.COUNTDOWN
        self.world = None
        self.finish_t = 0
        self.lod = 0
        self.frame_ms = []
        self.results = None
        self.ghost = None
        self.stats = {"laps": 0, "items_fired": 0, "hits": 0, "finished": 0}

    @staticmethod
    def demo(app, seed=None):
        rng = random.Random(seed)
        return RaceScene(app, {"mode": "demo", "track": rng.randrange(len(TRACKS)), "humans": []}, seed=seed)

    # -- setup ------------------------------------------------------------
    def setup(self):
        w, cfg = self.world, self.cfg
        humans = list(cfg.get("humans", []))
        count = 1 if self.mode == "time" else 6
        pool = [i for i in range(len(ROSTER)) if i not in humans]
        self.rng.shuffle(pool)
        cpus = pool[:count - len(humans)]
        order = cpus + humans                             # humans start at the back
        level = self.app.settings.get("cpu_level", 1)
        self.karts, self.drivers, self.human_karts = [], {}, []
        for slot, (x, y, heading, seg) in zip(order, w.start_positions(len(order))):
            k = Kart(ROSTER[slot], w, x, y, heading, seg, slot)
            self.karts.append(k)
            if slot in humans:
                self.human_karts.append(k)
            else:
                self.drivers[k] = Driver(k, level, seed=self.rng.random())
        self.human_karts.sort(key=lambda k: humans.index(k.slot))
        crates = [] if self.mode == "time" else w.crates
        self.items = ItemSystem(w, self.karts, seed=self.rng.random())
        self.items.crates = crates
        self.crates = crates
        self.cam_karts = self.human_karts if self.human_karts else self.karts[:2]
        View = (Mode7View, TopDownView)[self.app.settings.get("camera", 0)]
        if len(self.cam_karts) == 2:
            self.rects = [pygame.Rect(0, 0, WIDTH, HEIGHT // 2), pygame.Rect(0, HEIGHT // 2, WIDTH, HEIGHT // 2)]
        else:
            self.rects = [pygame.Rect(0, 0, WIDTH, HEIGHT)]
        q = self.app.settings.get("ground_q", 1.0)   # ground resolution: 1 = full, 0.5 = half-size buffer
        self.views = [View(r.w, r.h, w, q=q) if View is Mode7View else View(r.w, r.h, w) for r in self.rects]
        for v in self.views:
            v.smooth = self.app.settings.get("smooth", True)
        self.lod = self.app.settings.get("lod", 0)   # full detail everywhere; the valve lowers it if needed
        for v in self.views:
            v.set_lod(self.lod)
        self.volatile = [True] * len(self.views)
        self.last_item = [None] * len(self.views)
        self.ranks = {k: i for i, k in enumerate(self.karts)}
        self.results = None
        self.go_frame = None
        # time trial ghost
        self.ghost = None
        self.lap_rec = []
        rec = records.get(self.track.name) if self.mode == "time" else None
        if rec:
            self.ghost_data = rec["ghost"]
            self.ghost_racer = next((r for r in ROSTER if r.name == rec["racer"]), ROSTER[0])
        else:
            self.ghost_data = None

    # -- update -----------------------------------------------------------
    def human_inputs(self):
        return [self.app.input.players[i] for i in range(len(self.human_karts))]

    def update(self):
        self.work_t0 = time.perf_counter()
        if self.mode == "demo" and self.app.input.any.pressed:
            self.app.switch(TitleScene(self.app))
            return
        if self.phase == "loading":
            if not self.loading_shown:
                self.loading_shown = True
                return
            self.world = get_world(self.app, self.track_idx)
            for idx, w in self.app.settings["worlds"].items():    # only the raced track keeps its 80 MB
                if idx != self.track_idx:
                    w.drop_rotations()
            self.setup()
            self.phase = "countdown"
            return
        if self.pause_menu:
            return self._update_pause()
        if self.mode != "demo" and self.phase in ("countdown", "race") and \
                any("start" in inp.pressed for inp in self.human_inputs()):
            self.pause_menu = Menu(["RESUME", "TITLE", "QUIT"], 92)
            return
        self.t += 1
        if self.phase == "countdown":
            self.count -= 1
            if self.count % 60 == 0 and self.count > 60:
                self.app.play("count")
            if self.count == 60:
                self.app.play("go")
                self.phase = "race"
                self.go_frame = self.karts[0].frame + 1
        self.step()
        if self.phase == "race":
            done = [k for k in self.cam_karts if k.finished is not None]
            if self.mode == "demo":                       # attract mode: wait for the top three
                fin = [k.finished for k in self.karts if k.finished is not None]
                if len(fin) >= 3 or (fin and self.t - min(fin) > 60 * 20) or self.t > 60 * 150:
                    self.phase = "finish"
            elif len(done) == len(self.cam_karts):
                self.phase = "finish"
        elif self.phase == "finish":
            self.finish_t += 1
            if self.finish_t > 150:
                self.end_race()

    def valve(self):
        """Safety valve, measured on our own work (update + draw, the flip is fixed): if it
        averages over 11 ms for a second, use fewer, taller ground strips."""
        self.frame_ms.append((time.perf_counter() - self.work_t0) * 1000)
        if len(self.frame_ms) >= 60:
            avg = sum(self.frame_ms) / len(self.frame_ms)
            self.frame_ms = []
            if avg > 11.0 and self.lod < 2 and "lod" not in self.app.settings:
                self.lod += 1
                for v in self.views:
                    v.set_lod(self.lod)

    def step(self):
        racing = self.phase in ("race", "finish")
        leader = max(k.prog for k in self.karts)
        half = self.lod >= 1                              # on a Pi, CPU karts step at 30 Hz (dt = 2)
        for i, k in enumerate(self.karts):
            d = self.drivers.get(k)
            if d is None and k.finished is not None:      # finished humans cruise on
                d = self.drivers[k] = Driver(k, 0, seed=1)
            if d is not None:
                dt = 1
                if half:
                    if (self.t + i) % 2:
                        continue
                    dt = 2
                if half or (self.t + i) % 3 == 0:         # CPU drivers think at 30 / 20 Hz
                    d.update(self.karts, self.items.items, leader)
                k.control(d.input if racing else NEUTRAL)
                d.input.pressed = frozenset()
                k.update(dt)
            else:
                k.control(self.app.input.players[self.human_karts.index(k)] if racing else NEUTRAL)
                k.update()
        if self.t % 2 == 0:
            collide(self.karts)
        elif self.t % 4 == 1:
            slipstreams(self.karts)
        if (self.crates or self.items.items) and self.t % 2 == 1:
            self.items.update(self.ranks)
        if self.t % 4 == 0 or self.phase == "finish":
            order = sorted(self.karts, key=lambda k: (k.finished if k.finished is not None else 1e9, -k.prog))
            self.ranks = {k: i for i, k in enumerate(order)}
        for k in self.karts:
            for ev in k.events:
                if ev in ("spin", "slip", "squawk", "splat", "gum", "splash"):
                    self.stats["hits"] += 1
                if ev in ("throw", "drop", "squawk", "sizzle", "shield", "boing", "hum"):
                    self.stats["items_fired"] += 1
                if ev == "lap":
                    self.stats["laps"] += 1
                    if k in self.human_karts and self.mode == "time":
                        self.record_lap(k)
                if ev == "finish":
                    self.stats["finished"] += 1
                    if k in self.human_karts:
                        self.app.play("cheer")
                if k in self.cam_karts or ev in ("squawk", "splat", "pop", "boing", "finish"):
                    self.app.play(ev)
            k.events.clear()
        if self.mode == "time" and self.human_karts:
            k = self.human_karts[0]
            self.lap_rec.append((k.x, k.y, k.heading, k.alt))
            if self.ghost_data:
                i = k.frame - k.lap_start
                if i < len(self.ghost_data):
                    g = self.ghost_data[i]
                    self.ghost = (g[0], g[1], g[2], g[3], self.ghost_racer)
                else:
                    self.ghost = None

    def record_lap(self, k):
        if k.laps_done and len(self.lap_rec) > 60:
            lap = k.laps_done[-1]
            if records.save(self.track.name, lap, k.racer.name, self.lap_rec):
                self.app.play("cheer")
        self.lap_rec = []

    def end_race(self):
        order = sorted(self.karts, key=lambda k: (k.finished if k.finished is not None else 1e9, -k.prog))
        results = [(k, (k.finished - self.go_frame) if k.finished is not None else None) for k in order]
        self.results = results
        if self.mode == "demo":
            self.app.switch(RaceScene.demo(self.app) if self.app.settings.get("demo_loop", True)
                            else TitleScene(self.app))
            return
        gp = self.cfg.get("gp")
        if gp:
            for i, (k, _) in enumerate(results):
                gp["points"][k.slot] = gp["points"].get(k.slot, 0) + GP_POINTS[i]
        self.app.switch(ResultsScene(self.app, self.cfg, results))

    def _update_pause(self):
        for inp in self.human_inputs():
            if "start" in inp.pressed or "b" in inp.pressed:
                self.pause_menu = None
                return
            choice = self.pause_menu.update(self.app, inp)
            if choice == 0:
                self.pause_menu = None
            elif choice == 1:
                self.app.switch(TitleScene(self.app))
            elif choice == 2:
                self.app.quit()
            if choice is not None:
                return

    # -- draw -------------------------------------------------------------
    def draw(self, surf):
        if self.phase == "loading":
            surf.fill((24, 18, 54))
            text.draw(surf, "LOADING", 30, YELLOW, (WIDTH // 2, 80), shadow=RED)
            text.draw(surf, self.track.name, 20, WHITE, (WIDTH // 2, 116))
            text.draw(surf, self.track.blurb, 13, (210, 210, 230), (WIDTH // 2, 140))
            return
        countdown = None
        if self.phase == "countdown" or (self.phase == "race" and self.count > 0):
            if self.phase == "race":
                self.count -= 1
            countdown = self.count // 60 if self.count > 60 else 0
        for i, (rect, view, k) in enumerate(zip(self.rects, self.views, self.cam_karts)):
            sub = surf.subsurface(rect)
            # on a Pi (lod >= 1) each split view refreshes its ground every other frame; the top
            # rows are only restored when something volatile (a message, the item label) was there
            refresh = self.lod == 0 or len(self.views) == 1 or (self.t + i) % 2 == 0
            full = self.volatile[i] or self.last_item[i] != k.item
            self.last_item[i] = k.item
            view.draw(sub, k, self.karts, self.items.items, self.crates, self.ghost, refresh, full)
            rank = self.ranks[k]
            finished = rank if k.finished is not None else None
            timer = (k.frame - self.go_frame) if self.mode == "time" and self.go_frame else None
            self.volatile[i] = draw_hud(sub, k, rank, len(self.karts), self.t, finished, countdown, timer)
            if self.mode == "time" and k.laps_done:
                text.draw(sub, "LAST %s" % fmt_time(k.laps_done[-1]), 12, (200, 230, 255), (rect.w - 26, 18), align="right")
        if len(self.rects) == 2:
            surf.fill(art.OUT, (0, HEIGHT // 2 - 1, WIDTH, 2))
            draw_minimap(surf, self.world, self.karts, (WIDTH - 48, HEIGHT // 2 - 22), self.t)
        else:
            draw_minimap(surf, self.world, self.karts, (WIDTH - 48, 28), self.t)
        if self.mode == "demo":
            text.draw(surf, "DEMO - press any button", 12, YELLOW, (WIDTH // 2, HEIGHT // 2 - 6))
        if self.pause_menu:
            darken(surf, 150)
            text.draw(surf, "PAUSED", 36, YELLOW, (WIDTH // 2, 56), shadow=RED)
            self.pause_menu.draw(surf, blink=pygame.time.get_ticks() // 16)
        elif self.phase in ("race", "finish"):
            self.valve()


# ---------------------------------------------------------------------- results / podium
class ResultsScene(Scene):
    def __init__(self, app, cfg, results):
        super().__init__(app)
        self.cfg, self.results = cfg, results
        self.gp = cfg.get("gp")
        self.t = 0
        self.last_round = bool(self.gp) and self.gp["round"] >= len(GP_TRACKS) - 1
        if self.gp and not self.last_round:
            items = ["NEXT RACE", "TITLE", "QUIT"]
        elif self.gp:
            items = ["TITLE", "QUIT"]
        else:
            items = ["REMATCH", "TRACK SELECT", "TITLE", "QUIT"]
        self.menu = Menu(items, HEIGHT - 16 - 14 * (len(items) - 1), 14, 14)
        self.menu.y = 150 if not self.last_round else 176
        self.rng = random.Random(1)
        self.confetti = [[self.rng.randrange(WIDTH), self.rng.randrange(HEIGHT), self.rng.choice(P_COLORS + (YELLOW, WHITE))]
                         for _ in range(40)]
        app.play("cheer")

    def standings(self):
        pts = self.gp["points"]
        return sorted(pts.items(), key=lambda kv: -kv[1])

    def update(self):
        self.t += 1
        backdrop(self.app).update()
        for c in self.confetti:
            c[1] = (c[1] + 1 + c[0] % 2) % HEIGHT
        choice = self.menu.update(self.app, self.app.input.any)
        if choice is None:
            return
        label = self.menu.items[choice]
        if label == "NEXT RACE":
            self.gp["round"] += 1
            self.cfg["track"] = GP_TRACKS[self.gp["round"]]
            self.app.switch(RaceScene(self.app, self.cfg))
        elif label == "REMATCH":
            self.app.switch(RaceScene(self.app, self.cfg))
        elif label == "TRACK SELECT":
            self.app.switch(TrackSelectScene(self.app, self.cfg))
        elif label == "TITLE":
            self.app.switch(TitleScene(self.app))
        else:
            self.app.quit()

    def draw(self, surf):
        backdrop(self.app).draw(surf, 170)
        if self.last_round:
            return self.draw_podium(surf)
        text.draw(surf, "RESULTS - %s" % TRACKS[self.cfg["track"]].name, 20, YELLOW, (WIDTH // 2, 3))
        for i, (k, time_frames) in enumerate(self.results):
            y = 26 + i * 20
            exp = "win" if i < 3 else ("hit" if i == len(self.results) - 1 else "normal")
            surf.blit(art.portrait(k.racer, exp, 20), (20, y - 2))
            text.draw(surf, "%d." % (i + 1), 15, YELLOW, (14, y), align="right")
            text.draw(surf, k.racer.name, 15, k.racer.body, (46, y), align="left")
            text.draw(surf, fmt_time(time_frames) if time_frames is not None else "DNF", 15, WHITE, (150, y), align="left")
            if k.laps_done:
                text.draw(surf, "best lap %s" % fmt_time(min(k.laps_done)), 12, (200, 230, 255), (210, y + 1), align="left")
            if self.gp:
                text.draw(surf, "+%d" % GP_POINTS[i], 13, (120, 255, 150), (320, y), align="left")
        if self.gp:
            text.draw(surf, "STANDINGS", 13, YELLOW, (WIDTH - 10, 26), align="right")
            for j, (slot, pts) in enumerate(self.standings()):
                text.draw(surf, "%s %d" % (ROSTER[slot].name, pts), 12, WHITE, (WIDTH - 10, 40 + j * 11), align="right")
        self.menu.draw(surf, blink=self.t)

    def draw_podium(self, surf):
        for c in self.confetti:
            surf.fill(c[2], (c[0], c[1], 2, 2))
        text.draw(surf, "GRAND PRIX CHAMPION", 22, YELLOW, (WIDTH // 2, 4), shadow=RED)
        st = self.standings()
        base = 146
        blocks = ((WIDTH // 2, 40), (WIDTH // 2 - 80, 28), (WIDTH // 2 + 80, 20))
        for i, (bx, bh) in enumerate(blocks):
            if i >= len(st):
                break
            slot, pts = st[i]
            r = ROSTER[slot]
            pygame.draw.rect(surf, (60, 50, 90), (bx - 32, base - bh, 64, bh), border_radius=3)
            pygame.draw.rect(surf, YELLOW if i == 0 else (160, 160, 180), (bx - 32, base - bh, 64, bh), 2, border_radius=3)
            text.draw(surf, "%d" % (i + 1), 22, WHITE, (bx, base - bh + 2))
            exp = "win" if i == 0 else "normal"
            surf.blit(art.kart_rear(r, exp), (bx - 28, base - bh - 40))
            surf.blit(art.portrait(r, exp, 40), (bx - 60 if i else bx - 70, base - bh - 36 + round(math.sin(self.t * 0.2 + i) * 2)))
            text.draw(surf, "%s %d" % (r.name, pts), 12, r.body, (bx, base + 2))
        self.menu.draw(surf, blink=self.t)
