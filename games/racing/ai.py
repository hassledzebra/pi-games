"""CPU drivers. Each one steers its kart through a VirtualInput, exactly like a
human on a pad, towards a point a little way ahead on the centreline (offset
by its own lane), drifts into bends at the higher levels, dodges hazards on
the road, uses items with simple rules and is rubber-banded to the leader.
"""
import math
import random

from engine.input import VirtualInput

from .kart import norm_angle

LEVELS = {
    0: {"name": "EASY", "cap": 0.84, "drift": 0.0, "rubber": 0.05, "items": 0.4},
    1: {"name": "NORMAL", "cap": 0.92, "drift": 0.5, "rubber": 0.07, "items": 0.7},
    2: {"name": "HARD", "cap": 1.0, "drift": 0.9, "rubber": 0.08, "items": 1.0},
}
FORWARD_ITEMS = ("chicken", "pie", "balloon", "banana")
BEHIND_ITEMS = ("gum", "banana")


class Driver:
    def __init__(self, kart, level=1, seed=None):
        self.kart = kart
        self.cfg = LEVELS[level]
        self.rng = random.Random(seed)
        self.input = VirtualInput()
        self.lane = self.rng.uniform(-12, 12)
        self.lane_t = 0
        self.held_item_t = 0
        self.drifting = False
        self.think = 0

    def update(self, karts, items, leader_prog):
        k, w, cfg = self.kart, self.kart.world, self.cfg
        held, pressed = set(), set()
        self.think += 1
        if k.finished is not None:
            k.cap = 0.6
            held.add("a")
            self.input.set(held, pressed)
            return
        self.lane_t -= 1
        if self.lane_t <= 0:
            self.lane_t = self.rng.randint(90, 240)
            self.lane = self.rng.uniform(-14, 14)
        # rubber band: trailing CPUs get a little extra, leading ones ease off
        behind = max(-1.0, min(1.0, (leader_prog - k.prog) / (w.n * 0.3)))
        k.cap = cfg["cap"] + cfg["rubber"] * behind
        # steer towards a point ahead on the centreline
        look = 5 + int(k.speed * 2.5)
        tx, ty = w.offset(k.seg + look, self.lane)
        ang = norm_angle(math.degrees(math.atan2(tx - k.x, -(ty - k.y))) - k.heading)
        fx, fy = w.offset(k.seg + look * 2 + 4, 0)
        far = norm_angle(math.degrees(math.atan2(fx - k.x, -(fy - k.y))) - k.heading)
        # dodge ground hazards straight ahead
        for it in items:
            if it.state == "ground":
                fwd, side = k.ahead_of_point(it.x, it.y)
                if 0 < fwd < 60 and abs(side) < 12:
                    ang = 35 if side < 0 else -35
                    break
        steer = 0
        if abs(ang) > 3:
            steer = 1 if ang > 0 else -1
        if k.speed < -0.2:
            steer = -steer
        if steer > 0:
            held.add("right")
        elif steer < 0:
            held.add("left")
        held.add("a")
        if abs(ang) > 60 and k.speed > 0.6 * k.top:
            held.discard("a")
        # drift into big bends (hold b while steering)
        if k.drift:
            self.drifting = True
        elif self.drifting:
            self.drifting = False
        elif steer and abs(far) > 28 and k.speed > 0.65 * k.top and not k.air and \
                self.rng.random() < cfg["drift"] * 0.12:
            pressed.add("b")
        # stuck against a wall: reverse for a moment
        if k.speed < 0.3 and k.frame > 180 and k.surface == 3 or (k.speed < 0.2 and k.frame % 240 > 200 and k.frame > 180):
            held.discard("a")
            held.add("b")
        # items
        self.items = items
        if k.item:
            self.held_item_t += 1
            if self.think % 5 == 0 and self.rng.random() < cfg["items"]:
                self.use_item(k, karts, held, pressed)
        else:
            self.held_item_t = 0
        self.input.set(held, pressed)

    def use_item(self, k, karts, held, pressed):
        kind = k.item
        ahead = behind = False
        for o in karts:
            if o is k:
                continue
            fwd, side = k.ahead_of(o)
            if 10 < fwd < 140 and abs(side) < 30:
                ahead = True
            if -80 < fwd < -8 and abs(side) < 22:
                behind = True
        hazard_ahead = any(it.state == "ground" and 0 < k.ahead_of_point(it.x, it.y)[0] < 70
                           and abs(k.ahead_of_point(it.x, it.y)[1]) < 14 for it in self.items)
        crate_near = any(c.active and abs(c.x - k.x) < 120 and abs(c.y - k.y) < 120 for c in k.world.crates)
        if kind == "pepper":                                # on a straight
            if abs(self.last_ang(k)) < 15 and not k.air or self.held_item_t > 300:
                pressed.add("up")
        elif kind == "shield":                              # when something is close behind
            if behind or self.held_item_t > 360:
                pressed.add("up")
        elif kind == "pogo":                                # before a known banana / gum
            if hazard_ahead and not k.air or self.held_item_t > 600:
                pressed.add("up")
        elif kind == "magnet":
            if crate_near and k.item_lock == 0 or self.held_item_t > 300:
                pressed.add("up")
        elif kind in FORWARD_ITEMS and ahead:
            pressed.add("up")
        elif kind in BEHIND_ITEMS and behind:
            held.add("down")
            pressed.add("up")
        elif self.held_item_t > 420:                         # don't hoard forever
            if kind in BEHIND_ITEMS:
                held.add("down")
            pressed.add("up")

    def last_ang(self, k):
        w = k.world
        tx, ty = w.offset(k.seg + 12, 0)
        return norm_angle(math.degrees(math.atan2(tx - k.x, -(ty - k.y))) - k.heading)
