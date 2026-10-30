"""Fighter, special-move and projectile drawing.

Everything is drawn from the pose skeleton with lines, circles and a few
polygons (outline pass first, then colours), so there are still no sprite
sheets. Colours come from a character's `look` dict (see data.py).
"""
import math
import random

import pygame

OUTLINE = (20, 16, 28)
WHITE = (255, 255, 255)
WIND = (180, 230, 255)


# ---------------------------------------------------------------------- helpers
def shade(c, k=0.7):
    return tuple(int(v * k) for v in c)


def prepare(look):
    """Add a darker `<name>_d` version of every colour (used for the far-side limbs)."""
    out = dict(look)
    for k, c in look.items():
        out[k + "_d"] = shade(c)
    return out


def flash(look):
    """All-white version for the first frames of a hit."""
    return {k: WHITE for k in look}


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def seg(surf, color, a, b, w):
    pygame.draw.line(surf, color, a, b, max(1, int(w)))
    if w >= 3:
        pygame.draw.circle(surf, color, a, w / 2)
        pygame.draw.circle(surf, color, b, w / 2)


def chain(surf, color, pts, w):
    for a, b in zip(pts, pts[1:]):
        seg(surf, color, a, b, w)


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1
    return dx / d, dy / d


def dot(surf, pos, color):
    surf.fill(color, (int(pos[0]), int(pos[1]), 1, 1))


def arc(surf, color, c, rad, a0, sweep, w=1):
    rect = pygame.Rect(0, 0, rad * 2, rad * 2)
    rect.center = (int(c[0]), int(c[1]))
    pygame.draw.arc(surf, color, rect, a0, a0 + sweep, w)


def star(surf, c, r1, r2, color, n=8, rot=0.0):
    pts = []
    for i in range(n * 2):
        a = rot + i * math.pi / n
        rr = r1 if i % 2 == 0 else r2
        pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr))
    pygame.draw.polygon(surf, color, pts)


