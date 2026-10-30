"""All Pi Rush sprites, drawn in code (no asset files).

Karts are composed from a vehicle shape (kart, buggy, mower, boat, trike, saucer)
and a big cartoon head (frog, robot, cat, penguin, dino, alien) in three views:
top-down (for the overhead camera and the minimap), rear/front (mode-7) and side.
Heads have three expressions: normal, hit (X eyes, open mouth) and win (happy
eyes, arms up). Everything is cached by its arguments, so a sprite is drawn once.
"""
import math

import pygame

OUT = (20, 16, 28)
WHITE = (255, 255, 255)
PINK = (255, 150, 170)
_cache = {}


def shade(c, k=0.7):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def light(c, k=0.3):
    return tuple(min(255, int(v + (255 - v) * k)) for v in c)


def cached(key, make):
    s = _cache.get(key)
    if s is None:
        s = _cache[key] = make()
    return s


def poly(surf, color, pts, outline=True):
    if outline:
        pygame.draw.polygon(surf, OUT, pts)
        pygame.draw.polygon(surf, OUT, pts, 2)
    pygame.draw.polygon(surf, color, pts)


def circle(surf, color, c, r):
    pygame.draw.circle(surf, OUT, c, r + 1)
    pygame.draw.circle(surf, color, c, r)


