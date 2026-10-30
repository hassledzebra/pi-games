"""The crowd behind the fence, the silver GX460 and the orange cat on its roof.

Everything is drawn once into small sprites at startup; each frame only blits
them with a vertical offset, which keeps it cheap on a Pi. The fight calls
react() and the crowd cheers, jumps and throws confetti:

    hit    people near the hit throw their arms up
    wave   (combo or special lands) a cheer ripples out from the hit
    big    (a special's finishing hit) everyone jumps, the cat ducks
    ko     jumping and confetti for a few seconds, cat stands, hazard lights blink
    round  short cheer at "FIGHT!"
"""
import math
import random

import pygame

from .art import OUTLINE, chain, seg

KEY = (255, 0, 255)
FENCE_TOP, FENCE_LEFT = 156, 100
CAR_X, CAR_Y = 6, 176            # car's left edge and wheel bottom
CAT_X, CAT_Y = 22, 135           # cat's feet on the roof
ROWS = ((152, 0.55, 104), (160, 0.8, 110))   # (feet y hidden behind the fence, brightness, first x)
SKINS = ((232, 190, 150), (196, 140, 100), (150, 100, 70), (240, 205, 175), (110, 75, 55))
HAIRS = ((30, 30, 40), (90, 55, 30), (200, 170, 90), (20, 20, 20), (150, 150, 150))
SHIRTS = ((200, 70, 60), (60, 120, 190), (230, 190, 60), (80, 160, 90), (150, 90, 170), (230, 230, 230),
          (40, 40, 50))
SILVER, SILVER_HI, SILVER_LO = (190, 194, 204), (232, 235, 242), (120, 124, 136)
CONFETTI = ((255, 220, 60), (230, 60, 50), (60, 140, 255), (80, 200, 120), (255, 255, 255))


def dim(c, k):
    return tuple(int(v * k) for v in c)


def sprite(w, h):
    s = pygame.Surface((w, h))
    s.fill(KEY)
    s.set_colorkey(KEY)
    return s


# ---------------------------------------------------------------------- one-off drawings
def draw_person(surf, x, yb, shirt, skin, hair, pose, sign):
    """A spectator from the waist up; the body runs on below `yb` so jumps never show a gap."""
    pygame.draw.rect(surf, shirt, (x - 4, yb - 10, 8, 18), border_top_left_radius=3, border_top_right_radius=3)
    if pose == "up":
        seg(surf, shirt, (x - 3, yb - 9), (x - 6, yb - 17), 2)
        seg(surf, shirt, (x + 3, yb - 9), (x + 6, yb - 17), 2)
        surf.fill(skin, (x - 7, yb - 19, 2, 2))
        surf.fill(skin, (x + 5, yb - 19, 2, 2))
    elif pose in ("sign", "sign_up"):
        lift = 5 if pose == "sign_up" else 0
        seg(surf, shirt, (x + 3, yb - 9), (x + 4, yb - 15 - lift), 2)
        surf.fill((245, 240, 225), (x + 1, yb - 23 - lift, 11, 7))
        surf.fill(sign, (x + 3, yb - 21 - lift, 7, 3))
    elif pose == "phone":
        seg(surf, shirt, (x + 3, yb - 9), (x + 4, yb - 14), 2)
        surf.fill((30, 30, 40), (x + 3, yb - 18, 3, 4))
    pygame.draw.circle(surf, skin, (x, yb - 14), 3)
    pygame.draw.circle(surf, hair, (x, yb - 15), 3, draw_top_left=True, draw_top_right=True)