# ---------------------------------------------------------------------- fighters
def draw_kaze(surf, p, f, t, c):
    """Gi with open lapels, black belt with swinging ends, headband tails, spiky hair, face."""
    w, r = 4, 6
    hx, hy = p["head"]
    sway = math.sin(t * 0.25) * 1.5
    tails = [[(hx - f * (r - 1), hy - 3)] + [(hx - f * (r - 1 + i * 2.5), hy - 3 + i * 0.8 + math.sin(t * 0.3 + i) + k)
                                           for i in range(1, 4)] for k in (0, 2)]
    spikes = [(hx + f * 3, hy - 5), (hx + f * 1, hy - 10), (hx - f * 1, hy - 6), (hx - f * 5, hy - 10),
              (hx - f * 4, hy - 5), (hx - f * 9, hy - 7), (hx - f * 6, hy - 2), (hx - f * 2, hy - 1)]
    feet = ((p["foot_b"], add(p["foot_b"], (f * 4, 0))), (p["foot_f"], add(p["foot_f"], (f * 4, 0))))
    limbs = (((p["hip"], p["knee_b"], p["foot_b"]), w + 1), ((p["neck"], p["elb_b"], p["hand_b"]), w),
             ((p["neck"], p["hip"]), w + 4), ((p["hip"], p["knee_f"], p["foot_f"]), w + 1),
             ((p["neck"], p["elb_f"], p["hand_f"]), w))
    # outline pass
    for pts, width in limbs:
        chain(surf, OUTLINE, pts, width + 2)
    for a, b in feet:
        seg(surf, OUTLINE, a, b, 5)
    for tail in tails:
        chain(surf, OUTLINE, tail, 3)
    pygame.draw.polygon(surf, OUTLINE, spikes, 3)
    pygame.draw.circle(surf, OUTLINE, (hx, hy), r + 1)
    # far leg and arm
    kb, fb = p["knee_b"], p["foot_b"]
    chain(surf, c["gi_d"], (p["hip"], kb, fb), w + 1)
    seg(surf, c["wrap_d"], lerp(kb, fb, 0.72), lerp(kb, fb, 0.92), w + 1)
    seg(surf, c["skin_d"], *feet[0], 3)
    eb, hb = p["elb_b"], p["hand_b"]
    seg(surf, c["gi_d"], p["neck"], eb, w + 1)
    seg(surf, c["skin_d"], eb, hb, w)
    seg(surf, c["wrap_d"], lerp(eb, hb, 0.55), lerp(eb, hb, 0.9), w)
    pygame.draw.circle(surf, c["skin_d"], hb, w / 2 + 1)
    # torso: jacket, hem below the belt, open lapels, belt with knot and tails
    d = unit(p["neck"], p["hip"])
    n = (-d[1], d[0])
    hip = p["hip"]
    seg(surf, c["gi"], p["neck"], hip, w + 4)
    hem = (add(hip, (n[0] * 4, n[1] * 4)), add(hip, (-n[0] * 4, -n[1] * 4)),
           add(hip, (-n[0] * 5 + d[0] * 6, -n[1] * 5 + d[1] * 6)), add(hip, (n[0] * 5 + d[0] * 6, n[1] * 5 + d[1] * 6)))
    pygame.draw.polygon(surf, c["gi"], hem)
    pygame.draw.polygon(surf, OUTLINE, hem, 1)
    chest = lerp(p["neck"], hip, 0.42)
    v = (add(p["neck"], (n[0] * 2.5 + f, n[1] * 2.5)), add(p["neck"], (-n[0] * 2.5 + f, -n[1] * 2.5)), add(chest, (f, 0)))
    pygame.draw.polygon(surf, c["skin"], v)
    seg(surf, c["gi_hi"], v[0], v[2], 1)
    seg(surf, c["gi_hi"], v[1], v[2], 1)
    seg(surf, c["belt"], add(hip, (n[0] * 5, n[1] * 5)), add(hip, (-n[0] * 5, -n[1] * 5)), 3)
    knot = add(hip, (f * 2, 0))
    pygame.draw.circle(surf, c["belt"], knot, 2)
    seg(surf, c["belt"], knot, add(knot, (f * 3 + sway, 7)), 2)
    seg(surf, c["belt"], knot, add(knot, (f * 0.5 + sway, 8)), 2)
    # near leg
    kf, ff = p["knee_f"], p["foot_f"]
    chain(surf, c["gi"], (hip, kf, ff), w + 1)
    seg(surf, c["gi_hi"], lerp(hip, kf, 0.3), lerp(hip, kf, 0.85), 1)
    seg(surf, c["wrap"], lerp(kf, ff, 0.72), lerp(kf, ff, 0.92), w + 1)
    seg(surf, c["skin"], *feet[1], 3)
    # near arm: sleeve with frayed cuff, bare forearm, wrist wrap, fist
    ef, hf = p["elb_f"], p["hand_f"]
    seg(surf, c["gi"], p["neck"], ef, w + 1)
    seg(surf, c["gi_hi"], lerp(p["neck"], ef, 0.8), ef, w)
    seg(surf, c["skin"], ef, hf, w)
    seg(surf, c["wrap"], lerp(ef, hf, 0.55), lerp(ef, hf, 0.9), w)
    pygame.draw.circle(surf, c["skin"], hf, w / 2 + 2)
    pygame.draw.circle(surf, c["wrap"], hf, w / 2 + 2, 1)
    # head: hair, face, headband
    pygame.draw.polygon(surf, c["hair"], spikes)
    pygame.draw.circle(surf, c["skin"], (hx, hy), r)
    pygame.draw.circle(surf, c["hair"], (hx - f, hy - 1), r, draw_top_right=True, draw_top_left=True)
    for tail in tails:
        chain(surf, c["band"], tail, 1)
    seg(surf, c["band"], (hx - r, hy - 3), (hx + r, hy - 3), 2)
    left = 1 if f < 0 else 0
    for ex in (1, 4):                                                      # eyes
        surf.fill(WHITE, (int(hx + f * ex) - left, int(hy - 1), 2, 2))
        dot(surf, (hx + f * (ex + 1) - left, hy), (25, 25, 40))
    seg(surf, (40, 30, 30), (hx - f * 0.5, hy - 2), (hx + f * 2.5, hy - 1.5), 1)    # brows, angled in
    seg(surf, (40, 30, 30), (hx + f * 3.5, hy - 1.5), (hx + f * 5.5, hy - 2.5), 1)
    dot(surf, (hx + f * 6, hy + 1), c["skin_d"])                           # nose
    seg(surf, (150, 70, 70), (hx + f * 2, hy + 3), (hx + f * 4, hy + 3), 1)  # mouth
    surf.fill(c["skin_d"], (int(hx - f * 2) - 1, int(hy), 2, 2))           # ear


