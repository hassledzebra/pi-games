"""The two cameras and the HUD.

Mode7View (the default "chase" camera) is built for a Pi 3: the world is
pre-rotated into 64 half-resolution copies at load time (world.ensure_rotations),
so a frame never rotates anything; it picks the copy nearest the kart's heading.
The ground is drawn into a half-size buffer (192x54 for a split view) as ~10
horizontal strips - one subsurface + transform.scale each, thin near the kart
and taller far away - then scaled x2 straight into the view in one call. Hills
are per-strip vertical offsets: each strip sits at the projected height of the
road that far ahead, strips are drawn near-to-far so a crest hides what is
behind it, and the sky line follows the kart's pitch. Sprites, the player's
kart and the HUD are drawn at full resolution on top.

TopDownView (the "overhead" camera): one blit of a window of the full world
plus pre-rotated sprites. Both expose project(): world (x, y, altitude) ->
screen (x, y, scale) or None when behind the camera or hidden by a crest.
"""
import math
import random
from bisect import bisect_left

import pygame

from engine import text

from . import art
from .data import ITEMS, LAPS
from .kart import DRIFT_MINI, DRIFT_SUPER, norm_angle
from .world import WORLD

WHITE = (255, 255, 255)
YELLOW = (255, 220, 60)
SIZES = (6, 8, 11, 14, 18, 22, 28, 34, 42, 50, 60)      # sprite widths kept in the scale cache
_scaled = {}


KEY = (255, 0, 255)


def keyed(s):
    """Opaque colour-keyed copy of a hard-edged alpha sprite: blits ~30% cheaper on a Pi."""
    k = pygame.Surface(s.get_size()).convert()
    k.fill(KEY)
    k.blit(s, (0, 0))
    k.set_colorkey(KEY)
    return k


def scaled(key, base, width):
    """`base` surface scaled to the nearest cached width (keeps aspect), colour-keyed."""
    w = min(SIZES, key=lambda s: abs(s - width))
    k = (key, w)
    s = _scaled.get(k)
    if s is None:
        s = _scaled[k] = keyed(pygame.transform.scale(base, (w, max(1, int(base.get_height() * w / base.get_width())))))
    return s


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


