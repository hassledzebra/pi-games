"""Item crates, held items, projectiles and ground hazards.

Six slapstick items (see data.ITEMS): Banana Skin and Bubble Gum stay on the
ground, Rubber Chicken flies level and homes a little, Cream Pie and Water
Balloon are lobbed in an arc, Turbo Can is used on yourself. `up` fires forward,
`down`+`up` throws/drops backward.
"""
import math
import random

from .data import ITEM_ORDER, ITEM_WEIGHTS

GRAVITY = 0.16


class Item:
    """One thing in the world. state: fly (has a z arc), ground (hazard), fx (short visual only)."""

    def __init__(self, kind, x, y, owner, vx=0.0, vy=0.0, vz=0.0, z=0.0, state="fly", life=600):
        self.kind, self.x, self.y, self.owner = kind, x, y, owner
        self.vx, self.vy, self.vz, self.z = vx, vy, vz, z
        self.state, self.life, self.age = state, life, 0
        self.alt = 0.0
        self.seg = 0          # road height under it (views add it to z)


class ItemSystem:
    def __init__(self, world, karts, seed=None):
        self.world, self.karts = world, karts
        self.items = []
        self.crates = world.crates
        self.rng = random.Random(seed)
        self.events = []        # (sound, kart) for the scene

    def roll(self, rank):
        return self.rng.choices(ITEM_ORDER, ITEM_WEIGHTS[min(rank, 5)])[0]

    def update(self, ranks):
        """ranks: kart -> 0-based position."""
        w = self.world
        for c in self.crates:
            c.update()
        for k in self.karts:
            if k.magnet:                                    # pull crates and dropped items in
                for c in self.crates:
                    if c.active and abs(c.x - k.x) < 90 and abs(c.y - k.y) < 90:
                        c.x += (k.x - c.x) * 0.12
                        c.y += (k.y - c.y) * 0.12
                for it in self.items:
                    if it.state == "ground" and abs(it.x - k.x) < 90 and abs(it.y - k.y) < 90:
                        it.x += (k.x - it.x) * 0.15
                        it.y += (k.y - it.y) * 0.15
                        if abs(it.x - k.x) < 12 and abs(it.y - k.y) < 12:
                            it.life = 0                     # sucked up harmlessly
                            k.events.append("pickup")
            if k.item is None and not k.item_lock and k.finished is None:
                for c in self.crates:
                    if c.active and abs(c.x - k.x) < 12 and abs(c.y - k.y) < 12:
                        c.take()
                        k.item = self.roll(ranks.get(k, 5))
                        k.item_lock = 20
                        k.events.append("pickup")
                        break
            if k.fire:
                if k.item and not k.spin and k.finished is None:
                    self.fire(k, k.item, k.fire_back)
                    k.item = None
                k.fire = False
        for it in self.items:
            self.move(it)
        self.items = [it for it in self.items if it.life > 0]

    def fire(self, kart, kind, back):
        dx, dy = kart.dir
        sp = max(kart.speed, 0.0)
        bx, by = kart.x - dx * 18, kart.y - dy * 18
        fx, fy = kart.x + dx * 14, kart.y + dy * 14
        if kind == "pepper":
            kart.pepper = 150
            kart.events.append("sizzle")
            return
        if kind == "shield":
            kart.shield = 480
            kart.events.append("shield")
            return
        if kind == "pogo":
            kart.pogo()
            return
        if kind == "magnet":
            kart.magnet = 240
            kart.events.append("hum")
            return
        if kind == "gum" or (kind == "banana" and back):
            it = Item(kind, bx, by, kart, state="ground", life=1800)
            it.alt = kart.alt
            self.items.append(it)
            kart.events.append("drop")
            return
        if back:
            vx, vy = -dx * 3.5, -dy * 3.5
            x, y = bx, by
        else:
            x, y = fx, fy
            vx, vy = dx * (sp + 4.0), dy * (sp + 4.0)
        if kind == "chicken":
            it = Item(kind, x, y, kart, vx, vy, 0.0, z=4.0, life=150)
        elif kind == "banana":
            it = Item(kind, x, y, kart, vx, vy, 2.4, life=1800)
        elif kind == "pie":
            it = Item(kind, x, y, kart, vx, vy, 1.9, life=400)
        else:                                               # balloon
            it = Item(kind, x, y, kart, vx, vy, 2.6, life=400)
        it.alt = kart.alt
        self.items.append(it)
        kart.events.append("throw" if kind != "chicken" else "squawk")

    def move(self, it):
        it.age += 1
        it.life -= 1
        w = self.world
        if it.state == "fx":
            return
        if it.state == "fly":
            if it.kind == "chicken":                        # flies level, homes on the nearest kart ahead
                target, best = None, 1e9
                for k in self.karts:
                    if k is it.owner:
                        continue
                    dx, dy = k.x - it.x, k.y - it.y
                    d = dx * dx + dy * dy
                    sp = math.hypot(it.vx, it.vy) or 1
                    if d < best and d < 160 * 160 and (dx * it.vx + dy * it.vy) / (math.sqrt(d) * sp + 1e-6) > 0.5:
                        target, best = k, d
                if target is not None:
                    sp = math.hypot(it.vx, it.vy)
                    d = math.sqrt(best) or 1
                    it.vx += (target.x - it.x) / d * 0.35
                    it.vy += (target.y - it.y) / d * 0.35
                    s2 = math.hypot(it.vx, it.vy) or 1
                    it.vx, it.vy = it.vx / s2 * sp, it.vy / s2 * sp
                it.z = 4.0 + math.sin(it.age * 0.5) * 1.5
            else:
                it.vz -= GRAVITY
                it.z += it.vz
            it.x += it.vx
            it.y += it.vy
            if w.surface_at(it.x, it.y) == 3:               # hit a wall
                it.x -= it.vx
                it.y -= it.vy
                it.vx = it.vy = 0.0
                if it.kind == "chicken":
                    it.life = 0
            if it.age == 1:
                it.seg, _ = w.nearest(it.x, it.y, it.owner.seg, w.n // 2)
            else:
                it.seg = w.nearest_index(it.x, it.y, it.seg, 3)
            it.alt = w.height_at(it.seg)
            if it.kind != "chicken" and it.z <= 0:          # landed
                it.z = 0.0
                if it.kind == "banana":
                    it.state, it.vx, it.vy = "ground", 0.0, 0.0
                elif it.kind == "balloon":
                    self.splash(it)
                else:                                       # pie: splat on the road, harmless
                    it.kind, it.state, it.life = "splat", "fx", 40
                return
        # collisions with karts
        for k in self.karts:
            if k is it.owner and it.age < 25 and it.state == "fly":
                continue
            if abs(k.x - it.x) < 11 and abs(k.y - it.y) < 11 and abs(k.z - it.z) < 7 and not k.spin:
                self.hit(it, k)
                return

    def hit(self, it, kart):
        kind = it.kind
        if kart.shield:                                     # the bubble takes it
            kart.pop_shield()
            if kind == "balloon":
                it.kind, it.state, it.life, it.z = "splash", "fx", 24, 0.0
            else:
                it.life = 0
            return
        if kind == "banana":
            kart.spin_out(40, "slip")
        elif kind == "chicken":
            kart.spin_out(30, "squawk")
            kart.speed = -0.5
        elif kind == "pie":
            kart.spin_out(20, "splat")
            kart.pie = 120
        elif kind == "gum":
            kart.stick(60)
        elif kind == "balloon":
            self.splash(it)
            return
        it.life = 0

    def splash(self, it):
        for k in self.karts:
            if abs(k.x - it.x) < 70 and abs(k.y - it.y) < 70:
                if k.shield:
                    k.pop_shield()
                else:
                    k.soak(90)
                k.events.append("splash")
        it.kind, it.state, it.life, it.z = "splash", "fx", 24, 0.0