def draw_brakk(surf, p, f, t, c):
    """Open vest with trim, cross strap, iron shoulder pad, studded belt, boots, beard and scar."""
    w, r = 5, 7
    hx, hy = p["head"]
    feet = ((add(p["foot_b"], (-f, 0)), add(p["foot_b"], (f * 5, 0))),
            (add(p["foot_f"], (-f, 0)), add(p["foot_f"], (f * 5, 0))))
    limbs = (((p["hip"], p["knee_b"], p["foot_b"]), w + 2), ((p["neck"], p["elb_b"], p["hand_b"]), w + 1),
             ((p["neck"], p["hip"]), w + 6), ((p["hip"], p["knee_f"], p["foot_f"]), w + 2),
             ((p["neck"], p["elb_f"], p["hand_f"]), w + 1))
    pad = lerp(p["neck"], p["elb_f"], 0.3)
    for pts, width in limbs:
        chain(surf, OUTLINE, pts, width + 2)
    for a, b in feet:
        seg(surf, OUTLINE, a, b, 6)
    pygame.draw.circle(surf, OUTLINE, (hx, hy), r + 1)
    pygame.draw.circle(surf, OUTLINE, pad, 6)
    pygame.draw.circle(surf, OUTLINE, p["hand_f"], w / 2 + 4)
    # far leg: trousers, knee pad, boot
    kb, fb = p["knee_b"], p["foot_b"]
    chain(surf, c["pants_d"], (p["hip"], kb, fb), w + 2)
    seg(surf, c["boot_d"], lerp(kb, fb, 0.5), fb, w + 2)
    seg(surf, c["boot_d"], *feet[0], 4)
    pygame.draw.circle(surf, c["iron_d"], kb, 3)
    # far arm with bracer
    eb, hb = p["elb_b"], p["hand_b"]
    chain(surf, c["skin_d"], (p["neck"], eb, hb), w + 1)
    seg(surf, c["leather_d"], lerp(eb, hb, 0.35), lerp(eb, hb, 0.85), w + 1)
    pygame.draw.circle(surf, c["skin_d"], hb, w / 2 + 2)
    # torso: open vest with trim, cross strap, studded belt and buckle
    d = unit(p["neck"], p["hip"])
    n = (-d[1], d[0])
    hip = p["hip"]
    seg(surf, c["vest"], p["neck"], hip, w + 6)
    c0, c1 = add(lerp(p["neck"], hip, 0.02), (f * 2, 0)), add(lerp(p["neck"], hip, 0.62), (f * 2, 0))
    seg(surf, c["skin"], c0, c1, 3)
    seg(surf, c["trim"], add(c0, (-f * 2, 0)), add(c1, (-f * 2, 0)), 1)
    seg(surf, c["trim"], add(c0, (f * 2, 0)), add(c1, (f * 2, 0)), 1)
    seg(surf, c["leather"], add(p["neck"], (f * 3, 1)), add(lerp(p["neck"], hip, 0.9), (-f * 4, 0)), 2)
    bl, br = add(hip, (n[0] * 6.5, n[1] * 6.5)), add(hip, (-n[0] * 6.5, -n[1] * 6.5))
    seg(surf, c["leather"], bl, br, 4)
    dot(surf, lerp(bl, br, 0.15), c["trim"])
    dot(surf, lerp(bl, br, 0.85), c["trim"])
    bx, by = int(hip[0] + f * 2) - 2, int(hip[1])
    surf.fill(c["trim"], (bx, by - 2, 5, 4))
    surf.fill(c["leather"], (bx + 1, by - 1, 3, 2))
    # near leg
    kf, ff = p["knee_f"], p["foot_f"]
    chain(surf, c["pants"], (hip, kf, ff), w + 2)
    seg(surf, c["boot"], lerp(kf, ff, 0.5), ff, w + 2)
    seg(surf, c["boot"], *feet[1], 4)
    seg(surf, (90, 80, 80), add(feet[1][0], (0, 1.5)), add(feet[1][1], (0, 1.5)), 1)   # sole
    pygame.draw.circle(surf, c["iron"], kf, 3)
    dot(surf, add(kf, (-1, -1)), (230, 235, 245))
    # near arm: tattoo band, bracer with rivet, big fist
    ef, hf = p["elb_f"], p["hand_f"]
    chain(surf, c["skin"], (p["neck"], ef, hf), w + 1)
    seg(surf, c["ink"], lerp(p["neck"], ef, 0.45), lerp(p["neck"], ef, 0.6), w + 1)
    seg(surf, c["leather"], lerp(ef, hf, 0.35), lerp(ef, hf, 0.85), w + 1)
    dot(surf, lerp(ef, hf, 0.6), c["trim"])
    pygame.draw.circle(surf, c["skin"], hf, w / 2 + 3)
    seg(surf, c["skin_d"], add(hf, (f, -2)), add(hf, (f, 2)), 1)          # knuckles
    # iron shoulder pad
    pygame.draw.circle(surf, c["iron"], pad, 5)
    pygame.draw.circle(surf, (205, 210, 222), add(pad, (-f, -2)), 2)
    dot(surf, add(pad, (-3, 3)), (90, 90, 100))
    dot(surf, add(pad, (3, 3)), (90, 90, 100))
    # head: flat-top, beard, heavy brow, scar
    pygame.draw.circle(surf, c["hair"], (hx, hy), r)
    pygame.draw.circle(surf, c["skin"], (hx + f, hy + 2), r - 1)
    pygame.draw.polygon(surf, c["hair"], ((hx - f * 2, hy), (hx - f, hy + r + 1), (hx + f * 3, hy + r + 2),
                                          (hx + f * 7, hy + 4), (hx + f * 7, hy + 2), (hx + f * 4, hy + 2),
                                          (hx + f, hy + 2)))
    seg(surf, (120, 50, 50), (hx + f * 3, hy + 4), (hx + f * 5, hy + 4), 1)     # mouth
    seg(surf, c["hair"], (hx, hy - 2), (hx + f * 7, hy - 2), 2)                  # brow
    for ex in (2, 5):
        dot(surf, (hx + f * ex, hy), WHITE)
        dot(surf, (hx + f * (ex + 1), hy), (25, 20, 25))
    seg(surf, (235, 175, 155), (hx + f * 4, hy - 4), (hx + f * 6, hy + 2), 1)    # scar
    surf.fill(c["skin_d"], (int(hx + f * 7) - (1 if f < 0 else 0), int(hy), 2, 2))  # nose
    pygame.draw.circle(surf, c["skin_d"], (hx - f * 2, hy + 1), 1.5)              # ear


