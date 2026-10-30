"""CPU opponent. It drives a fighter through a VirtualInput, exactly like a
player would, so it has to perform real motions to throw specials."""
import random
from collections import deque

from engine.input import VirtualInput

LEVELS = {
    # reaction frames, block chance, anti-air chance, combo chance
    0: dict(name="EASY", react=(20, 34), block=0.2, anti_air=0.15, combo=0.1),
    1: dict(name="NORMAL", react=(10, 20), block=0.5, anti_air=0.45, combo=0.4),
    2: dict(name="HARD", react=(5, 11), block=0.75, anti_air=0.75, combo=0.75),
}


class AI:
    def __init__(self, level=1, seed=None):
        self.cfg = LEVELS[level]
        self.rng = random.Random(seed)
        self.input = VirtualInput()
        self.script = deque()
        self.hold = frozenset()
        self.wait = 0

    def think(self, me, opp, match):
        if self.script:
            held, pressed = self.script.popleft()
        else:
            self.wait -= 1
            if self.wait <= 0 and me.state in ("idle", "walk", "crouch", "land", "jump", "blockstun"):
                self.decide(me, opp, match)
            if self.script:
                held, pressed = self.script.popleft()
            else:
                held, pressed = self.hold, ()
        self.input.set(held, pressed)
        return self.input

    # -- helpers -------------------------------------------------------
    @staticmethod
    def keys(d, facing):
        """Numpad direction relative to facing -> set of absolute actions."""
        held = set()
        x = (d - 1) % 3 - 1
        if x:
            held.add("right" if x * facing > 0 else "left")
        if d >= 7:
            held.add("up")
        elif d <= 3:
            held.add("down")
        return held

    def motion(self, dirs, button, facing):
        for d in dirs:
            self.script.extend([(self.keys(d, facing), ())] * 2)
        last = self.keys(dirs[-1], facing)
        self.script.append((last, (button,)))

    def press(self, d, button, facing, after=0):
        self.script.extend([(self.keys(d, facing), ())] * after)
        self.script.append((self.keys(d, facing), (button,)))

    def special(self, me, key):
        for sp in me.char.specials:
            if sp.key == key:
                return sp
        return None

    def projectile_special(self, me):
        for sp in me.char.specials:
            if me.moves[sp.key].projectile:
                return sp
        return None

    # -- decisions -----------------------------------------------------
    def decide(self, me, opp, match):
        r, cfg, f = self.rng, self.cfg, me.facing
        self.wait = r.randint(*cfg["react"])
        self.hold = frozenset()
        dist = abs(opp.x - me.x)
        roll = r.random()

        incoming = [p for p in match.projectiles
                    if p.owner is opp and (me.x - p.x) * p.vx > 0 and abs(p.x - me.x) < 140]
        if incoming:
            if roll < 0.3 and abs(incoming[0].x - me.x) > 50:
                self.script.extend([(self.keys(9, f), ())] * 3)
            elif roll < 0.3 + cfg["block"]:
                self.hold = frozenset(self.keys(1 if incoming[0].move.level == "low" else 4, f))
                self.wait = 25
            return

        if opp.state == "attack" and dist < 100 and roll < cfg["block"]:
            m = opp.move
            low = m.level == "low"
            self.hold = frozenset(self.keys(1 if low or (m.crouch and m.level != "high") else 4, f))
            self.wait = 14
            return

        if opp.airborne and opp.state in ("jump", "attack") and dist < 85 and roll < cfg["anti_air"]:
            dp = self.special(me, "sp2")
            if dp and dp.motion[0] == 6:
                self.motion(dp.motion, dp.button, f)
            else:
                self.press(5, "b", f)
            return

        if me.state == "jump":
            if dist < 60 and not me.air_used:
                self.press(5, "b" if roll < 0.6 else "a", f)
            return

        proj = self.projectile_special(me)
        can_throw = proj and me.projectile is None
        if dist > 150:
            if can_throw and roll < 0.35:
                self.motion(proj.motion, proj.button, f)
            elif roll < 0.85:
                self.hold = frozenset(self.keys(6, f))
                self.wait = r.randint(15, 40)
            elif roll < 0.95:
                self.script.extend([(self.keys(9, f), ())] * 3)
        elif dist > 65:
            if roll < 0.4:
                self.hold = frozenset(self.keys(6, f))
                self.wait = r.randint(10, 25)
            elif roll < 0.6 and can_throw:
                self.motion(proj.motion, proj.button, f)
            elif roll < 0.75:
                self.script.extend([(self.keys(9, f), ())] * 3)
            elif roll < 0.85:
                self.hold = frozenset(self.keys(4, f))
                self.wait = r.randint(8, 18)
            else:
                rush = self.special(me, "sp2")
                if rush and me.moves["sp2"].drive and dist < 120:
                    self.motion(rush.motion, rush.button, f)
        else:
            if roll < 0.25:
                self.press(5, "a", f)
                if r.random() < cfg["combo"]:  # jab -> special cancel
                    sp = r.choice(me.char.specials)
                    self.script.extend([(set(), ())] * 3)
                    self.motion(sp.motion, sp.button, f)
            elif roll < 0.45:
                self.press(5, "b", f)
            elif roll < 0.62:
                self.press(2, "b", f, after=2)
            elif roll < 0.75:
                self.press(2, "a", f, after=2)
            elif roll < 0.87:
                self.hold = frozenset(self.keys(4, f))
                self.wait = r.randint(10, 20)
            else:
                self.hold = frozenset(self.keys(1, f))
                self.wait = r.randint(10, 20)