def draw_gx460(surf, x0, yb):
    """Side view of a silver GX460-style SUV (no badges), front to the right, ~93 x 43 px."""
    body = [(x0 + 2, yb - 8), (x0 + 2, yb - 38), (x0 + 5, yb - 41), (x0 + 58, yb - 41), (x0 + 67, yb - 27),
            (x0 + 90, yb - 25), (x0 + 93, yb - 21), (x0 + 93, yb - 10), (x0 + 90, yb - 8)]
    pygame.draw.polygon(surf, OUTLINE, [(px + (1 if px > x0 + 40 else -1), py + (-1 if py < yb - 20 else 1))
                                        for px, py in body])
    pygame.draw.polygon(surf, SILVER, body)
    surf.fill(SILVER_LO, (x0 + 3, yb - 15, 89, 6))                      # lower body shade
    seg(surf, SILVER_HI, (x0 + 4, yb - 27), (x0 + 66, yb - 27), 1)     # belt line
    seg(surf, SILVER_HI, (x0 + 67, yb - 25), (x0 + 89, yb - 24), 1)    # hood line
    glass = (52, 62, 84)
    for a0, a1 in ((x0 + 6, x0 + 21), (x0 + 24, x0 + 40), (x0 + 43, x0 + 56)):
        pygame.draw.polygon(surf, glass, [(a0, yb - 38), (a1 if a1 < x0 + 50 else a1 - 1, yb - 38),
                                          (a1 + (7 if a1 > x0 + 50 else 0), yb - 29), (a0, yb - 29)])
    seg(surf, (110, 125, 150), (x0 + 45, yb - 37), (x0 + 50, yb - 31), 1)   # glare
    for px in (x0 + 22, x0 + 41):
        seg(surf, (30, 30, 36), (px, yb - 38), (px, yb - 10), 1)           # door seams
    seg(surf, (30, 30, 36), (x0 + 58, yb - 28), (x0 + 58, yb - 10), 1)
    seg(surf, (40, 40, 46), (x0 + 6, yb - 43), (x0 + 56, yb - 43), 1)       # roof rail
    for px in (x0 + 8, x0 + 30, x0 + 54):
        surf.fill((40, 40, 46), (px, yb - 42, 1, 1))
    surf.fill((40, 40, 46), (x0 + 57, yb - 31, 3, 3))                       # mirror
    for px in (x0 + 33, x0 + 52):
        surf.fill(SILVER_HI, (px, yb - 25, 3, 1))                           # handles
    surf.fill((30, 30, 36), (x0 - 1, yb - 33, 4, 22))                       # spare tyre on the rear door
    surf.fill((200, 40, 40), (x0 + 2, yb - 35, 2, 8))                       # tail lamp
    surf.fill((255, 245, 200), (x0 + 88, yb - 24, 5, 3))                    # head lamp
    surf.fill((60, 60, 70), (x0 + 90, yb - 19, 3, 6))                       # grille edge
    surf.fill((55, 55, 62), (x0 + 24, yb - 9, 38, 2))                       # running board
    for wx in (x0 + 18, x0 + 74):
        pygame.draw.circle(surf, (36, 36, 44), (wx, yb - 8), 10)            # arch
        pygame.draw.circle(surf, (24, 24, 28), (wx, yb - 7), 8)             # tyre
        pygame.draw.circle(surf, SILVER, (wx, yb - 7), 4)                   # rim
        for k in range(5):
            a = k * 2 * math.pi / 5
            seg(surf, SILVER_LO, (wx, yb - 7), (wx + math.cos(a) * 4, yb - 7 + math.sin(a) * 4), 1)
        surf.fill((60, 60, 70), (wx, yb - 7, 1, 1))