DRAW = {"kaze": draw_kaze, "brakk": draw_brakk}


def ghost(surf, p, dx, color, w):
    """Flat one-colour silhouette, used for the Ram Charge afterimages."""
    q = {j: (v[0] + dx, v[1]) for j, v in p.items()}
    for pts in ((q["hip"], q["knee_b"], q["foot_b"]), (q["neck"], q["hip"]), (q["hip"], q["knee_f"], q["foot_f"]),
                (q["neck"], q["elb_f"], q["hand_f"])):
        chain(surf, color, pts, w)
    pygame.draw.circle(surf, color, q["head"], 6)


# ---------------------------------------------------------------------- special-move effects
def draw_fx(surf, fi, p, behind):
    m = fi.move
    if fi.state != "attack" or not m.fx:
        return
    t, f, kind = fi.t, fi.facing, m.fx
    active = m.startup < t <= m.startup + m.active
    if kind == "tempest" and not behind and t <= m.startup:
        hands = lerp(p["hand_f"], p["hand_b"], 0.5)
        if t < 10:                                         # wind spiralling into the hands
            for i in range(3):
                arc(surf, WIND, hands, 16 - t + i * 4, t * 0.5 + i * 2.1, 1.6)
        else:
            rad = 2 + min(5, fi.charge / 6)
            pygame.draw.circle(surf, (40, 110, 200), hands, rad + 1)
            pygame.draw.circle(surf, (170, 230, 255), hands, rad)
            if fi.charged:                                 # sparkles once fully charged
                for i in range(4):
                    a = fi.anim * 0.3 + i * math.pi / 2
                    dot(surf, (hands[0] + math.cos(a) * 9, hands[1] + math.sin(a) * 9), WHITE)
    elif kind == "cyclone" and behind:
        if t <= m.startup:
            for i in range(3):
                arc(surf, WIND, p["foot_f"], 8 + i * 4, math.pi * 0.05, math.pi * 0.9)
        elif t <= m.startup + 16:
            mid = lerp(p["neck"], p["hip"], 0.5)
            for i in range(3):
                arc(surf, WIND, mid, 14 + i * 4, t * 0.6 + i * 2.1, 2.2)
        elif active:
            foot = p["foot_f"]
            for i in range(3):
                seg(surf, (240, 240, 250), (foot[0] - f * (4 + i * 3), foot[1] - 14 + i * 3),
                    (foot[0] - f * (2 + i * 3), foot[1] - 4 + i * 3), 1)
    elif kind == "slam" and not behind and 8 <= t <= m.startup and t % 4 < 2:
        for hand in (p["hand_f"], p["hand_b"]):
            seg(surf, (255, 240, 180), add(hand, (-3, -4)), add(hand, (3, -4)), 1)
            seg(surf, (255, 240, 180), add(hand, (0, -7)), add(hand, (0, -1)), 1)
    elif kind == "ram":
        if behind and 3 <= t <= m.startup:
            nose = add(p["head"], (f * 9, 0))
            for i in range(3):
                pygame.draw.circle(surf, (235, 235, 240), (nose[0] + f * (2 + i * 3), nose[1] - i * 2 - (t % 3)),
                                   1.5 + i * 0.6)
            if 5 <= t <= 11:
                for i in range(3):
                    pygame.draw.circle(surf, (170, 150, 140), add(p["foot_b"], (-f * (4 + i * 4), -1 - (t + i) % 3)), 2)
        elif behind and active:
            ghost(surf, p, -f * 20, (95, 40, 50), 5)
            ghost(surf, p, -f * 10, (150, 55, 45), 5)
            for i in range(5):
                y = p["hip"][1] - 20 + i * 7
                x = p["hip"][0] - f * (26 + (i * 7) % 11)
                seg(surf, (240, 240, 250), (x, y), (x - f * (10 + i % 3 * 4), y), 1)
        elif not behind and active:
            pad = lerp(p["neck"], p["elb_f"], 0.3)
            for i in range(3):
                arc(surf, (255, 140 - i * 30, 50), pad, 7 + i * 2, -1.2 + i * 0.3 + (math.pi if f < 0 else 0), 2.4, 2)