class Mode7View:
    def __init__(self, w, h, world, angles=64, q=1.0):
        self.w, self.h, self.world = w, h, world
        self.F = 120.0 * w / 384  # focal length in px: horizontal fov ~ 116 degrees at any canvas size
        self.q = q                                           # ground buffer px per screen px (1 = full res)
        self.bw, self.bh = int(w * q), int(h * q)
        self.cam_h = 15.0 * h / 108
        self.horizon0 = int(h * 0.37)                        # full-res px
        self.hb0 = int(self.horizon0 * q)
        self.buf = pygame.Surface((self.bw, self.bh)).convert()
        self.ground = world.theme["ground"]
        self.fog = mix(world.theme["sky"][1], self.ground, 0.55)
        self.band = (mix(world.theme["sky"][1], self.ground, 0.25), mix(world.theme["sky"][1], self.ground, 0.4))
        self.angles = world.ensure_rotations(angles)
        self.step = 360.0 / self.angles
        self.smooth = True                                   # average far strips instead of picking texels
        self.set_lod(0)
        self.sky = self.paint_sky()
        self.pitch = 0.0
        self.vis = []
        self.horizon = self.horizon0
        self.heading = 0.0
        self.t = 0
        self.dests = {}
        self.blits, self.marks = [], []

    def paint_sky(self):
        bw, hb0 = self.w // 2, self.horizon0 // 2           # painted at half res, then scaled to the buffer
        th = self.world.theme
        s = pygame.Surface((bw, hb0 + 40)).convert()
        top, bot = th["sky"]
        for y in range(hb0 + 40):
            s.fill(mix(top, bot, min(1.0, y / (hb0 + 20))), (0, y, bw, 1))
        rng = random.Random(len(self.world.path))
        hx = -10
        while hx < bw + 20:                                  # distant hills / skyline
            r = rng.randint(7, 16)
            if self.world.track.theme == "neon":
                pygame.draw.rect(s, th["hills"], (hx, hb0 + 22 - r, rng.randint(4, 8), r + 10))
                for yy in range(hb0 + 24 - r, hb0 + 22, 2):
                    if rng.random() < 0.5:
                        s.fill((255, 230, 120), (hx + 1, yy, 1, 1))
            else:
                pygame.draw.circle(s, th["hills"], (hx, hb0 + 23), r)
            hx += rng.randint(9, 20)
        if self.world.track.theme == "harbor":
            for cx in (20, 75, 150):
                pygame.draw.rect(s, (40, 40, 60), (cx, hb0 + 10, 2, 13))
                pygame.draw.rect(s, (40, 40, 60), (cx - 7, hb0 + 10, 15, 1))
        if self.q != 0.5:
            s = pygame.transform.scale(s, (self.bw, int((hb0 + 40) * 2 * self.q)))
        return s

    # strip heights near -> far as relative weights: tall strips near the kart (where texels are
    # stretched anyway), thin ones far away where the road's shape matters
    STRIPS = (None, [1] * 17, [8, 7, 5, 5, 4, 3, 2])

    def set_lod(self, level):
        """Strip table, nearest first: (top row in the buffer, distance ahead, distance in centreline
        points, distance in half-res px, strip width in half-res px, buffer px per half-res px,
        buffer rows per world px of height). Level 0: one strip per buffer row (true mode-7);
        1: 17 thin strips; 2: 7 tall ones."""
        rows = self.bh - self.hb0
        weights = self.STRIPS[level] or [1] * rows
        total = float(sum(weights))
        heights = [max(1, int(round(w / total * rows))) for w in weights]
        heights[-1] += rows - sum(heights)
        q = self.q
        self.strips, y = [], self.bh
        for hh in heights:
            y -= hh
            yt = max(y, self.hb0)
            dy = yt / q - self.horizon0 + 6
            dist = self.F * self.cam_h / dy
            ww = dist * self.w / self.F * 0.5
            self.strips.append((yt, dist, dist / 9.0, dist * 0.5, ww, 2 * q * self.F / dist, q * self.F / dist))
        self.dists = [st[1] for st in self.strips]
        self.lod = level

    # -- camera -------------------------------------------------------------
    def follow(self, kart):
        world = self.world
        if world.rotations is None or world.n_rot != self.angles:      # rebuilt or dropped by another race
            self.angles = world.ensure_rotations(self.angles)
            self.step = 360.0 / self.angles
        heading = (kart.heading + 180) % 360 if kart.look_back else kart.heading
        self.ai = int(round(heading / self.step)) % self.angles
        heading = self.ai * self.step                        # the ground is only pre-rotated this finely
        a = math.radians(heading)
        fx, fy = math.sin(a), -math.cos(a)
        self.heading = heading
        self.fwd = (fx, fy)
        self.cam = (kart.x - fx * 28, kart.y - fy * 28)
        self.cam_alt = kart.alt
        self.kart = kart
        # pitch follows the road slope under the kart (smoothed); the sky line moves with it
        target = 0.0 if kart.air else self.world.slope_at(kart.prog) * (-1 if kart.look_back else 1)
        self.pitch += (max(-0.3, min(0.3, target)) - self.pitch) * 0.15
        bob = kart.bounce if kart.landed else 0.0
        self.horizon = self.horizon0 + int(self.F * self.pitch) + int(bob)

    def project(self, x, y, alt=None):
        """World point -> (sx, sy, k) with k = px per world px, or None if behind/hidden."""
        dx, dy = x - self.cam[0], y - self.cam[1]
        fx, fy = self.fwd
        fwd = dx * fx + dy * fy
        if fwd < 8 or fwd > 420:
            return None
        side = dx * -fy + dy * fx
        k = self.F / fwd
        dh = (alt if alt is not None else self.world.height_at(self.kart.prog + fwd / 9.0)) - self.cam_alt
        sy = self.horizon + k * (self.cam_h - dh)
        if self.vis:                                         # hidden behind a crest?
            v = self.vis[min(len(self.vis) - 1, bisect_left(self.dists, fwd))]
            if v is None or sy > v + 4:
                return None
        return self.w / 2 + side * k, sy, k

    # -- ground -------------------------------------------------------------
    def draw_ground(self, view):
        world, buf, bw, bh = self.world, self.buf, self.bw, self.bh
        rot, rcx, rcy = world.rotations[self.ai]
        rw, rh = rot.get_size()
        a = math.radians(self.heading)
        c, s = math.cos(a), math.sin(a)
        offx, offy = self.cam[0] * 0.5 - world.rot_cx, self.cam[1] * 0.5 - world.rot_cy
        ccx = rcx + offx * c + offy * s
        ccy = rcy - offx * s + offy * c
        q = self.q
        hb = int(self.horizon * q)
        buf.blit(self.sky, (0, hb - self.hb0))
        if hb < bh:
            buf.fill(self.ground, (0, max(0, hb), bw, bh - max(0, hb)))
        scale = pygame.transform.scale
        smoothscale = pygame.transform.smoothscale if self.smooth else scale
        subsurface = rot.subsurface
        blit = buf.blit
        dests = self.dests
        prog, cam_alt, cam_h = self.kart.prog, self.cam_alt, self.cam_h
        hts, n = world.heights, world.n
        maxy = bh                                            # painter's limit: lowest free buffer row
        vis = []
        prev_dh = 0.0
        for (yt, dist, dp, dhalf, ww, inv, ks) in self.strips:      # near to far
            p = prog + dp
            i = int(p)
            f = p - i
            dh = hts[i % n] * (1 - f) + hts[(i + 1) % n] * f - cam_alt
            y = int(hb + (cam_h - dh) * ks)
            if y >= maxy:                                    # hidden by nearer, higher ground
                vis.append(None)
                prev_dh = dh
                continue
            vis.append(y / q)
            hgt = maxy - y
            srow = int(ccy - dhalf)
            sx = ccx - ww * 0.5
            x_a = int(sx) if sx > 0 else 0
            x_b = int(sx + ww)
            if x_b > rw:
                x_b = rw
            if 0 <= srow < rh and x_b - x_a >= 2:
                size = (int((x_b - x_a) * inv) + 1, hgt)
                dest = dests.get(size)
                if dest is None:                             # reuse strip surfaces: no per-frame allocation
                    dest = dests[size] = pygame.Surface(size).convert()
                # far strips squeeze several texels into one pixel: average them (smoothscale) so the
                # distance reads as a road rather than as noise; near strips stretch, so plain scale
                sc = smoothscale if inv < 0.7 else scale
                blit(sc(subsurface((x_a, srow, x_b - x_a, 1)), size, dest), (int((x_a - sx) * inv), y))
                slope = dh - prev_dh
                if slope > 0.6:                              # facing uphill: lighter
                    buf.fill((30, 30, 30), (0, y, bw, hgt), special_flags=pygame.BLEND_RGB_ADD)
                elif slope < -0.6:
                    buf.fill((30, 30, 30), (0, y, bw, hgt), special_flags=pygame.BLEND_RGB_SUB)
            prev_dh = dh
            maxy = y
        if maxy > hb + 2:                                    # beyond the last strip: haze
            buf.fill(self.fog, (0, max(0, hb + 2), bw, maxy - max(0, hb + 2)))
        if 0 <= hb < bh - 1:
            buf.fill(self.band[0], (0, hb, bw, 1))
            buf.fill(self.band[1], (0, hb + 1, bw, 1))
        if q == 1.0:
            view.blit(buf, (0, 0))
        else:
            scale(buf, (self.w, self.h), view)
        self.vis = vis

    # -- sprites ------------------------------------------------------------
    def draw_sprites(self, view, karts, items, crates, ghost=None):
        """Project everything, sort far-to-near, blit in one call. The blit list is kept so a
        non-refresh frame (frozen camera) can repeat it without projecting again."""
        t = self.t
        cam_kart = self.kart
        cx, cy = self.cam
        project = self.project
        out = []
        for k in karts:
            if k is not cam_kart and abs(k.x - cx) < 430 and abs(k.y - cy) < 430:
                pr = project(k.x, k.y, k.alt)
                if pr:
                    out.append((pr, "kart", k))
                    for d in k.dust:
                        pr = project(d[0], d[1])
                        if pr:
                            out.append((pr, "dust", d))
        for d in cam_kart.dust:
            pr = project(d[0], d[1])
            if pr:
                out.append((pr, "dust", d))
        if ghost is not None:
            pr = project(ghost[0], ghost[1], ghost[3])
            if pr:
                out.append((pr, "ghost", ghost))
        for it in items:
            if abs(it.x - cx) < 430 and abs(it.y - cy) < 430:
                pr = project(it.x, it.y, it.alt + it.z)
                if pr:
                    out.append((pr, "item", it))
        for c in crates:
            if c.active and abs(c.x - cx) < 430 and abs(c.y - cy) < 430:
                pr = project(c.x, c.y)
                if pr:
                    out.append((pr, "crate", c))
        if len(out) > 1:
            out.sort(key=lambda e: e[0][2])                  # far (small k) first
        blits = []
        marks = []
        for (sx, sy, k), kind, obj in out:
            if kind == "kart" or kind == "ghost":
                if kind == "ghost":
                    racer, heading, expr = obj[4], obj[2], "normal"
                else:
                    racer, heading, expr = obj.racer, obj.heading, obj.expr
                rel = norm_angle(heading - self.heading)
                if abs(rel) < 60:
                    base = art.kart_rear(racer, expr)
                    key = ("rear", racer.name, expr)
                elif abs(rel) > 120:
                    base = art.kart_rear(racer, expr, front=True)
                    key = ("front", racer.name, expr)
                else:
                    base = art.kart_side(racer, expr)
                    key = ("side", racer.name, expr)
                    if rel < 0:
                        base = art.cached(("sideflip", racer.name, expr), lambda b=base: pygame.transform.flip(b, True, False))
                        key = ("sidef", racer.name, expr)
                spr = scaled(key, base, 24 * k)
                if kind == "ghost":
                    spr = art.cached(("ghost",) + key + (spr.get_width(),), lambda s=spr: _translucent(s))
                x, y = int(sx - spr.get_width() / 2), int(sy - spr.get_height())
                if spr.get_width() >= 14:
                    sh = art.shadow(spr.get_width(), max(2, spr.get_width() // 4))
                    blits.append((sh, (x, int(sy - sh.get_height() / 2))))
                blits.append((spr, (x, y)))
                if kind == "kart":
                    marks.append((obj, sx, sy, k, spr))
            elif kind == "item":
                spr = scaled(("item", obj.kind), art.item_sprite(obj.kind), 12 * k)
                if obj.kind == "chicken" and (t // 4) % 2:
                    spr = art.cached(("chickflip", spr.get_width()), lambda s=spr: pygame.transform.flip(s, False, True))
                blits.append((spr, (int(sx - spr.get_width() / 2), int(sy - spr.get_height()))))
            elif kind == "crate":
                spr = scaled(("crate",), art.item_sprite("crate"), 14 * k)
                bob = int(math.sin(t * 0.15 + obj.x) * 2 * k)
                blits.append((spr, (int(sx - spr.get_width() / 2), int(sy - spr.get_height() - 3 * k - bob))))
            else:
                r = max(1, int(3 * k * obj[2] / 18))
                blits.append((dust_dot(r), (int(sx) - r, int(sy) - r)))
        self.blits, self.marks, self.mark_t = blits, marks, t
        self.repeat_sprites(view)

    def repeat_sprites(self, view):
        if self.blits:
            view.blits(self.blits, 0)
        for (obj, sx, sy, k, spr) in self.marks:
            if obj.pepper or obj.shield or obj.hit_t or obj.stuck:
                self.kart_extras(view, obj, sx, sy, k, spr, self.mark_t)

    def kart_extras(self, view, k, sx, sy, kk, spr, t):
        """Flames, bubble, dizzy stars, gum; animated with the sprite list's own frame counter."""
        if k.pepper:
            art.flames(view, sx, sy - spr.get_height() * 0.3, t, kk * 1.2)
        if k.shield:
            b = art.bubble(max(8, int(spr.get_width() * 1.3)))
            view.blit(b, (int(sx - b.get_width() / 2), int(sy - spr.get_height() * 0.6 - b.get_height() / 2)))
        if k.hit_t:
            art.hit_stars(view, sx, sy - spr.get_height(), t, max(4, int(spr.get_width() * 0.35)))
        if k.stuck:
            pygame.draw.line(view, (255, 120, 190), (int(sx - 4 * kk), int(sy)), (int(sx + 4 * kk), int(sy - 6 * kk)), 2)

    def draw_player(self, view, k):
        """The view's own kart, big, bottom centre."""
        w, h = self.w, self.h
        big_w = int(w * 0.15)
        big_h = int(big_w * 36 / 56)
        lean = int(round(k.lean))
        base = art.cached(("bigkart", k.racer.name, k.expr, lean, k.look_back, big_w),
                          lambda: keyed(art.kart_rear(k.racer, k.expr, lean=lean, front=k.look_back, w=big_w, h=big_h)))
        lift = int(k.z * 4.3) + int(k.bounce)
        shake = int(math.sin(k.frame * 1.7) * 2) if k.shake else 0
        x = w // 2 - big_w // 2 + shake + int(k.lean * (3 if k.drift else 1))
        y = h - big_h - 2 - lift
        if self.lod == 0:                                    # soft shadow (skipped on a Pi)
            sh = art.shadow(big_w, big_w // 4)
            view.blit(sh, (w // 2 - big_w // 2, h - sh.get_height() // 2 - 4))
        if k.drift and k.drift_t > 10:                       # tyre sparks
            col = WHITE if k.drift_t >= DRIFT_SUPER else ((80, 230, 255) if k.drift_t >= DRIFT_MINI else (255, 160, 60))
            for sx in (-1, 1):
                for i in range(3):
                    px = w // 2 + sx * (big_w // 2 - 4) + ((k.frame * 5 + i * 7) % 9) * -sx
                    py = h - 4 - (k.frame * 3 + i * 5) % 7
                    view.fill(col, (px, py, 2, 2))
        if k.pepper:
            for sx in (-1, 1):
                art.flames(view, w // 2 + sx * big_w * 0.22, h - 6 - lift, k.frame, 1.3)
        view.blit(base, (x, y))
        if k.shield:
            b = art.bubble(int(big_w * 1.35))
            view.blit(b, (w // 2 - b.get_width() // 2, y + big_h // 2 - b.get_height() // 2))
        if k.hit_t:
            art.hit_stars(view, w // 2, y, k.frame, big_w // 3)
        if k.stuck:
            for i in range(3):
                pygame.draw.line(view, (255, 120, 190), (w // 2 - 10 + i * 10, h - 2), (w // 2 - 6 + i * 10, y + big_h - 8), 2)

    TOP = 17              # buffer rows above which nothing volatile is drawn (fixed HUD boxes, sky)

    def draw(self, view, kart, karts, items, crates, ghost=None, refresh=True, full=True):
        """refresh=False reuses the last ground, camera and sprite list (a split view on a Pi
        refreshes every other frame; the player's kart and the HUD still move every frame).
        full=False then restores only the rows below the fixed HUD boxes."""
        self.t += 1
        if refresh or not self.vis:
            self.follow(kart)
            self.draw_ground(view)
            self.draw_sprites(view, karts, items, crates, ghost)
        else:
            if full:
                pygame.transform.scale(self.buf, (self.w, self.h), view)
            else:
                top = self.TOP
                pygame.transform.scale(self.buf.subsurface((0, top, self.bw, self.bh - top)),
                                       (self.w, self.h - 2 * top), view.subsurface((0, 2 * top, self.w, self.h - 2 * top)))
            self.repeat_sprites(view)
        self.draw_player(view, kart)


def dust_dot(r):
    def make():
        s = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
        pygame.draw.circle(s, (200, 190, 170), (r, r), r)
        return keyed(s)
    return art.cached(("dust", r), make)


def _translucent(s):
    t = s.copy()
    t.set_alpha(110)
    return t


class TopDownView:
    """Overhead camera: a window of the world, north up, kart centred and nudged ahead."""

    def __init__(self, w, h, world):
        self.w, self.h, self.world = w, h, world
        self.t = 0
        self.x0 = self.y0 = 0
        self.lod = 0

    def set_lod(self, level):
        self.lod = level

    def follow(self, kart):
        fx, fy = kart.dir
        self.kart = kart
        cx, cy = kart.x + fx * 24, kart.y + fy * 24
        self.x0 = max(0, min(WORLD - self.w, int(cx - self.w / 2)))
        self.y0 = max(0, min(WORLD - self.h, int(cy - self.h / 2)))

    def project(self, x, y, alt=None):
        sx, sy = x - self.x0, y - self.y0
        if -30 < sx < self.w + 30 and -30 < sy < self.h + 30:
            return sx, sy, 1.0
        return None

    def draw(self, view, kart, karts, items, crates, ghost=None, refresh=True, full=True):
        self.t += 1
        self.follow(kart)
        view.blit(self.world.surface, (0, 0), (self.x0, self.y0, self.w, self.h))
        for c in crates:
            if c.active:
                pr = self.project(c.x, c.y)
                if pr:
                    spr = art.item_sprite("crate")
                    view.blit(spr, (int(pr[0] - 8), int(pr[1] - 8 - math.sin(self.t * 0.15 + c.x) * 2)))
        for it in items:
            pr = self.project(it.x, it.y)
            if pr:
                spr = art.item_sprite(it.kind)
                if it.z > 0:
                    sh = art.shadow(10, 5)
                    view.blit(sh, (int(pr[0] - 5), int(pr[1] - 2)))
                view.blit(spr, (int(pr[0] - spr.get_width() / 2), int(pr[1] - spr.get_height() / 2 - it.z * 2)))
        for k in karts:
            for d in k.dust:
                pr = self.project(d[0], d[1])
                if pr:
                    pygame.draw.circle(view, (200, 190, 170), (int(pr[0]), int(pr[1])), max(1, d[2] // 6))
        if ghost is not None:
            pr = self.project(ghost[0], ghost[1])
            if pr:
                spr = art.kart_top_rotations(ghost[4])[int(ghost[2] / 360 * 32) % 32]
                g = art.cached(("ghosttop", ghost[4].name, int(ghost[2] / 360 * 32) % 32), lambda s=spr: _translucent(s))
                view.blit(g, (int(pr[0] - g.get_width() / 2), int(pr[1] - g.get_height() / 2)))
        for k in sorted(karts, key=lambda q: q.z):
            pr = self.project(k.x, k.y)
            if not pr:
                continue
            spr = art.kart_top_rotations(k.racer, k.expr)[int(k.heading / 360 * 32) % 32]
            sh = art.shadow(18, 12)
            view.blit(sh, (int(pr[0] - 9), int(pr[1] - 5)))
            scale = 1.0 + 0.006 * k.z + 0.001 * (k.alt - k.z)      # higher = a little bigger
            if scale > 1.02:
                spr = pygame.transform.scale(spr, (int(spr.get_width() * scale), int(spr.get_height() * scale)))
            x, y = int(pr[0] - spr.get_width() / 2), int(pr[1] - spr.get_height() / 2 - k.z * 2)
            if k.pepper:
                fx, fy = k.dir
                art.flames(view, pr[0] - fx * 14, pr[1] - fy * 14, self.t, 1.0)
            view.blit(spr, (x, y))
            if k.shield:
                b = art.bubble(34)
                view.blit(b, (int(pr[0] - 17), int(pr[1] - 17 - k.z * 2)))
            if k.hit_t:
                art.hit_stars(view, pr[0], pr[1] - 12, self.t, 10)
            if k.drift and k.drift_t > 10:
                col = WHITE if k.drift_t >= DRIFT_SUPER else ((80, 230, 255) if k.drift_t >= DRIFT_MINI else (255, 160, 60))
                fx, fy = k.dir
                pygame.draw.circle(view, col, (int(pr[0] - fx * 9), int(pr[1] - fy * 9)), 2)


# ---------------------------------------------------------------------- HUD
def opaque(w, h, draw):
    """A square HUD box drawn once; opaque, so it blits as a plain copy."""
    s = pygame.Surface((w, h)).convert()
    draw(s)
    return s


def hud_top(lap, rank):
    """Lap and position boxes as one opaque block."""
    def make(s):
        s.fill((10, 10, 20))
        text.draw(s, "LAP %d/%d" % (min(LAPS, lap), LAPS), 14, WHITE, (23, 1))
        s.fill((24, 22, 40), (0, 15, 46, 1))
        text.draw(s, "%d" % (rank + 1), 22, YELLOW, (11, 16))
        text.draw(s, ("ST", "ND", "RD", "TH", "TH", "TH")[rank], 10, YELLOW, (28, 26), align="right")
    return art.cached(("hudtop", lap, rank), lambda: opaque(46, 36, make))


def hud_bottom(racer, expr):
    """Framed portrait, name badge and empty speed bar as one opaque block."""
    def make(s):
        s.fill((10, 10, 20))
        s.blit(art.portrait(racer, expr, 24), (1, 6))
        s.fill(racer.body, (26, 14, 62, 11))
        pygame.draw.rect(s, art.OUT, (26, 14, 62, 11), 1)
        text.draw(s, racer.name, 11, WHITE, (57, 14))
        s.fill(art.OUT, (26, 25, 62, 9))
        s.fill((60, 60, 80), (27, 26, 60, 7))
    return art.cached(("hudbottom", racer.name, expr), lambda: opaque(88, 36, make))


def hud_item(kind):
    """Item box with icon; kind None = empty box."""
    def make(s):
        s.fill((40, 34, 70))
        pygame.draw.rect(s, art.OUT, (0, 0, 20, 20), 1)
        if kind:
            ic = art.item_sprite(kind)
            s.blit(ic, (10 - ic.get_width() // 2, 10 - ic.get_height() // 2))
    return art.cached(("huditem", kind), lambda: opaque(20, 20, make))


def draw_hud(view, kart, rank, total, t, finished_rank=None, countdown=None, timer=None):
    w, h = view.get_size()
    col = kart.racer.body
    view.blit(hud_top(kart.lap, rank), (2, 2))
    view.blit(hud_bottom(kart.racer, "win" if finished_rank is not None and finished_rank < 3 else kart.expr), (2, h - 38))
    frac = abs(kart.speed) / (kart.top * 1.45)
    bar = WHITE if kart.drift_t >= DRIFT_SUPER else ((80, 230, 255) if kart.drift_t >= DRIFT_MINI else
                                                     ((255, 120, 40) if kart.boost or kart.pepper else col))
    view.fill(bar, (29, h - 10, int(60 * min(1.0, frac)), 7))
    if t % 4 == 0 or not hasattr(kart, "hud_speed"):
        kart.hud_speed = int(abs(kart.speed) * 20) * 3      # steps of 3 keep the text cache small
    text.draw(view, "%d" % kart.hud_speed, 12, WHITE, (92, h - 12), align="left")
    if kart.item == "magnet":
        view.blit(hud_item("magnet"), (w - 22 + int(math.sin(t * 0.3) * 2), 2))
    else:
        view.blit(hud_item(kart.item), (w - 22, 2))
    if kart.item:
        text.draw(view, ITEMS[kart.item]["label"], 10, YELLOW, (w - 2, 23), align="right")
    volatile = timer is not None or countdown is not None or finished_rank is not None or kart.pie > 0
    if timer is not None:
        text.draw(view, fmt_time(timer), 14, WHITE, (w - 26, 3), align="right")
    # messages
    if countdown is not None:
        if countdown > 0:
            text.draw(view, "%d" % countdown, 40, YELLOW, (w // 2, h // 2 - 24), shadow=(200, 40, 40))
        else:
            text.draw(view, "GO!", 40, (80, 255, 120), (w // 2, h // 2 - 24), shadow=(20, 80, 40))
    elif finished_rank is not None:
        text.draw(view, "FINISH!", 26, YELLOW, (w // 2, h // 2 - 26), shadow=(200, 40, 40))
        text.draw(view, "%d%s place" % (finished_rank + 1, ("st", "nd", "rd", "th", "th", "th")[finished_rank]), 16,
                  WHITE, (w // 2, h // 2))
    elif kart.wrong_way:
        volatile = True
        if (t // 20) % 2:
            text.draw(view, "WRONG WAY", 18, (255, 90, 70), (w // 2, h // 2 - 20))
    elif kart.lap == LAPS and kart.frame - kart.lap_start < 90:
        volatile = True
        if (t // 10) % 2:
            text.draw(view, "FINAL LAP", 18, YELLOW, (w // 2, h // 2 - 20))
    if kart.pie:                                             # cream pie on the lens, wiped off over 2 s
        n = int(7 * kart.pie / 120) + 1
        for i in range(n):
            bx, by = (i * 97 + 31) % w, (i * 61 + 17) % h
            r = 14 + (i * 7) % 12
            pygame.draw.circle(view, (255, 250, 230), (bx, by), r)
            pygame.draw.circle(view, (240, 225, 190), (bx + 3, by + 3), r // 2)
    return volatile


def draw_minimap(surf, world, karts, pos, t=0):
    """The map with the karts' dots; the dots are refreshed every 4th frame."""
    mm = getattr(world, "minimap_live", None)
    if mm is None or t % 4 == 0:
        if mm is None:
            mm = world.minimap_live = world.minimap.copy()
        mm.blit(world.minimap, (0, 0))
        k = world.minimap_scale
        for q in karts:
            x, y = 3 + q.x * k, 3 + q.y * k
            mm.fill(art.OUT, (x - 2, y - 2, 5, 5))
            mm.fill(q.racer.body, (x - 1, y - 1, 3, 3))
    surf.blit(mm, pos)


def fmt_time(frames):
    s = frames / 60.0
    return "%d:%05.2f" % (int(s // 60), s % 60)