def draw_cat(surf, x, yb, pose="sit", tail=0.0, eyes=True, ears=True):
    """Orange tabby facing right, ~12 px tall sitting. pose: sit / duck / stand."""
    o, od, ol = (240, 140, 40), (190, 95, 25), (255, 190, 110)
    if pose == "duck":
        tail_pts = [(x - 5, yb - 1), (x - 9, yb - 1), (x - 11, yb - 2)]
        body, head = (x - 6, yb - 6, 13, 6), (x + 5, yb - 4)
    elif pose == "stand":
        tail_pts = [(x - 6, yb - 7), (x - 7, yb - 12), (x - 6, yb - 17), (x - 5, yb - 19)]
        body, head = (x - 7, yb - 10, 14, 7), (x + 6, yb - 10)
    else:
        tail_pts = [(x - 4, yb - 1), (x - 8, yb - 2), (x - 9 - tail, yb - 6), (x - 8 - tail, yb - 9)]
        body, head = (x - 5, yb - 9, 11, 10), (x + 2, yb - 11)
    chain(surf, OUTLINE, tail_pts, 4)
    chain(surf, o, tail_pts, 2)
    if pose == "stand":
        for lx in (x - 5, x - 2, x + 2, x + 5):
            seg(surf, OUTLINE, (lx, yb - 5), (lx, yb), 3)
            seg(surf, o, (lx, yb - 5), (lx, yb - 1), 1)
    pygame.draw.ellipse(surf, OUTLINE, body)
    pygame.draw.ellipse(surf, o, (body[0] + 1, body[1] + 1, body[2] - 2, body[3] - 2))
    if pose == "sit":
        surf.fill(ol, (x, yb - 6, 3, 5))                                    # chest
        surf.fill(od, (x - 2, yb - 6, 1, 1))
        surf.fill(od, (x - 2, yb - 4, 1, 1))                                # stripes
    else:
        for k in (-3, 0, 3):
            surf.fill(od, (body[0] + body[2] // 2 + k, body[1] + 1, 1, 2))
    hx, hy = head
    ear_h = 5 if ears else 3
    for ex in (-3, 2):
        pygame.draw.polygon(surf, OUTLINE, [(hx + ex - 1, hy - 1), (hx + ex + 1, hy - 1 - ear_h), (hx + ex + 3, hy - 1)])
        pygame.draw.polygon(surf, o, [(hx + ex, hy - 2), (hx + ex + 1, hy - ear_h), (hx + ex + 2, hy - 2)])
    pygame.draw.circle(surf, OUTLINE, (hx, hy), 4.5)
    pygame.draw.circle(surf, o, (hx, hy), 3.5)
    seg(surf, od, (hx - 1, hy - 3), (hx + 1, hy - 3), 1)
    eye = (120, 220, 90) if eyes else od
    surf.fill(eye, (hx - 2, hy, 1, 1))
    surf.fill(eye, (hx + 1, hy, 1, 1))
    surf.fill((240, 120, 140), (hx, hy + 2, 1, 1))                          # nose


def draw_fence(surf):
    surf.fill((36, 26, 44), (FENCE_LEFT, FENCE_TOP + 2, 384 - FENCE_LEFT, 12))
    for px in range(FENCE_LEFT + 4, 384, 16):
        surf.fill((90, 70, 95), (px, FENCE_TOP, 2, 14))
    surf.fill((140, 110, 140), (FENCE_LEFT, FENCE_TOP, 384 - FENCE_LEFT, 2))
    for px in range(FENCE_LEFT + 8, 384, 4):
        surf.fill((60, 46, 70), (px, FENCE_TOP + 7, 1, 1))
    surf.fill((200, 50, 40), (200, FENCE_TOP + 4, 60, 8))                   # banner
    img = pygame.font.Font(None, 11).render("PI BRAWL", False, (255, 220, 60))
    surf.blit(img, (230 - img.get_width() // 2, FENCE_TOP + 5))


# ---------------------------------------------------------------------- the crowd
class Person:
    __slots__ = ("x", "yb", "rest", "cheer", "phone", "phase", "h", "vy", "arms", "delay", "hop")

    def __init__(self, x, yb, rest, cheer, phone, phase):
        self.x, self.yb, self.rest, self.cheer, self.phone, self.phase = x, yb, rest, cheer, phone, phase
        self.h = self.vy = 0.0
        self.arms = 0       # frames left with arms up
        self.delay = 0      # frames before a queued reaction starts
        self.hop = 0.0      # jump speed of the queued reaction


class Audience:
    def __init__(self, app=None, seed=11):
        self.app = app
        self.t = 0
        self.danger = False
        self.ko = 0
        self.cat_duck = 0
        self.cat_twitch = 0
        self.cheer_cooldown = 0
        self.confetti = []
        self.rng = random.Random(seed)
        self.people = []
        rng = random.Random(seed)
        for yb, k, x in ROWS:
            while x < 384:
                pose = rng.choices(("down", "up", "sign", "phone"), (5, 2, 1, 1))[0]
                look = (dim(rng.choice(SHIRTS), k), dim(rng.choice(SKINS), k), dim(rng.choice(HAIRS), k),
                        rng.choice(((220, 60, 50), (40, 120, 205))))
                rest, cheer = sprite(16, 34), sprite(16, 34)
                draw_person(rest, 8, 26, *look[:3], pose, look[3])
                draw_person(cheer, 8, 26, *look[:3], "sign_up" if pose == "sign" else "up", look[3])
                phone = (x + 4, yb - 17) if pose == "phone" else None
                self.people.append(Person(x, yb + rng.choice((0, 0, -1)), rest, cheer, phone,
                                          rng.uniform(0, 6.3)))
                x += rng.randint(11, 15)
        # fence, car and banner in one colour-keyed layer in front of the crowd
        self.front = sprite(384, 64)
        self.front_y = 120
        layer = pygame.Surface((384, 216))
        layer.fill(KEY)
        draw_fence(layer)
        draw_gx460(layer, CAR_X, CAR_Y)
        self.front.blit(layer, (0, -self.front_y))
        self.cats = {}
        for name, kw in (("sit0", dict(tail=0)), ("sit1", dict(tail=1)), ("sit2", dict(tail=2)),
                         ("blink", dict(eyes=False)), ("twitch", dict(ears=False)), ("duck", dict(pose="duck")),
                         ("stand", dict(pose="stand"))):
            s = sprite(28, 28)
            draw_cat(s, 14, 24, **kw)
            self.cats[name] = s

    # -- reactions -------------------------------------------------------
    def react(self, kind, x=192):
        rng = self.rng
        if kind == "hit":
            self.cat_twitch = 8
            for p in self.people:
                if abs(p.x - x) < 45:
                    p.delay, p.arms, p.hop = rng.randint(0, 4), 20, rng.choice((0.0, 0.0, 1.0))
        elif kind == "wave":
            for p in self.people:
                p.delay, p.arms, p.hop = int(abs(p.x - x) / 6), 28, 1.2
            self._cheer("cheer")
        elif kind == "big":
            self.cat_duck = 45
            for p in self.people:
                p.delay, p.arms, p.hop = rng.randint(0, 6), 40, rng.uniform(1.6, 2.4)
            self._cheer("cheer")
        elif kind == "ko":
            self.ko = 150
            self.cat_duck = 0
            for _ in range(70):
                self.confetti.append([rng.uniform(FENCE_LEFT, 384), FENCE_TOP, rng.uniform(-0.6, 0.6),
                                      rng.uniform(-3.6, -1.8), rng.choice(CONFETTI)])
            if self.app:
                self.app.play("roar")
        elif kind == "round":
            for p in self.people:
                p.delay, p.arms, p.hop = rng.randint(0, 10), 30, 0.0
            self._cheer("cheer")

    def _cheer(self, name):
        if self.app and self.cheer_cooldown == 0:
            self.app.play(name)
            self.cheer_cooldown = 45

    # -- per frame -------------------------------------------------------
    def update(self):
        self.t += 1
        rng = self.rng
        self.cheer_cooldown = max(0, self.cheer_cooldown - 1)
        self.cat_duck = max(0, self.cat_duck - 1)
        self.cat_twitch = max(0, self.cat_twitch - 1)
        self.ko = max(0, self.ko - 1)
        for p in self.people:
            if p.delay:
                p.delay -= 1
                if p.delay == 0 and p.hop and p.h == 0:
                    p.vy = p.hop
                continue
            if self.ko and p.h == 0 and rng.random() < 0.15:   # keep jumping during the KO celebration
                p.vy = rng.uniform(1.4, 2.4)
                p.arms = 20
            if p.vy or p.h:
                p.h += p.vy
                p.vy -= 0.25
                if p.h <= 0:
                    p.h = p.vy = 0.0
            if p.arms:
                p.arms -= 1
        for c in self.confetti:
            c[0] += c[2] + math.sin((self.t + c[1]) * 0.1) * 0.3
            c[1] += c[3]
            c[3] = min(c[3] + 0.06, 0.8)
        self.confetti = [c for c in self.confetti if c[1] < 200]

    # -- drawing ---------------------------------------------------------
    def draw_crowd(self, surf):
        blink = 5 if self.danger else 40
        for p in self.people:
            bob = 1 if math.sin(self.t * 0.06 + p.phase) > 0.8 else 0
            y = p.yb - 26 - int(p.h) - bob
            surf.blit(p.cheer if p.arms and not p.delay else p.rest, (p.x - 8, y))
            if p.phone and (self.t + int(p.phase * 10)) % blink == 0:   # camera flash
                surf.fill((255, 255, 255), (p.phone[0], p.phone[1] - int(p.h) - bob, 2, 2))

    def draw_front(self, surf):
        surf.blit(self.front, (0, self.front_y))
        if self.ko and (self.ko // 10) % 2:             # hazard lights
            surf.fill((255, 170, 30), (CAR_X + 1, CAR_Y - 36, 3, 4))
            surf.fill((255, 170, 30), (CAR_X + 89, CAR_Y - 20, 4, 3))
        if self.ko:
            cat = "stand"
        elif self.cat_duck:
            cat = "duck"
        elif self.cat_twitch:
            cat = "twitch"
        elif self.danger:
            cat = "sit2"
        elif self.t % 180 < 6:
            cat = "blink"
        else:
            cat = "sit%d" % ((self.t // 12) % 4 if (self.t // 12) % 4 < 3 else 1)
        surf.blit(self.cats[cat], (CAT_X - 14, CAT_Y - 24))
        for x, y, _, _, color in self.confetti:
            surf.fill(color, (int(x), int(y), 2, 1 + (int(x) % 2)))

    def draw(self, surf):
        self.draw_crowd(surf)
        self.draw_front(surf)