def ellipse(surf, color, rect):
    x, y, w, h = rect
    pygame.draw.ellipse(surf, OUT, (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.ellipse(surf, color, rect)


def rrect(surf, color, rect, radius=2):
    x, y, w, h = rect
    pygame.draw.rect(surf, OUT, (x - 1, y - 1, w + 2, h + 2), border_radius=radius + 1)
    pygame.draw.rect(surf, color, rect, border_radius=radius)


# ---------------------------------------------------------------------- faces
def eyes(surf, cx, cy, r, expr, style="round", dx=0.42, dy=-0.15, size=0.3):
    """Two eyes at cx +- r*dx. style: round (white + pupil), led (robot), black (alien)."""
    ew = max(2, int(r * size * 2))
    for sx in (-1, 1):
        ex, ey = int(cx + sx * r * dx), int(cy + r * dy)
        if expr == "hit":                               # X eyes
            d = max(1, ew // 2)
            pygame.draw.line(surf, OUT, (ex - d, ey - d), (ex + d, ey + d), 2)
            pygame.draw.line(surf, OUT, (ex - d, ey + d), (ex + d, ey - d), 2)
        elif expr == "win":                             # happy closed eyes (arches)
            d = max(1, ew // 2)
            pygame.draw.lines(surf, OUT, False, [(ex - d, ey + 1), (ex, ey - d + 1), (ex + d, ey + 1)], 2)
        elif style == "led":
            pygame.draw.rect(surf, OUT, (ex - ew // 2 - 1, ey - ew // 3 - 1, ew + 2, ew * 2 // 3 + 2))
            pygame.draw.rect(surf, (120, 240, 255), (ex - ew // 2, ey - ew // 3, ew, ew * 2 // 3))
        elif style == "black":
            pygame.draw.ellipse(surf, OUT, (ex - ew // 2, ey - ew * 2 // 3, ew, ew * 4 // 3))
            pygame.draw.ellipse(surf, (60, 70, 90), (ex - ew // 2 + 1, ey - ew * 2 // 3 + 1, ew - 2, ew * 4 // 3 - 2))
            surf.fill(WHITE, (ex - 1, ey - ew // 2, 1, 2))
        else:
            pygame.draw.ellipse(surf, OUT, (ex - ew // 2 - 1, ey - ew // 2 - 1, ew + 2, ew + 2))
            pygame.draw.ellipse(surf, WHITE, (ex - ew // 2, ey - ew // 2, ew, ew))
            pygame.draw.rect(surf, OUT, (ex - 1 + sx, ey - 1, 2, 2))


def mouth(surf, cx, cy, r, expr, style="smile"):
    w = int(r * 0.55)
    if expr == "hit":                                   # open "ouch" mouth
        pygame.draw.ellipse(surf, OUT, (cx - w // 2, cy - 2, w, w))
        pygame.draw.ellipse(surf, (200, 60, 70), (cx - w // 2 + 1, cy - 1, w - 2, w - 2))
    elif expr == "win":                                 # big grin
        pts = [(cx - w, cy - 1), (cx + w, cy - 1), (cx + w // 2, cy + w // 2 + 1), (cx - w // 2, cy + w // 2 + 1)]
        pygame.draw.polygon(surf, OUT, pts)
        pygame.draw.polygon(surf, (200, 60, 70), [(cx - w + 2, cy), (cx + w - 2, cy), (cx + w // 2 - 1, cy + w // 2 - 1),
                                                  (cx - w // 2 + 1, cy + w // 2 - 1)])
        surf.fill(WHITE, (cx - w + 2, cy, 2 * w - 4, 2))
    elif style == "grille":
        for i in (-1, 0, 1):
            surf.fill(OUT, (cx + i * 3 - 1, cy - 1, 2, 3))
    elif style == "beak":
        poly(surf, (255, 160, 40), [(cx - w, cy - 2), (cx + w, cy - 2), (cx, cy + w // 2 + 2)])
    elif style == "teeth":
        pygame.draw.lines(surf, OUT, False, [(cx - w, cy - 2), (cx - w // 2, cy + 2), (cx, cy + 3), (cx + w // 2, cy + 2),
                                             (cx + w, cy - 2)], 2)
        for i in range(-w + 2, w - 2, 3):
            surf.fill(WHITE, (cx + i, cy - 1, 2, 2))
    elif style == "tiny":
        surf.fill(OUT, (cx - 1, cy, 3, 2))
    else:
        pygame.draw.lines(surf, OUT, False, [(cx - w, cy - 1), (cx - w // 2, cy + 1), (cx + w // 2, cy + 1),
                                             (cx + w, cy - 1)], 2)


def head(surf, cx, cy, r, racer, expr="normal", view="face"):
    """Big cartoon head centred at (cx, cy) with radius r. view: face, top, side (facing up/right)."""
    sp, col = racer.species, racer.skin
    cx, cy, r = int(cx), int(cy), int(r)
    hot = expr == "pepper"
    if hot:                                             # red face, puffed cheeks
        col = tuple(int(c * 0.4 + h * 0.6) for c, h in zip(col, (240, 70, 50)))
    if expr not in ("hit", "win"):
        expr = "normal"
    if view == "top":
        _head_top(surf, cx, cy, r, sp, col, expr, racer.trim)
        if hot:
            for sx in (-1, 1):
                pygame.draw.circle(surf, (255, 120, 100), (cx + sx * int(r * 0.75), cy + int(r * 0.1)), max(2, r // 3))
        return
    if view == "side":
        _head_side(surf, cx, cy, r, sp, col, expr, racer.trim)
        return
    _head_face(surf, cx, cy, r, sp, col, expr, racer)
    if hot:
        for sx in (-1, 1):
            circle(surf, (255, 120, 100), (cx + sx * int(r * 0.75), cy + int(r * 0.25)), max(2, int(r * 0.38)))
        pygame.draw.ellipse(surf, OUT, (cx - 2, cy + int(r * 0.4), 5, 4))
        for i in range(3):                              # steam
            pygame.draw.circle(surf, (230, 230, 240), (cx + int(r * 1.3) + i * 2, cy - r - 2 - i * 3), 2 - i // 2)


def _head_face(surf, cx, cy, r, sp, col, expr, racer):
    """Rear / front / portrait: the racer looks at the camera."""
    if sp == "frog":
        circle(surf, col, (cx, cy), r)
        for sx in (-1, 1):                              # eye bumps on top
            circle(surf, col, (cx + sx * int(r * 0.55), cy - int(r * 0.75)), int(r * 0.45))
        eyes(surf, cx, cy, r, expr, dx=0.55, dy=-0.75, size=0.3)
        mouth(surf, cx, cy + int(r * 0.35), r + 2, expr)
        for sx in (-1, 1):
            surf.fill(PINK, (cx + sx * int(r * 0.6) - 1, cy + int(r * 0.15), 3, 2))
    elif sp == "robot":
        rrect(surf, col, (cx - r, cy - r, 2 * r, 2 * r), max(2, r // 3))
        pygame.draw.line(surf, OUT, (cx, cy - r), (cx, cy - r - r // 2 - 2), 2)
        circle(surf, (240, 70, 60), (cx, cy - r - r // 2 - 2), max(2, r // 4))
        surf.fill(shade(col), (cx - r + 2, cy + r - 3, 2 * r - 4, 2))
        eyes(surf, cx, cy, r, expr, style="led", dx=0.45, dy=-0.25, size=0.32)
        mouth(surf, cx, cy + int(r * 0.45), r, expr, style="grille")
    elif sp == "cat":
        for sx in (-1, 1):                              # ears
            ex = cx + sx * int(r * 0.7)
            poly(surf, col, [(ex - r // 3, cy - r // 2), (ex, cy - r - r // 2), (ex + r // 3, cy - r // 2)])
            pygame.draw.polygon(surf, PINK, [(ex - r // 6, cy - r // 2 - 1), (ex, cy - r - r // 6), (ex + r // 6, cy - r // 2 - 1)])
        circle(surf, col, (cx, cy), r)
        pygame.draw.circle(surf, shade(col, 0.85), (cx - r // 2, cy - r // 3), max(2, r // 3))  # patch
        eyes(surf, cx, cy, r, expr, dx=0.42, dy=-0.15, size=0.3)
        poly(surf, PINK, [(cx - 2, cy + r // 4), (cx + 2, cy + r // 4), (cx, cy + r // 4 + 3)], outline=False)
        mouth(surf, cx, cy + int(r * 0.5), r * 0.8, expr)
        if expr != "hit":
            for sx in (-1, 1):
                for k in (-1, 1):
                    pygame.draw.line(surf, OUT, (cx + sx * r // 2, cy + r // 3 + k),
                                     (cx + sx * (r + r // 3), cy + r // 4 + k * 3), 1)
    elif sp == "penguin":
        circle(surf, col, (cx, cy), r)
        pygame.draw.ellipse(surf, WHITE, (cx - int(r * 0.7), cy - int(r * 0.45), int(r * 1.4), int(r * 1.3)))
        eyes(surf, cx, cy, r, expr, dx=0.36, dy=-0.1, size=0.28)
        mouth(surf, cx, cy + int(r * 0.45), r, expr, style="beak")
    elif sp == "dino":
        for i in (-1, 0, 1):                            # crest spikes
            sx = cx + i * int(r * 0.6)
            poly(surf, racer.trim, [(sx - r // 3, cy - r + 2), (sx, cy - r - r // 2 - abs(i) * -2), (sx + r // 3, cy - r + 2)])
        circle(surf, col, (cx, cy), r)
        pygame.draw.ellipse(surf, light(col, 0.4), (cx - int(r * 0.5), cy, r, int(r * 0.8)))
        eyes(surf, cx, cy, r, expr, dx=0.42, dy=-0.25, size=0.34)
        mouth(surf, cx, cy + int(r * 0.45), r, expr, style="teeth")
    else:                                               # alien: tall dome, big black eyes, antenna
        ellipse(surf, col, (cx - r, cy - int(r * 1.3), 2 * r, int(r * 2.4)))
        pygame.draw.line(surf, OUT, (cx + r // 2, cy - int(r * 1.2)), (cx + r, cy - int(r * 1.8)), 2)
        circle(surf, racer.trim, (cx + r, cy - int(r * 1.8)), max(2, r // 4))
        eyes(surf, cx, cy, r, expr, style="black", dx=0.45, dy=-0.3, size=0.34)
        mouth(surf, cx, cy + int(r * 0.5), r, expr, style="tiny")


def _head_top(surf, cx, cy, r, sp, col, expr, trim):
    """Head seen from above, facing up (nose at the top)."""
    if sp == "cat":
        for sx in (-1, 1):
            ex = cx + sx * int(r * 0.7)
            poly(surf, col, [(ex - r // 3, cy - r // 3), (ex, cy - r - r // 3), (ex + r // 3, cy - r // 3)])
    if sp == "robot":
        rrect(surf, col, (cx - r, cy - r, 2 * r, 2 * r), max(1, r // 3))
        circle(surf, (240, 70, 60), (cx, cy), max(1, r // 3))
    elif sp == "alien":
        ellipse(surf, col, (cx - r, cy - int(r * 1.2), 2 * r, int(r * 2.4)))
        circle(surf, trim, (cx + r // 2, cy + r // 2), max(1, r // 3))
    else:
        circle(surf, col, (cx, cy), r)
    if sp == "frog":
        for sx in (-1, 1):
            circle(surf, col, (cx + sx * int(r * 0.55), cy - int(r * 0.6)), int(r * 0.42))
        eyes(surf, cx, cy, r, expr, dx=0.55, dy=-0.6, size=0.28)
    elif sp == "penguin":
        pygame.draw.ellipse(surf, WHITE, (cx - int(r * 0.6), cy - int(r * 0.9), int(r * 1.2), int(r * 1.1)))
        poly(surf, (255, 160, 40), [(cx - r // 3, cy - r + 1), (cx + r // 3, cy - r + 1), (cx, cy - r - r // 2)])
        eyes(surf, cx, cy, r, expr, dx=0.36, dy=-0.5, size=0.26)
    elif sp == "dino":
        for i in (-1, 0, 1):
            pygame.draw.rect(surf, OUT, (cx - 2, cy + i * (r // 2) - 2, 4, 4))
            pygame.draw.rect(surf, trim, (cx - 1, cy + i * (r // 2) - 1, 2, 2))
        eyes(surf, cx, cy, r, expr, dx=0.5, dy=-0.5, size=0.3)
    elif sp == "robot":
        eyes(surf, cx, cy, r, expr, style="led", dx=0.45, dy=-0.55, size=0.3)
    elif sp == "alien":
        eyes(surf, cx, cy, r, expr, style="black", dx=0.45, dy=-0.5, size=0.3)
    else:
        eyes(surf, cx, cy, r, expr, dx=0.42, dy=-0.5, size=0.28)


def _head_side(surf, cx, cy, r, sp, col, expr, trim):
    """Head seen from the side, facing right."""
    if sp == "robot":
        rrect(surf, col, (cx - r, cy - r, 2 * r, 2 * r), max(1, r // 3))
        pygame.draw.line(surf, OUT, (cx, cy - r), (cx, cy - r - r // 2), 2)
        circle(surf, (240, 70, 60), (cx, cy - r - r // 2), max(1, r // 4))
    elif sp == "alien":
        ellipse(surf, col, (cx - r, cy - int(r * 1.3), 2 * r, int(r * 2.4)))
    else:
        circle(surf, col, (cx, cy), r)
    if sp == "frog":
        circle(surf, col, (cx + r // 3, cy - int(r * 0.8)), int(r * 0.42))
    elif sp == "cat":
        poly(surf, col, [(cx - r // 2, cy - r // 2), (cx - r // 3, cy - r - r // 2), (cx + r // 6, cy - r // 2)])
    elif sp == "penguin":
        pygame.draw.ellipse(surf, WHITE, (cx - r // 4, cy - r // 2, r, r))
        poly(surf, (255, 160, 40), [(cx + r // 2, cy - 2), (cx + r + r // 2, cy + 1), (cx + r // 2, cy + 4)])
    elif sp == "dino":
        for i in range(3):
            sx = cx - r + i * (r // 2) - 1
            poly(surf, trim, [(sx, cy - r + 2), (sx + r // 4, cy - r - r // 2), (sx + r // 2, cy - r + 2)])
    eyes(surf, cx + r // 2, cy, r, expr, style="black" if sp == "alien" else ("led" if sp == "robot" else "round"),
         dx=0, dy=-0.25, size=0.3)
    if expr == "hit":
        mouth(surf, cx + r // 2, cy + r // 2, r, expr)


def arms(surf, cx, cy, r, racer, expr, view="face", body=None):
    """Hands on the wheel, or both arms up when winning."""
    col = racer.skin
    hand = max(1, r // 3)
    for sx in (-1, 1):
        if expr == "win":
            up = (int(r * 1.5), -int(r * 0.9))
        elif expr == "flail":                           # one arm high, one wide, mid-air panic
            up = (int(r * 1.7), -int(r * 1.1)) if sx > 0 else (int(r * 1.8), -int(r * 0.1))
        else:
            up = None
        if view == "face":
            sh = (cx + sx * int(r * 0.8), cy + int(r * 0.9))
            hd = (cx + sx * up[0], cy + up[1]) if up else (cx + sx * int(r * 1.2), cy + int(r * 1.6))
            pygame.draw.line(surf, OUT, sh, hd, hand + 2)
            pygame.draw.line(surf, body or racer.body, sh, hd, hand)
            circle(surf, col, hd, hand)
        else:
            hd = (cx + sx * int(up[0] * 0.8), cy + up[1]) if up else (cx + sx * int(r * 1.0), cy - int(r * 0.2))
            circle(surf, col, hd, hand)


# ---------------------------------------------------------------------- vehicles, top-down (nose up)
def kart_top(racer, expr="normal"):
    """Top-down kart with the driver's head, ~16x24 in a 28x32 surface."""
    def make():
        w, h = 28, 32
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, body, trim, shape = w // 2, racer.body, racer.trim, racer.shape
        top, bot = 4, 28
        if shape in ("kart", "buggy", "mower", "trike"):
            wheels = [(cx - 9, top + 3), (cx + 5, top + 3), (cx - 9, bot - 9), (cx + 5, bot - 9)]
            if shape == "trike":
                wheels = [(cx - 2, top), (cx - 9, bot - 9), (cx + 5, bot - 9)]
            if shape == "mower":
                wheels = [(cx - 8, top + 7), (cx + 4, top + 7), (cx - 10, bot - 9), (cx + 6, bot - 9)]
            for wx, wy in wheels:
                big = shape == "buggy" or (shape == "mower" and wy > h // 2)
                rrect(s, (60, 60, 70), (wx, wy, 5 if big else 4, 7 if big else 6), 1)
        if shape == "boat":
            poly(s, body, [(cx, top), (cx + 8, top + 10), (cx + 7, bot - 2), (cx - 7, bot - 2), (cx - 8, top + 10)])
            pygame.draw.polygon(s, trim, [(cx, top + 2), (cx + 6, top + 10), (cx - 6, top + 10)])
            rrect(s, shade(body), (cx - 3, bot - 8, 6, 4), 1)
            rrect(s, trim, (cx - 2, bot - 7, 4, 2), 1)          # funnel
        elif shape == "saucer":
            ellipse(s, body, (cx - 11, top + 2, 22, 22))
            pygame.draw.ellipse(s, shade(body), (cx - 9, top + 6, 18, 16))
            for i in range(6):
                a = i * math.pi / 3
                s.fill(trim, (int(cx + math.cos(a) * 9) - 1, int(top + 13 + math.sin(a) * 9) - 1, 2, 2))
        elif shape == "mower":
            rrect(s, (90, 90, 100), (cx - 9, top + 1, 18, 7), 2)   # cutting deck
            rrect(s, body, (cx - 6, top + 6, 12, 18), 2)
            rrect(s, trim, (cx - 4, bot - 5, 8, 3), 1)             # grass bag
        else:
            rrect(s, body, (cx - 6, top + 1, 12, 23), 3)
            s.fill(shade(body), (cx - 5, top + 13, 10, 9))
            s.fill(trim, (cx - 1, top + 2, 2, 5))                  # nose stripe
            if shape == "kart":
                rrect(s, trim, (cx - 8, bot - 4, 16, 3), 1)        # spoiler
            elif shape == "buggy":
                pygame.draw.rect(s, OUT, (cx - 7, top + 8, 14, 12), 2)  # roll cage
            elif shape == "trike":
                rrect(s, (90, 90, 100), (cx - 2, bot - 4, 4, 4), 1)     # rocket exhaust
                s.fill((255, 200, 60), (cx - 1, bot - 1, 2, 2))
        hy = top + 14
        if shape == "saucer":
            pygame.draw.circle(s, light(trim, 0.5), (cx, hy - 1), 7)  # glass dome
        arms(s, cx, hy, 5, racer, expr, view="top")
        head(s, cx, hy, 5, racer, expr, view="top")
        return s
    return cached(("top", racer.name, expr), make)


def kart_top_rotations(racer, expr="normal", n=32):
    """Pre-rotated frames: index i faces i*360/n degrees clockwise from up."""
    return cached(("toprot", racer.name, expr, n),
                  lambda: [pygame.transform.rotate(kart_top(racer, expr), -i * 360 / n) for i in range(n)])


# ---------------------------------------------------------------------- vehicles, rear / front / side
def kart_rear(racer, expr="normal", lean=0, front=False, w=56, h=36):
    """Kart seen from behind (or the front, lights swapped). lean = -1/0/1 tilts the head into a turn."""
    def make():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, body, trim, shape = w // 2, racer.body, racer.trim, racer.shape
        floor = h - 2
        ww, wh = max(6, w // 6), max(6, h // 3)
        if shape not in ("boat", "saucer"):                   # wheels
            for wx in (1, w - ww - 1):
                rrect(s, (60, 60, 70), (wx, floor - wh, ww, wh), 2)
                s.fill((110, 110, 120), (wx + 1, floor - wh + 1, ww - 2, 2))
        bw = w - 2 * ww + 4
        by = floor - int(h * 0.55)
        if shape == "boat":
            poly(s, body, [(cx - bw // 2 - 4, floor - 8), (cx + bw // 2 + 4, floor - 8), (cx + bw // 2, floor),
                           (cx - bw // 2, floor)])
            poly(s, body, [(cx - bw // 2 - 2, by), (cx + bw // 2 + 2, by), (cx + bw // 2 + 4, floor - 8),
                           (cx - bw // 2 - 4, floor - 8)])
            s.fill(trim, (cx - bw // 2 - 2, floor - 10, bw + 4, 3))              # bumper band
            rrect(s, shade(body), (cx - 4, by - 8, 8, 10), 1)                   # funnel
            s.fill(trim, (cx - 4, by - 8, 8, 3))
        elif shape == "saucer":
            ellipse(s, body, (cx - w // 2 + 2, floor - 12, w - 4, 12))
            for i in range(5):
                s.fill(trim, (cx - w // 2 + 6 + i * (w - 12) // 4, floor - 7, 3, 2))
            pygame.draw.ellipse(s, light(trim, 0.5), (cx - 13, floor - 30, 26, 24))   # glass dome
            pygame.draw.ellipse(s, OUT, (cx - 13, floor - 30, 26, 24), 1)
        else:
            poly(s, body, [(cx - bw // 2, floor - 3), (cx + bw // 2, floor - 3), (cx + bw // 2 - 3, by), (cx - bw // 2 + 3, by)])
            s.fill(shade(body), (cx - bw // 2 + 2, floor - 9, bw - 4, 4))
            if shape == "mower":
                rrect(s, trim, (cx - bw // 2 + 2, by - 6, bw - 4, 8), 2)          # grass bag
                pygame.draw.line(s, OUT, (cx - 6, by - 6), (cx - 6, by - 14), 2)  # handlebar
                pygame.draw.line(s, OUT, (cx + 6, by - 6), (cx + 6, by - 14), 2)
                pygame.draw.line(s, OUT, (cx - 7, by - 14), (cx + 7, by - 14), 3)
            elif shape == "buggy":
                pygame.draw.lines(s, OUT, False, [(cx - bw // 2 + 4, by + 2), (cx - bw // 2 + 6, by - 12),
                                                  (cx + bw // 2 - 6, by - 12), (cx + bw // 2 - 4, by + 2)], 3)
            elif shape == "kart":
                rrect(s, trim, (cx - bw // 2 - 2, by - 8, bw + 4, 5), 1)          # spoiler
                s.fill(OUT, (cx - 1, by - 3, 2, 4))
            elif shape == "trike":
                rrect(s, (90, 90, 100), (cx - 5, floor - 10, 10, 7), 2)           # rocket nozzle
                s.fill((255, 200, 60), (cx - 3, floor - 8, 6, 3))
        lights = (255, 240, 160) if front else (255, 80, 60)
        if shape not in ("saucer",):
            s.fill(OUT, (cx - bw // 2 + 2, floor - 7, 5, 4))
            s.fill(lights, (cx - bw // 2 + 3, floor - 6, 3, 2))
            s.fill(OUT, (cx + bw // 2 - 7, floor - 7, 5, 4))
            s.fill(lights, (cx + bw // 2 - 6, floor - 6, 3, 2))
        r = max(4, h // 4)
        hx, hy = cx + lean * (r // 2 + 1), by - r + 2
        if shape == "saucer":
            hy = floor - 20
        arms(s, hx, hy, r, racer, expr, view="face")
        head(s, hx, hy, r, racer, expr, view="face")
        return s
    return cached(("rear", racer.name, expr, lean, front, w, h), make)


def kart_side(racer, expr="normal", w=56, h=30):
    """Kart seen from its right side, facing right."""
    def make():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        body, trim, shape = racer.body, racer.trim, racer.shape
        floor = h - 2
        if shape == "boat":
            poly(s, body, [(4, floor - 14), (w - 2, floor - 14), (w - 8, floor), (8, floor)])
            s.fill(trim, (6, floor - 12, w - 12, 3))
        elif shape == "saucer":
            ellipse(s, body, (2, floor - 10, w - 4, 10))
            pygame.draw.ellipse(s, light(trim, 0.5), (w // 2 - 12, floor - 26, 24, 20))
        else:
            rrect(s, body, (8, floor - 14, w - 16, 10), 3)
            s.fill(shade(body), (10, floor - 8, w - 20, 3))
            for wx in (10, w - 20):
                circle(s, (60, 60, 70), (wx + 4, floor - 5), 5)
                pygame.draw.circle(s, (110, 110, 120), (wx + 4, floor - 5), 2)
            if shape == "kart":
                rrect(s, trim, (6, floor - 20, 8, 3), 1)
            elif shape == "trike":
                s.fill((255, 200, 60), (2, floor - 11, 6, 3))
        r = max(4, h // 4)
        head(s, w // 2 + 4, floor - 18 if shape != "saucer" else floor - 16, r, racer, expr, view="side")
        return s
    return cached(("side", racer.name, expr, w, h), make)


def portrait(racer, expr="normal", size=32):
    """Head and shoulders for menus and the HUD."""
    def make():
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        r = int(size * 0.28)
        cx, cy = size // 2, int(size * 0.48)
        rrect(s, racer.body, (size // 6, size - size // 4, size - size // 3, size // 4 + 2), 3)
        arms(s, cx, cy, r, racer, expr, view="face")
        head(s, cx, cy, r, racer, expr, view="face")
        return s
    return cached(("portrait", racer.name, expr, size), make)


def hit_stars(surf, cx, cy, t, r=10):
    """Three little stars circling a dizzy head."""
    for i in range(3):
        a = t * 0.25 + i * 2.1
        x, y = int(cx + math.cos(a) * r), int(cy - 2 + math.sin(a) * r * 0.4)
        pygame.draw.polygon(surf, (255, 230, 80), [(x, y - 3), (x + 1, y - 1), (x + 3, y), (x + 1, y + 1),
                                                   (x, y + 3), (x - 1, y + 1), (x - 3, y), (x - 1, y - 1)])


# ---------------------------------------------------------------------- items
def item_sprite(kind, size=1.0):
    """World sprite / HUD icon of an item. kind: banana, chicken, pie, gum, balloon, turbo, crate, splat."""
    def make():
        if kind == "banana":
            s = pygame.Surface((16, 12), pygame.SRCALPHA)
            pygame.draw.lines(s, OUT, False, [(2, 3), (5, 9), (11, 9), (14, 3)], 6)
            pygame.draw.lines(s, (250, 220, 60), False, [(2, 3), (5, 9), (11, 9), (14, 3)], 3)
            s.fill((120, 90, 30), (1, 1, 2, 3))
        elif kind == "chicken":
            s = pygame.Surface((18, 14), pygame.SRCALPHA)
            ellipse(s, (250, 210, 70), (1, 5, 13, 8))
            circle(s, (250, 210, 70), (13, 4), 3)
            s.fill((230, 70, 60), (12, 0, 3, 2))                 # comb
            poly(s, (255, 150, 40), [(16, 3), (18, 4), (16, 6)], outline=False)
            s.fill(OUT, (13, 3, 1, 1))
            pygame.draw.line(s, (255, 150, 40), (4, 12), (4, 14), 1)
        elif kind == "pie":
            s = pygame.Surface((16, 12), pygame.SRCALPHA)
            rrect(s, (190, 190, 200), (1, 6, 14, 5), 1)
            ellipse(s, (255, 250, 230), (1, 1, 14, 8))
            s.fill((230, 60, 70), (7, 1, 2, 2))
        elif kind == "gum":
            s = pygame.Surface((12, 10), pygame.SRCALPHA)
            ellipse(s, (255, 120, 190), (1, 2, 10, 7))
            s.fill(WHITE, (3, 3, 2, 1))
        elif kind == "balloon":
            s = pygame.Surface((12, 14), pygame.SRCALPHA)
            ellipse(s, (80, 160, 250), (1, 1, 10, 11))
            s.fill(WHITE, (3, 3, 2, 2))
            s.fill(OUT, (5, 12, 2, 2))
        elif kind == "pepper":
            s = pygame.Surface((12, 16), pygame.SRCALPHA)
            pygame.draw.lines(s, OUT, False, [(4, 4), (3, 9), (6, 14), (9, 12)], 7)
            pygame.draw.lines(s, (235, 50, 40), False, [(4, 4), (3, 9), (6, 14), (9, 12)], 4)
            s.fill((255, 150, 130), (3, 6, 1, 3))
            pygame.draw.line(s, (70, 160, 60), (4, 3), (7, 0), 2)
        elif kind == "shield":
            s = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(s, (120, 220, 255, 110), (8, 8), 7)
            pygame.draw.circle(s, (200, 245, 255), (8, 8), 7, 1)
            pygame.draw.circle(s, WHITE, (5, 5), 2)
        elif kind == "pogo":
            s = pygame.Surface((12, 16), pygame.SRCALPHA)
            pygame.draw.lines(s, OUT, False, [(6, 0), (6, 3), (2, 5), (10, 7), (2, 9), (10, 11), (6, 13)], 3)
            pygame.draw.lines(s, (200, 200, 210), False, [(6, 3), (2, 5), (10, 7), (2, 9), (10, 11), (6, 13)], 1)
            rrect(s, (230, 60, 50), (2, 13, 8, 3), 1)
            s.fill((230, 60, 50), (5, 0, 3, 3))
        elif kind == "magnet":
            s = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.lines(s, OUT, False, [(3, 1), (3, 8), (7, 12), (11, 8), (11, 1)], 6)
            pygame.draw.lines(s, (230, 60, 50), False, [(3, 1), (3, 8), (7, 12), (11, 8), (11, 1)], 3)
            s.fill((190, 190, 200), (2, 0, 4, 3))
            s.fill((190, 190, 200), (9, 0, 4, 3))
        elif kind == "crate":
            s = pygame.Surface((16, 16), pygame.SRCALPHA)
            rrect(s, (240, 150, 50), (1, 1, 14, 14), 2)
            pygame.draw.rect(s, (255, 210, 90), (3, 3, 10, 10), 1)
            pygame.draw.lines(s, OUT, False, [(5, 6), (6, 4), (10, 4), (11, 6), (8, 8), (8, 10)], 2)
            s.fill(OUT, (7, 12, 2, 2))
        elif kind == "splash":
            s = pygame.Surface((24, 10), pygame.SRCALPHA)
            for i in range(6):
                pygame.draw.circle(s, (120, 190, 255), (2 + i * 4, 8 - (i % 3) * 3), 2)
        else:                                                   # pie splat left on a kart
            s = pygame.Surface((14, 10), pygame.SRCALPHA)
            for i in range(5):
                pygame.draw.circle(s, (255, 250, 230), (2 + i * 2 + (i % 2), 3 + (i % 3) * 2), 3)
        if size != 1.0:
            s = pygame.transform.scale(s, (max(1, int(s.get_width() * size)), max(1, int(s.get_height() * size))))
        return s
    return cached(("item", kind, size), make)


def flames(surf, x, y, t, size=1.0):
    """Pepper exhaust: three jittering fire blobs around (x, y)."""
    for i, (col, r) in enumerate((((255, 90, 30), 5), ((255, 170, 40), 3), ((255, 240, 150), 2))):
        j = (t * 7 + i * 5) % 5 - 2
        pygame.draw.circle(surf, col, (int(x + j * size), int(y + (i - 1) * 2 * size)), max(1, int(r * size)))


def bubble(d):
    """Translucent shield bubble of diameter d."""
    def make():
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        pygame.draw.circle(s, (120, 220, 255, 70), (d // 2, d // 2), d // 2)
        pygame.draw.circle(s, (210, 245, 255, 180), (d // 2, d // 2), d // 2, 1)
        pygame.draw.circle(s, (255, 255, 255, 160), (d // 3, d // 3), max(1, d // 8))
        return s
    return cached(("bubble", d), make)


def shadow(w, h):
    def make():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 90), (0, 0, w, h))
        return s
    return cached(("shadow", w, h), make)