# ---------------------------------------------------------------------- projectiles
def spiral(surf, c, d, length):
    for i in range(0, length, 1):
        x = c[0] - d * i
        for ph, col in ((0, (150, 215, 255)), (math.pi, (90, 160, 235))):
            dot(surf, (x, c[1] + math.sin(i * 0.45 + ph) * (6 - i * 0.12)), col)


def pillar(surf, x, gy, h, w=9):
    if h < 2:
        return
    top = gy - h
    pts = ((x - w / 2, gy), (x - w / 2 + 1, top + 4), (x - 1, top), (x + 2, top + 2), (x + w / 2, top + 6),
           (x + w / 2, gy))
    pygame.draw.polygon(surf, OUTLINE, pts)
    pygame.draw.polygon(surf, (150, 105, 75), [(px + (1 if px < x else -1), py + 1) for px, py in pts])
    seg(surf, (200, 150, 100), (x - w / 2 + 2, top + 6), (x - w / 2 + 2, gy - 2), 1)
    seg(surf, (255, 170, 60), (x, top + 5), (x + 1, top + h * 0.5), 1)        # glowing crack


def draw_projectile(surf, pr, ox, oy, gy):
    cx, cy = pr.x + ox, gy - pr.y + oy
    d = 1 if pr.vx > 0 else -1
    if pr.style == "orb":
        rad = 12 if pr.charged else 9
        if pr.linger is not None:                          # bursting into a gust
            k = pr.t * 0.7
            for i in range(4):
                arc(surf, (200, 240, 255), (cx, cy), 5 + i * 3 + (pr.t % 4), k + i * 1.4, 2.4)
            star(surf, (cx, cy), rad - 1, 4, WHITE, rot=pr.t * 0.2)
            pygame.draw.circle(surf, (70, 170, 255), (cx, cy), max(2, rad // 3))
            return
        spiral(surf, (cx - d * rad, cy), d, 30)
        pulse = (pr.t // 3) % 2
        pygame.draw.circle(surf, (40, 110, 200), (cx, cy), rad + 2 + pulse)
        pygame.draw.circle(surf, (70, 170, 255), (cx, cy), rad)
        pygame.draw.circle(surf, (170, 230, 255), (cx, cy), rad * 0.65)
        pygame.draw.circle(surf, WHITE, (cx + d * 2, cy - 1), rad * 0.3)
        for i in range(3):
            arc(surf, (200, 240, 255), (cx, cy), rad + 4, pr.t * 0.3 + i * 2.1, 1.3)
    else:  # rock pillars bursting up one after another along a glowing crack
        ground = gy + oy
        x0 = pr.x0 + ox
        dist = abs(cx - x0)
        rng = random.Random(int(pr.x0))
        pts, step = [], 6
        for i in range(int(dist // step) + 1):
            pts.append((x0 + d * i * step, ground + rng.choice((-1, 0, 0, 1))))
        pts.append((cx, ground))
        if len(pts) > 1:
            pygame.draw.lines(surf, (255, 170, 60), False, pts, 1)
        for k in range(int(dist // 16) + 1):
            px = x0 + d * (k * 16 + 8)
            age = (dist - k * 16) / max(0.5, abs(pr.vx))
            top = min(30, 10 + k * 5)
            if age < 6:
                pillar(surf, px, ground, top * age / 6)
            elif age < 18:
                pillar(surf, px, ground, top)
            elif age < 30:
                h = top * (30 - age) / 12
                pillar(surf, px, ground, h)
                for i in range(3):
                    surf.fill((150, 105, 75), (int(px - 5 + i * 4), int(ground - h - 3 - (i % 2) * 3 - (age - 18) / 3), 2, 2))
