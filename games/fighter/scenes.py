"""Title, character select, controls and the fight itself."""
import math
import random

import pygame

from engine import text
from engine.app import Scene
from engine.input import NEUTRAL

from .ai import AI, LEVELS
from .audience import Audience
from .data import ROSTER
from .fighter import GROUND_Y, HEIGHT, STAGE_LEFT, STAGE_RIGHT, WIDTH, Fighter, Projectile

WHITE = (255, 255, 255)
YELLOW = (255, 220, 60)
RED = (230, 60, 50)
P_COLORS = ((235, 70, 60), (60, 140, 255))
ROUND_TIME = 99
WINS_NEEDED = 2

_stage_back = None
_stage = None


def stage():
    """Background with a still crowd, for the menus."""
    global _stage
    if _stage is None:
        _stage = stage_back().copy()
        Audience().draw(_stage)
    return _stage


def stage_back():
    """Sky, city and floor, drawn once into a surface and blitted every frame."""
    global _stage_back
    if _stage_back is not None:
        return _stage_back
    surf = pygame.Surface((WIDTH, HEIGHT)).convert()
    horizon = 150
    top, mid, low = (24, 18, 54), (120, 50, 110), (250, 140, 90)
    for y in range(horizon):
        k = y / horizon
        a, b, kk = (top, mid, k / 0.6) if k < 0.6 else (mid, low, (k - 0.6) / 0.4)
        surf.fill(tuple(int(a[i] + (b[i] - a[i]) * kk) for i in range(3)), (0, y, WIDTH, 1))
    rng = random.Random(7)
    for _ in range(40):  # stars
        surf.set_at((rng.randrange(WIDTH), rng.randrange(70)), (200, 190, 230))
    sun = (282, 112)
    pygame.draw.circle(surf, (255, 200, 110), sun, 30)
    for i, y in enumerate(range(sun[1] + 4, sun[1] + 30, 5)):  # retro sun stripes
        surf.fill(mid, (sun[0] - 32, y, 64, 1 + i // 2))
    pygame.draw.polygon(surf, (70, 35, 85), [(0, horizon), (0, 118), (60, 96), (120, 124), (180, 100),
                                             (250, 128), (320, 104), (384, 120), (384, horizon)])
    x = 0
    while x < WIDTH:  # city silhouette with lit windows
        w, h = rng.randint(14, 30), rng.randint(16, 44)
        pygame.draw.rect(surf, (36, 22, 48), (x, horizon - h, w, h))
        for wy in range(horizon - h + 4, horizon - 4, 6):
            for wx in range(x + 3, x + w - 3, 5):
                if rng.random() < 0.3:
                    surf.fill((255, 210, 120), (wx, wy, 2, 2))
        x += w + rng.randint(0, 6)
    surf.fill((62, 44, 62), (0, horizon, WIDTH, HEIGHT - horizon))
    for i in range(9):  # perspective floor lines
        y = horizon + int((HEIGHT - horizon) * (i / 8) ** 1.8)
        surf.fill((84, 60, 80), (0, y, WIDTH, 1))
    for i in range(-12, 13):
        pygame.draw.line(surf, (84, 60, 80), (WIDTH / 2 + i * 14, horizon), (WIDTH / 2 + i * 70, HEIGHT))
    surf.fill((30, 22, 34), (0, GROUND_Y + 3, WIDTH, 1))
    _stage_back = surf
    return surf


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

    def draw(self, surf, labels=None, blink=0):
        for i, item in enumerate(labels or self.items):
            sel = i == self.index
            color = YELLOW if sel else (200, 200, 220)
            y = self.y + i * self.gap
            text.draw(surf, item, self.size, color, (WIDTH // 2, y))
            if sel and (blink // 15) % 2 == 0:
                w = text.render(item, self.size, color).get_width()
                text.draw(surf, ">", self.size, color, (WIDTH // 2 - w // 2 - 10, y))


def darken(surf, alpha=140):
    shade = pygame.Surface((WIDTH, HEIGHT))
    shade.set_alpha(alpha)
    surf.blit(shade, (0, 0))


# ---------------------------------------------------------------------- title
class TitleScene(Scene):
    ITEMS = ["VS CPU", "VS PLAYER", "CPU LEVEL", "CONTROLS", "QUIT"]

    def __init__(self, app):
        super().__init__(app)
        self.menu = Menu(self.ITEMS, 112)
        self.t = 0
        self.idle = 0
        self.preview = [Fighter(ROSTER[0], 70, 1), Fighter(ROSTER[1], WIDTH - 70, -1)]
        self.crowd = Audience()

    def update(self):
        inp = self.app.input.any
        self.t += 1
        self.crowd.update()
        self.idle = 0 if inp.pressed or inp.held else self.idle + 1
        for f in self.preview:
            f.anim += 1
        level = self.app.settings["cpu_level"]
        if self.menu.index == 2:
            if "left" in inp.pressed:
                self.app.settings["cpu_level"] = max(0, level - 1)
                self.app.play("select")
            elif "right" in inp.pressed:
                self.app.settings["cpu_level"] = min(2, level + 1)
                self.app.play("select")
        choice = self.menu.update(self.app, inp)
        if choice == 0:
            self.app.switch(SelectScene(self.app, vs_cpu=True))
        elif choice == 1:
            self.app.switch(SelectScene(self.app, vs_cpu=False))
        elif choice == 2:
            self.app.settings["cpu_level"] = (level + 1) % 3
        elif choice == 3:
            self.app.switch(ControlsScene(self.app))
        elif choice == 4:
            self.app.quit()
        if self.idle > 60 * 20:
            self.app.switch(FightScene.demo(self.app))

    def draw(self, surf):
        surf.blit(stage_back(), (0, 0))
        self.crowd.draw(surf)
        for f in self.preview:
            f.draw_shadow(surf)
            f.draw(surf)
        bounce = round(math.sin(self.t * 0.05) * 2)
        text.draw(surf, "PI BRAWL", 64, (40, 20, 60), (WIDTH // 2 + 3, 22 + bounce + 3), shadow=None)
        text.draw(surf, "PI BRAWL", 64, YELLOW, (WIDTH // 2, 22 + bounce), shadow=RED)
        text.draw(surf, "a Raspberry Pi fighting game", 14, (230, 220, 255), (WIDTH // 2, 76))
        labels = list(self.ITEMS)
        labels[2] = "CPU LEVEL: < %s >" % LEVELS[self.app.settings["cpu_level"]]["name"]
        self.menu.draw(surf, labels, self.t)
        text.draw(surf, "F11 fullscreen   F3 fps", 12, (180, 170, 200), (WIDTH // 2, HEIGHT - 12))


class ControlsScene(Scene):
    LINES = [
        ("", "PLAYER 1", "PLAYER 2"),
        ("Move / jump / crouch", "W A S D", "Arrow keys"),
        ("Punch (P)", "F", "K  or  Num1"),
        ("Kick (K)", "G", "L  or  Num2"),
        ("Pause", "Esc", "Enter"),
        ("Gamepad", "1st pad: A/X = P", "2nd pad: B/Y = K"),
    ]

    def update(self):
        if self.app.input.any.pressed & {"a", "b", "start"}:
            self.app.play("confirm")
            self.app.switch(TitleScene(self.app))

    def draw(self, surf):
        surf.blit(stage(), (0, 0))
        darken(surf, 170)
        text.draw(surf, "CONTROLS", 28, YELLOW, (WIDTH // 2, 8))
        for i, (a, b, c) in enumerate(self.LINES):
            y = 38 + i * 15
            col = YELLOW if i == 0 else WHITE
            text.draw(surf, a, 14, col, (12, y), align="left")
            text.draw(surf, b, 14, col, (210, y))
            text.draw(surf, c, 14, col, (316, y))
        tips = [
            "Hold BACK to block. Hold DOWN-BACK to block sweeps and waves.",
            "Jump attacks must be blocked standing.",
            "Specials: roll the stick, then press the button, e.g. D, DF, F + P.",
            "Hit with a Punch, then roll a special to combo into it.",
            "Keep P held after D, DF, F to charge Kaze's orb. Best of 3 rounds.",
        ]
        for i, line in enumerate(tips):
            text.draw(surf, line, 13, (210, 210, 230), (WIDTH // 2, 136 + i * 13))
        text.draw(surf, "press P to go back", 12, YELLOW, (WIDTH // 2, HEIGHT - 12))


# ---------------------------------------------------------------------- select
class SelectScene(Scene):
    def __init__(self, app, vs_cpu):
        super().__init__(app)
        self.vs_cpu = vs_cpu
        self.cursor = [0, 1 % len(ROSTER)]
        self.done = [False, False]
        self.t = 0
        self.ready_t = 0
        n = len(ROSTER)
        self.card_w = 150
        self.card_x = [WIDTH // 2 - (n * self.card_w + (n - 1) * 12) // 2 + i * (self.card_w + 12) for i in range(n)]
        self.previews = [Fighter(c, self.card_x[i] + self.card_w // 2, 1 if i == 0 else -1)
                         for i, c in enumerate(ROSTER)]

    def update(self):
        self.t += 1
        for f in self.previews:
            f.anim += 1
        if all(self.done):
            self.ready_t += 1
            if self.ready_t > 40:
                chars = [ROSTER[i] for i in self.cursor]
                self.app.switch(FightScene(self.app, chars, cpu=(False, self.vs_cpu)))
            return
        if self.vs_cpu:
            slot = 0 if not self.done[0] else 1
            self._control(slot, self.app.input.any)
        else:
            for slot in (0, 1):
                self._control(slot, self.app.input.players[slot])

    def _control(self, slot, inp):
        if "b" in inp.pressed:
            self.app.play("select")
            if self.done[slot]:
                self.done[slot] = False
            elif self.vs_cpu and slot == 1:
                self.done[0] = False
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
        elif inp.pressed & {"a", "start"}:
            self.done[slot] = True
            self.app.play("confirm")

    def draw(self, surf):
        surf.blit(stage(), (0, 0))
        darken(surf, 120)
        text.draw(surf, "CHOOSE YOUR FIGHTER", 22, YELLOW, (WIDTH // 2, 5))
        top, h = 24, 120
        for i, char in enumerate(ROSTER):
            x = self.card_x[i]
            pygame.draw.rect(surf, (30, 24, 50), (x, top, self.card_w, h))
            pygame.draw.rect(surf, (90, 80, 130), (x, top, self.card_w, h), 1)
            text.draw(surf, char.name, 20, WHITE, (x + self.card_w // 2, top + 4))
            text.draw(surf, char.title, 13, (200, 190, 230), (x + self.card_w // 2, top + 19))
            f = self.previews[i]
            f.draw(surf, 0, (top + h - 8) - GROUND_Y)
            for j, (label, val) in enumerate((("POW", char.power), ("SPD", char.speed))):
                yy = top + 36 + j * 10
                text.draw(surf, label, 12, (200, 200, 220), (x + 6, yy), align="left")
                for k in range(5):
                    c = YELLOW if k < val else (70, 60, 90)
                    surf.fill(c, (x + 30 + k * 7, yy + 2, 5, 5))
        for slot in (1, 0):
            i = self.cursor[slot]
            x = self.card_x[i]
            inset = 2 + slot * 3
            col = P_COLORS[slot] if not self.done[slot] or (self.t // 4) % 2 else WHITE
            pygame.draw.rect(surf, col, (x - inset, top - inset, self.card_w + inset * 2, h + inset * 2), 2)
            label = ("CPU" if self.vs_cpu and slot == 1 else "%dP" % (slot + 1))
            lx = x + 6 if slot == 0 else x + self.card_w - 6
            text.draw(surf, label, 16, P_COLORS[slot], (lx, top + h - 16), align="left" if slot == 0 else "right")
        for slot in (0, 1):  # move list for each player's highlighted character
            char = ROSTER[self.cursor[slot]]
            x0 = 10 if slot == 0 else WIDTH // 2 + 6
            y = 150
            for j, sp in enumerate(char.specials):
                text.draw(surf, "%s: %s" % (sp.name, sp.notation), 13, WHITE, (x0, y + 2 + j * 12), align="left")
        if self.vs_cpu and self.done[0] and not self.done[1]:
            msg = "Now pick the CPU's fighter"
        elif all(self.done):
            msg = "GET READY!"
        else:
            msg = "LEFT/RIGHT choose   P confirm   K back"
        text.draw(surf, msg, 14, YELLOW, (WIDTH // 2, HEIGHT - 16))


# ---------------------------------------------------------------------- fight
class Spark:
    def __init__(self, x, y, kind):
        self.x, self.y, self.kind, self.t = x, y, kind, 0
        self.life = 10 if kind != "dust" else 14

    def draw(self, surf, ox, oy):
        k = self.t / self.life
        x, y = self.x + ox, self.y + oy
        if self.kind == "dust":
            for d in (-1, 1):
                pygame.draw.circle(surf, (150, 130, 140), (x + d * (6 + 14 * k), y - 3 - 4 * k), max(1, 5 - 4 * k))
            return
        color = (120, 200, 255) if self.kind == "block" else ((255, 240, 120) if k < 0.5 else (255, 140, 40))
        r = 4 + 12 * k if self.kind != "block" else 4 + 6 * k
        for i in range(8):
            a = i * math.pi / 4 + 0.3
            pygame.draw.line(surf, color, (x + math.cos(a) * r * 0.4, y + math.sin(a) * r * 0.4),
                             (x + math.cos(a) * r, y + math.sin(a) * r), 2)


class FightScene(Scene):
    def __init__(self, app, chars, cpu=(False, True), demo=False, seed=None):
        super().__init__(app)
        self.chars = chars
        self.cpu = cpu
        self.demo = demo
        level = app.settings.get("cpu_level", 1)
        rng = random.Random(seed)
        self.ai = [AI(level if not demo else 1, rng.random()) if cpu[i] else None for i in (0, 1)]
        alt = chars[0] is chars[1]
        self.fighters = [Fighter(chars[0], 0, 1), Fighter(chars[1], 0, -1, alt=alt)]
        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.crowd = Audience(app)
        self.round = 0
        self.stats = {"hits": 0, "blocks": 0, "specials": 0, "rounds": 0, "matches": 0}
        self.pause_menu = None
        self.end_menu = None
        self.start_round()

    @classmethod
    def demo(cls, app, seed=None):
        rng = random.Random(seed)
        return cls(app, [rng.choice(ROSTER), rng.choice(ROSTER)], cpu=(True, True), demo=True, seed=seed)

    def start_round(self):
        self.round += 1
        for i, f in enumerate(self.fighters):
            f.reset(WIDTH // 2 + (-60 if i == 0 else 60), 1 if i == 0 else -1)
        self.projectiles = []
        self.effects = []
        self.time = ROUND_TIME * 60
        self.hitstop = 0
        self.shake = 0
        self.combo = None   # (attacker index, hits, frames left)
        self.phase = "intro"
        self.phase_t = 0
        self.winner = None
        self.app.play("round")

    # -- helpers used by fighters -------------------------------------------
    def spawn_projectile(self, owner, move):
        p = Projectile(owner, move)
        owner.projectile = p
        self.projectiles.append(p)
        self.stats["specials"] += 1

    def dust(self, x):
        self.effects.append(Spark(x, GROUND_Y, "dust"))

    def other(self, f):
        return self.fighters[1] if f is self.fighters[0] else self.fighters[0]

    # -- update -----------------------------------------------------------
    def inputs(self):
        res = []
        for i, f in enumerate(self.fighters):
            if self.ai[i]:
                res.append(self.ai[i].think(f, self.other(f), self))
            elif any(self.cpu):
                res.append(self.app.input.any)
            else:
                res.append(self.app.input.players[i])
        return res

    def human_inputs(self):
        if self.demo:
            return [self.app.input.any]
        return [self.app.input.any] if any(self.cpu) else self.app.input.players

    def update(self):
        if self.demo and self.app.input.any.pressed:
            self.app.switch(TitleScene(self.app))
            return
        if self.pause_menu:
            return self._update_pause()
        if self.end_menu:
            return self._update_end()
        if not self.demo and self.phase in ("intro", "fight") and \
                any("start" in inp.pressed for inp in self.human_inputs()):
            self.pause_menu = Menu(["RESUME", "CHARACTER SELECT", "TITLE", "QUIT"], 92)
            return

        self.phase_t += 1
        self.crowd.update()
        self.crowd.danger = any(0 < f.health < f.char.health * 0.25 for f in self.fighters)
        live = self.phase == "fight"
        inputs = self.inputs() if live else [NEUTRAL, NEUTRAL]
        if self.phase == "intro" and self.phase_t > 100:
            self.phase, self.phase_t = "fight", 0
            self.crowd.react("round")
        elif self.phase == "ko":
            if self.phase_t > 60 and self.phase_t % 2 == 0 and self.phase_t < 120:
                return  # slow motion after a KO
            if self.phase_t > 170:
                self._end_round()
        elif self.phase == "timeup" and self.phase_t > 120:
            self._end_round()
        elif self.phase == "roundover" and self.phase_t > 90:
            self._after_round()
            return

        self.step(inputs)

        if live:
            self.time -= 1
            if any(f.health <= 0 for f in self.fighters):
                self.phase, self.phase_t = "ko", 0
                self.app.play("ko")
                self.shake = 12
                self.crowd.react("ko")
            elif self.time <= 0:
                self.phase, self.phase_t = "timeup", 0
        if self.phase in ("ko", "timeup", "roundover"):
            for f in self.fighters:
                if f.health > 0 and f.state in ("idle", "walk", "crouch") and self.phase_t > 60:
                    f.state = "win" if self._leader() is f else "idle"

    def step(self, inputs):
        a, b = self.fighters
        for f, inp in zip(self.fighters, inputs):
            f.read_input(inp)
        if self.hitstop:
            self.hitstop -= 1
            return
        a.threatened, b.threatened = b.threatens(a), a.threatens(b)
        a.update(b, self)
        b.update(a, self)
        for p in self.projectiles:
            p.update()
        self.collide()
        self.push_apart()
        for p in self.projectiles:
            if p.dead and p.owner.projectile is p:
                p.owner.projectile = None
        self.projectiles = [p for p in self.projectiles if not p.dead]
        for e in self.effects:
            e.t += 1
        self.effects = [e for e in self.effects if e.t < e.life]
        for f in self.fighters:
            if f.red_health > f.health and f.state not in ("hitstun",):
                f.red_health = max(f.health, f.red_health - 4)
        if self.combo:
            i, n, left = self.combo
            self.combo = (i, n, left - 1) if left > 1 else None
        if self.shake:
            self.shake -= 1

    def collide(self):
        hits = []
        for att, dfn in ((self.fighters[0], self.fighters[1]), (self.fighters[1], self.fighters[0])):
            if att.state == "attack" and att.can_hit():
                hb = att.hitbox()
                if hb:
                    for hurt in dfn.hurtboxes():
                        if hb.colliderect(hurt):
                            hits.append((att, dfn, att.move, hb.clip(hurt).center, False))
                            break
        for p in self.projectiles:
            if p.dead:
                continue
            for q in self.projectiles:
                if q is not p and q.owner is not p.owner and not q.dead and p.rect().colliderect(q.rect()):
                    p.dead = q.dead = True
                    self.effects.append(Spark((p.x + q.x) / 2, GROUND_Y - p.y, "hit"))
                    self.app.play("block")
            if not p.can_hit():
                continue
            dfn = self.other(p.owner)
            r = p.rect()
            for hurt in dfn.hurtboxes():
                if r.colliderect(hurt):
                    hits.append((p.owner, dfn, p.move, r.clip(hurt).center, p))
                    break
        for hit in hits:
            self.resolve(*hit)

    def resolve(self, att, dfn, move, point, is_proj):
        sign = 1 if dfn.x >= att.x else -1
        if is_proj:
            sign = 1 if is_proj.vx > 0 else -1
            hit_no, last = is_proj.hits_done, is_proj.hits_left <= 1
            is_proj.connected()
        else:
            att.move_contact = True
            hit_no, last = att.hits_done, att.hits_done + 1 >= move.hits
            att.hits_done += 1
            att.rehit_at = att.t + move.rehit
        if dfn.can_block(move.level):
            dfn.enter_stun("blockstun", move.blockstun, sign * move.push)
            dfn.health -= move.chip
            self.hitstop = max(self.hitstop, 5)
            self.effects.append(Spark(point[0], point[1], "block"))
            self.app.play("block")
            self.stats["blocks"] += 1
        else:
            scale = max(0.4, 1 - 0.12 * dfn.combo_taken)
            dfn.health -= int(move.damage_for(hit_no) * scale)
            dfn.combo_taken += 1
            if dfn.combo_taken >= 2:
                self.combo = (self.fighters.index(att), dfn.combo_taken, 70)
            if dfn.health <= 0:
                dfn.knock(sign, (2.5, 5.5), ko=True)
            elif (move.knockdown and last) or dfn.airborne:
                dfn.knock(sign, move.launch)
            else:
                dfn.enter_stun("hitstun", move.hitstun, sign * move.push)
                if move.followup and not is_proj:
                    att.followup = att.moves[move.followup]
            if move.special and move.knockdown and last:
                self.crowd.react("big", point[0])
            elif move.special or dfn.combo_taken >= 3:
                self.crowd.react("wave", point[0])
            else:
                self.crowd.react("hit", point[0])
            self.hitstop = max(self.hitstop, move.hitstop)
            self.effects.append(Spark(point[0], point[1], "hit"))
            self.app.play(move.sfx)
            if move.sfx == "heavy":
                self.shake = max(self.shake, 6)
            self.stats["hits"] += 1
        if dfn.health <= 0 and dfn.state != "ko":
            dfn.health = 0
            dfn.knock(sign, (2.5, 5.5), ko=True)
        dfn.health = max(0, dfn.health)
        # pinned against the wall: the attacker gets pushed back instead
        if not is_proj and (dfn.x <= STAGE_LEFT + 1 or dfn.x >= STAGE_RIGHT - 1):
            att.recoil = -sign * move.push

    def push_apart(self):
        a, b = self.fighters
        if abs(a.y - b.y) > 40 or a.state in ("knockdown", "ko") and a.landed and b.airborne:
            return
        width = 11 * (a.s + b.s)
        dx = b.x - a.x
        if abs(dx) >= width:
            return
        side = 1 if dx > 0 or (dx == 0 and a.facing > 0) else -1
        overlap = width - abs(dx)
        a.x -= side * overlap / 2
        b.x += side * overlap / 2
        for f, g in ((a, b), (b, a)):  # if one is pinned to a wall, shove the other
            if f.x < STAGE_LEFT:
                g.x += STAGE_LEFT - f.x
                f.x = STAGE_LEFT
            elif f.x > STAGE_RIGHT:
                g.x -= f.x - STAGE_RIGHT
                f.x = STAGE_RIGHT

    def _leader(self):
        a, b = self.fighters
        ra, rb = a.health / a.char.health, b.health / b.char.health
        if a.health <= 0 and b.health <= 0 or ra == rb:
            return None
        return a if ra > rb else b

    def _end_round(self):
        self.winner = self._leader()
        if self.winner is None:
            for f in self.fighters:
                f.wins += 1
        else:
            self.winner.wins += 1
        self.stats["rounds"] += 1
        self.phase, self.phase_t = "roundover", 0

    def _after_round(self):
        a, b = self.fighters
        if a.wins >= WINS_NEEDED or b.wins >= WINS_NEEDED:
            self.stats["matches"] += 1
            if self.demo:
                self.app.switch(FightScene.demo(self.app) if self.app.settings.get("demo_loop", True)
                                else TitleScene(self.app))
                return
            self.phase, self.phase_t = "matchover", 0
            self.end_menu = Menu(["REMATCH", "CHARACTER SELECT", "TITLE", "QUIT"], 112)
        else:
            self.start_round()

    def _update_pause(self):
        for inp in self.human_inputs():
            if "start" in inp.pressed or "b" in inp.pressed:
                self.pause_menu = None
                return
            choice = self.pause_menu.update(self.app, inp)
            if choice is not None:
                self._menu_choice(choice, resume=True)
                return

    def _update_end(self):
        self.phase_t += 1
        for f in self.fighters:
            f.anim += 1
        for inp in self.human_inputs():
            choice = self.end_menu.update(self.app, inp)
            if choice is not None:
                self._menu_choice(choice)
                return

    def _menu_choice(self, choice, resume=False):
        if choice == 0:
            if resume:
                self.pause_menu = None
            else:
                self.app.switch(FightScene(self.app, self.chars, self.cpu))
        elif choice == 1:
            self.app.switch(SelectScene(self.app, vs_cpu=any(self.cpu)))
        elif choice == 2:
            self.app.switch(TitleScene(self.app))
        else:
            self.app.quit()

    # -- draw -------------------------------------------------------------
    def draw(self, surf):
        c = self.canvas
        c.blit(stage_back(), (0, 0))
        self.crowd.draw(c)
        for f in self.fighters:
            f.draw_shadow(c)
        a, b = self.fighters
        order = (b, a) if a.state == "attack" else (a, b)
        for f in order:
            f.draw(c)
        for p in self.projectiles:
            p.draw(c)
        for e in self.effects:
            e.draw(c, 0, 0)
        if self.shake:
            surf.fill((0, 0, 0))
            surf.blit(c, ((self.shake % 4) - 2, (self.shake % 3) - 1))
        else:
            surf.blit(c, (0, 0))
        self.draw_hud(surf)

    def draw_hud(self, surf):
        bar_w, bar_h, y = 158, 9, 8
        for i, f in enumerate(self.fighters):
            x = 10 if i == 0 else WIDTH - 10 - bar_w
            surf.fill((20, 16, 30), (x - 2, y - 2, bar_w + 4, bar_h + 4))
            surf.fill((70, 20, 30), (x, y, bar_w, bar_h))
            red = int(bar_w * f.red_health / f.char.health)
            cur = int(bar_w * max(0, f.health) / f.char.health)
            low = f.health < f.char.health * 0.25
            color = (240, 70, 50) if low and (self.phase_t // 8) % 2 else YELLOW
            if i == 0:  # bars drain towards the outside edge
                surf.fill((220, 40, 40), (x + bar_w - red, y, red, bar_h))
                surf.fill(color, (x + bar_w - cur, y, cur, bar_h))
            else:
                surf.fill((220, 40, 40), (x, y, red, bar_h))
                surf.fill(color, (x, y, cur, bar_h))
            name_x, align = (x, "left") if i == 0 else (x + bar_w, "right")
            label = f.char.name + (" (CPU)" if self.cpu[i] else "")
            text.draw(surf, label, 14, WHITE, (name_x, y + bar_h + 3), align=align)
            for w in range(WINS_NEEDED):
                px = x + bar_w - 6 - w * 9 if i == 0 else x + 6 + w * 9
                pygame.draw.circle(surf, YELLOW if f.wins > w else (60, 50, 70), (px, y + bar_h + 9), 3)
        secs = max(0, math.ceil(self.time / 60))
        text.draw(surf, "%02d" % secs, 26, WHITE if secs > 10 else RED, (WIDTH // 2, 4))

        if self.combo:
            i, n, _ = self.combo
            x, align = (12, "left") if i == 0 else (WIDTH - 12, "right")
            text.draw(surf, "%d HITS!" % n, 20, YELLOW, (x, 42), align=align, shadow=RED)

        cy = 70
        if self.phase == "intro":
            msg = "ROUND %d" % self.round if self.phase_t < 60 else "FIGHT!"
            text.draw(surf, msg, 40, YELLOW, (WIDTH // 2, cy), shadow=RED)
        elif self.phase == "ko" and self.phase_t < 120:
            text.draw(surf, "K.O.", 56, RED, (WIDTH // 2, cy - 6), shadow=(40, 0, 0))
        elif self.phase == "timeup":
            text.draw(surf, "TIME!", 44, YELLOW, (WIDTH // 2, cy), shadow=RED)
        elif self.phase in ("roundover", "matchover") or (self.phase == "ko" and self.phase_t >= 120):
            w = self.winner if self.phase != "ko" else self._leader()
            if self.phase == "matchover":
                a, b = self.fighters
                w = a if a.wins > b.wins else b if b.wins > a.wins else None
                text.draw(surf, ("%s WINS THE MATCH!" % w.char.name) if w else "DRAW GAME", 30, YELLOW,
                          (WIDTH // 2, 62), shadow=RED)
            else:
                text.draw(surf, ("%s WINS" % w.char.name) if w else "DRAW", 36, YELLOW, (WIDTH // 2, cy),
                          shadow=RED)
        if self.end_menu:
            self.end_menu.draw(surf, blink=self.phase_t)
        if self.pause_menu:
            darken(surf, 150)
            text.draw(surf, "PAUSED", 36, YELLOW, (WIDTH // 2, 56), shadow=RED)
            self.pause_menu.draw(surf, blink=pygame.time.get_ticks() // 16)
        if self.demo and (pygame.time.get_ticks() // 600) % 2:
            text.draw(surf, "DEMO - PRESS ANY BUTTON", 16, WHITE, (WIDTH // 2, HEIGHT - 16))
