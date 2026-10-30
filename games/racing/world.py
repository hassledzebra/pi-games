"""A track turned into a world: the centreline, its height profile, the painted
ground (full and half resolution), a coarse surface-type grid for the physics,
the minimap, and where the crates, boost pads and start grid are.

Everything here is built once per track (about 0.1 s on a PC, ~2 s on a Pi 3)
and then only read, so a race frame never paints anything but sprites.
"""
import math
import random

import pygame

from .art import OUT, shade, light
from .data import CRATE_RESPAWN, WORLD

SPACING = 9.0             # px between centreline points (progress unit)
GRASS, ROAD, KERB, WALL, ICE, LAVA, BOOST = range(7)
GRID = 256                # surface grid cells per side (4x4 px each)
G = WORLD // GRID

THEMES = {
    # ground, ground2, road, kerb a, kerb b, lane, barrier, sky top, sky bottom, hills
    "harbor": dict(ground=(70, 140, 60), ground2=(62, 128, 54), road=(80, 80, 90), kerb=((200, 60, 50), (235, 235, 235)),
                   lane=(200, 200, 190), barrier=(150, 110, 70), sky=((60, 120, 210), (160, 210, 240)), hills=(70, 110, 150)),
    "cinder": dict(ground=(96, 72, 62), ground2=(84, 62, 54), road=(58, 54, 62), kerb=((230, 120, 40), (40, 30, 34)),
                   lane=(170, 150, 140), barrier=(60, 50, 50), sky=((90, 40, 50), (240, 140, 60)), hills=(70, 40, 45)),
    "frost": dict(ground=(226, 236, 246), ground2=(208, 222, 238), road=(120, 125, 140), kerb=((60, 120, 200), (245, 245, 255)),
                  lane=(220, 225, 235), barrier=(90, 100, 120), sky=((120, 150, 200), (220, 230, 245)), hills=(170, 190, 215)),
    "neon": dict(ground=(42, 40, 62), ground2=(36, 34, 54), road=(70, 70, 92), kerb=((255, 60, 200), (60, 240, 255)),
                 lane=(240, 220, 120), barrier=(90, 80, 120), sky=((16, 10, 40), (120, 50, 110)), hills=(30, 22, 50)),
    "orchard": dict(ground=(104, 172, 72), ground2=(92, 158, 64), road=(142, 120, 88), kerb=((250, 250, 240), (120, 80, 50)),
                    lane=(200, 180, 150), barrier=(140, 100, 60), sky=((80, 150, 230), (200, 230, 250)), hills=(80, 140, 90)),
}

# hills per theme: (position 0..1 along the lap, height px, half-width 0..1). Short, tall bumps are jump crests.
HILLS = {
    "harbor": [(0.18, 14, 0.05), (0.42, 22, 0.08), (0.46, 12, 0.012), (0.72, 18, 0.07), (0.9, 8, 0.03)],
    "cinder": [(0.1, 30, 0.06), (0.3, 40, 0.09), (0.47, 24, 0.013), (0.6, 35, 0.08), (0.8, 28, 0.05), (0.84, 12, 0.01)],
    "frost": [(0.15, 36, 0.08), (0.33, 20, 0.014), (0.52, 44, 0.1), (0.7, 26, 0.04), (0.88, 30, 0.06)],
    "neon": [(0.14, 16, 0.025), (0.15, 8, 0.01), (0.4, 24, 0.05), (0.5, 18, 0.02), (0.78, 20, 0.03), (0.82, 14, 0.02)],
    "orchard": [(0.25, 18, 0.08), (0.42, 14, 0.013), (0.75, 20, 0.08)],
}


def catmull(points, per=40):
    out = []
    n = len(points)
    for i in range(n):
        p0, p1, p2, p3 = points[(i - 1) % n], points[i], points[(i + 1) % n], points[(i + 2) % n]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    return out


def resample(dense, spacing):
    """Points every `spacing` px along a closed polyline."""
    out, carry = [dense[0]], 0.0
    for a, b in zip(dense, dense[1:] + dense[:1]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        pos = spacing - carry
        while pos < seg:
            k = pos / seg
            out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            pos += spacing
        carry = seg - (pos - spacing)
    if math.hypot(out[-1][0] - out[0][0], out[-1][1] - out[0][1]) < spacing * 0.5:
        out.pop()
    return out


class World:
    def __init__(self, track, with_hills=True):
        self.track = track
        self.theme = THEMES[track.theme]
        self.road_w = track.road_w
        self.path = resample(catmull(track.points), SPACING)
        self.n = len(self.path)
        n = self.n
        # unit normals (left of travel) per point, and direction
        self.dirs, self.normals = [], []
        for i in range(n):
            a, b = self.path[i - 1], self.path[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dy) or 1
            self.dirs.append((dx / d, dy / d))
            self.normals.append((-dy / d, dx / d))
        # height profile along the lap
        self.heights = [0.0] * n
        if with_hills:
            for (pos, amp, hw) in HILLS[track.theme]:
                for i in range(n):
                    u = (i / n - pos + 0.5) % 1.0 - 0.5
                    self.heights[i] += amp * math.exp(-(u * u) / (2 * hw * hw))
        self.slopes = [(self.heights[(i + 1) % n] - self.heights[i - 1]) / (2 * SPACING) for i in range(n)]
        self.max_height = max(self.heights) or 1.0
        # painted ground
        self.surface = self.paint()
        self.half = pygame.transform.scale(self.surface, (WORLD // 2, WORLD // 2)).convert()
        self.grid = self.build_grid()
        self.minimap = self.paint_minimap()
        self.rotations = None
        # crates and boost pads in world coordinates
        self.crates = []
        for idx in track.crates:
            for off in (-14, 0, 14):
                self.crates.append(Crate(self.offset(idx, off), idx))
        self.boost_pads = [(self.offset(i, off), i) for i, off in track.boosts]

    # -- pre-rotated copies for the mode-7 camera ----------------------------
    def ensure_rotations(self, n=64):
        """n half-resolution copies of the track area, rotated in 360/n steps, in the display
        format (about 80 MB for 64, ~1 s on a Pi 3). Only the track being raced keeps them."""
        if getattr(self, "rotations", None) and self.n_rot >= n:
            return self.n_rot
        xs = [p[0] for p in self.path]
        ys = [p[1] for p in self.path]
        m = self.road_w // 2 + 72
        x0, y0 = max(0, int(min(xs) - m)) // 2, max(0, int(min(ys) - m)) // 2
        x1, y1 = min(WORLD, int(max(xs) + m)) // 2, min(WORLD, int(max(ys) + m)) // 2
        crop = self.half.subsurface((x0, y0, x1 - x0, y1 - y0)).copy()
        crop.set_at((0, 0), self.theme["ground"])       # rotate pads the corners with the top-left pixel
        self.rot_cx, self.rot_cy = x0 + crop.get_width() / 2, y0 + crop.get_height() / 2
        self.rotations = []
        for i in range(n):
            r = pygame.transform.rotate(crop, i * 360 / n).convert()
            self.rotations.append((r, r.get_width() / 2, r.get_height() / 2))
        self.n_rot = n
        return n

    def drop_rotations(self):
        self.rotations = None

    # -- geometry ---------------------------------------------------------
    def offset(self, idx, lateral):
        p, nrm = self.path[idx % self.n], self.normals[idx % self.n]
        return (p[0] + nrm[0] * lateral, p[1] + nrm[1] * lateral)

    def height_at(self, prog):
        """Road height at a (fractional) centreline index."""
        i = int(math.floor(prog))
        f = prog - i
        h = self.heights
        return h[i % self.n] * (1 - f) + h[(i + 1) % self.n] * f

    def slope_at(self, prog):
        return self.slopes[int(prog) % self.n]

    def surface_at(self, x, y):
        gx, gy = int(x) // G, int(y) // G
        if 0 <= gx < GRID and 0 <= gy < GRID:
            return self.grid[gy * GRID + gx]
        return WALL

    def nearest_index(self, x, y, guess, window=2):
        """Centreline index nearest to (x, y) within +-window of `guess` (no sqrt: the hot path)."""
        best, bd, path, n = guess, 1e18, self.path, self.n
        for k in range(guess - window, guess + window + 1):
            p = path[k % n]
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < bd:
                best, bd = k % n, d
        return best

    def nearest(self, x, y, guess, window=12):
        """Centreline index nearest to (x, y), searched around `guess`."""
        best, bd = guess, 1e18
        for k in range(guess - window, guess + window + 1):
            p = self.path[k % self.n]
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < bd:
                best, bd = k % self.n, d
        return best, math.sqrt(bd)

    def start_positions(self, count):
        """Two columns behind the line, pole on the inside."""
        out = []
        for i in range(count):
            idx = (self.n - 5 - (i // 2) * 3) % self.n
            x, y = self.offset(idx, -12 if i % 2 == 0 else 12)
            heading = math.degrees(math.atan2(self.dirs[idx][1], self.dirs[idx][0])) + 90
            out.append((x, y, heading, idx))
        return out

    # -- painting ---------------------------------------------------------
    def paint(self):
        t, tr, rng = self.theme, self.track, random.Random(len(self.path))
        n, path, rw = self.n, self.path, self.road_w
        surf = pygame.Surface((WORLD, WORLD)).convert()
        surf.fill(t["ground"])
        for _ in range(2200):
            surf.fill(t["ground2"], (rng.randrange(WORLD), rng.randrange(WORLD), 3, 2))
        self.paint_theme_background(surf, rng)
        pairs = list(zip(path, path[1:] + path[:1]))
        # barrier ring, then the grass verge over it (leaves a 4 px fence either side), then kerbs
        for a, b in pairs:
            pygame.draw.line(surf, t["barrier"], a, b, rw + 68)
        for p in path:
            pygame.draw.circle(surf, t["barrier"], p, (rw + 68) // 2)
        for i, (a, b) in enumerate(pairs):      # verge, tinted by height so hills read from above
            k = self.heights[i] / self.max_height
            col = light(t["ground"], 0.25 * k)
            pygame.draw.line(surf, col, a, b, rw + 60)
        for i, p in enumerate(path):
            pygame.draw.circle(surf, light(t["ground"], 0.25 * self.heights[i] / self.max_height), p, (rw + 60) // 2)
        self.paint_theme_verge(surf, rng)
        for i, (a, b) in enumerate(pairs):
            pygame.draw.line(surf, t["kerb"][(i // 3) % 2], a, b, rw + 10)
        for i, (a, b) in enumerate(pairs):      # road, shaded by slope: uphill lighter, downhill darker
            s = self.slopes[i]
            col = light(t["road"], min(0.3, s * 1.5)) if s > 0 else shade(t["road"], max(0.7, 1 + s * 1.5))
            pygame.draw.line(surf, col, a, b, rw)
            pygame.draw.circle(surf, col, a, rw // 2)
        for i, (a, b) in enumerate(pairs):
            if i % 4 < 2:
                pygame.draw.line(surf, t["lane"], a, b, 2)
        for idx in tr.ice:                      # ice patches on the road
            pygame.draw.ellipse(surf, (175, 222, 250), self.patch_rect(idx, rw - 6, 30))
        for idx in tr.lava:                     # lava pools on the verge
            x, y = self.offset(idx, rw // 2 + 22)
            pygame.draw.ellipse(surf, (255, 190, 60), (x - 22, y - 16, 44, 32))
            pygame.draw.ellipse(surf, (250, 110, 30), (x - 18, y - 13, 36, 26))
        if tr.tunnel:
            s, e = tr.tunnel
            for i in range(s, e):
                pygame.draw.line(surf, (50, 52, 70), path[i], path[(i + 1) % n], rw + 10)
                pygame.draw.line(surf, (36, 36, 50), path[i], path[(i + 1) % n], rw - 4)
            for i in (s, e):
                a = self.offset(i, -(rw // 2 + 8))
                b = self.offset(i, rw // 2 + 8)
                pygame.draw.line(surf, (110, 110, 130), a, b, 6)
        for (x, y), idx in [(self.offset(i, off), i) for i, off in tr.boosts]:   # boost chevrons
            d = self.dirs[idx]
            for k in range(3):
                cx, cy = x - d[0] * (k - 1) * 7, y - d[1] * (k - 1) * 7
                nx, ny = -d[1], d[0]
                pygame.draw.polygon(surf, (60, 240, 255), [(cx + nx * 8, cy + ny * 8), (cx + d[0] * 5, cy + d[1] * 5),
                                                            (cx - nx * 8, cy - ny * 8), (cx - d[0] * 1, cy - d[1] * 1)])
        # start / finish checkerboard across the road at index 0
        sx, sy = path[0]
        d, nrm = self.dirs[0], self.normals[0]
        for k in range(-rw // 2, rw // 2, 4):
            for j in range(2):
                col = (250, 250, 250) if (k // 4 + j) % 2 else OUT
                cx, cy = sx + nrm[0] * k + d[0] * j * 4, sy + nrm[1] * k + d[1] * j * 4
                pygame.draw.rect(surf, col, (cx - 2, cy - 2, 4, 4))
        self.paint_props(surf, rng)
        return surf

    def patch_rect(self, idx, w, h):
        p, d = self.path[idx % self.n], self.dirs[idx % self.n]
        if abs(d[0]) > abs(d[1]):
            w, h = h, w
        return (p[0] - w // 2, p[1] - h // 2, w, h)

    def paint_theme_background(self, surf, rng):
        th = self.track.theme
        if th == "harbor":                      # water along the north edge
            pygame.draw.rect(surf, (40, 90, 160), (0, 0, WORLD, 64))
            for x in range(0, WORLD, 16):
                surf.fill((70, 130, 200), (x + rng.randrange(8), rng.randrange(6, 60), 7, 1))
        elif th == "neon":                      # rooftop tiles
            for x in range(0, WORLD, 64):
                surf.fill((50, 48, 72), (x, 0, 1, WORLD))
                surf.fill((50, 48, 72), (0, x, WORLD, 1))
        elif th == "cinder":
            for _ in range(60):
                x, y = rng.randrange(WORLD), rng.randrange(WORLD)
                pygame.draw.circle(surf, (120, 90, 70), (x, y), rng.randint(6, 20))

    def paint_theme_verge(self, surf, rng):
        th = self.track.theme
        if th == "frost":                       # snow drifts near the road
            for i in range(0, self.n, 4):
                x, y = self.offset(i, rng.choice((-1, 1)) * (self.road_w // 2 + rng.randint(8, 24)))
                pygame.draw.ellipse(surf, (240, 246, 255), (x - 8, y - 4, 16, 8))

    def paint_props(self, surf, rng):
        """Trees, rocks, signs... outside the barrier, drawn flat (they also show in mode-7)."""
        th, rw = self.track.theme, self.road_w
        far = rw // 2 + 40
        placed = 0
        tries = 0
        while placed < 110 and tries < 1200:
            tries += 1
            x, y = rng.randrange(20, WORLD - 20), rng.randrange(20, WORLD - 20)
            if th == "harbor" and y < 80:
                continue
            idx, dist = self.nearest(x, y, rng.randrange(self.n), window=self.n // 2)
            if dist < far:
                continue
            placed += 1
            if th == "harbor" or th == "orchard":
                pygame.draw.circle(surf, OUT, (x, y), 8)
                pygame.draw.circle(surf, (40, 110, 50), (x, y), 7)
                pygame.draw.circle(surf, (80, 160, 70), (x - 2, y - 2), 3)
                if th == "orchard":
                    for _ in range(3):
                        surf.fill((230, 50, 50), (x + rng.randint(-5, 4), y + rng.randint(-5, 4), 2, 2))
            elif th == "cinder":
                pygame.draw.circle(surf, OUT, (x, y), 7)
                pygame.draw.circle(surf, (70, 60, 66), (x, y), 6)
                pygame.draw.circle(surf, (100, 90, 96), (x - 2, y - 2), 2)
            elif th == "frost":
                pygame.draw.polygon(surf, OUT, [(x - 8, y + 7), (x, y - 10), (x + 8, y + 7)])
                pygame.draw.polygon(surf, (30, 90, 60), [(x - 6, y + 6), (x, y - 8), (x + 6, y + 6)])
                pygame.draw.polygon(surf, (235, 245, 255), [(x - 3, y - 2), (x, y - 8), (x + 3, y - 2)])
            else:                               # neon: AC units and signs
                pygame.draw.rect(surf, OUT, (x - 6, y - 5, 12, 10))
                col = rng.choice(((255, 60, 200), (60, 240, 255), (255, 220, 60)))
                pygame.draw.rect(surf, (90, 90, 110) if rng.random() < 0.6 else col, (x - 5, y - 4, 10, 8))
        if th == "harbor":                      # cranes on the dock
            for x in (140, 500, 860):
                pygame.draw.rect(surf, OUT, (x, 40, 10, 40))
                pygame.draw.rect(surf, (230, 200, 60), (x + 1, 41, 8, 38))
                pygame.draw.rect(surf, OUT, (x - 30, 44, 70, 6))
                pygame.draw.rect(surf, (230, 200, 60), (x - 29, 45, 68, 4))

    def build_grid(self):
        """Surface types on a 256x256 grid, painted with the same shapes at 1/4 scale.
        An 8-bit surface whose palette is index-coloured gives us the bytes in one call."""
        tr, rw = self.track, self.road_w / G
        s = pygame.Surface((GRID, GRID), depth=8)
        pal = [(i, i, i) for i in range(256)]
        s.set_palette(pal)
        c = lambda i: (i, i, i)  # noqa: E731
        s.fill(c(WALL))
        pts = [(p[0] / G, p[1] / G) for p in self.path]
        pairs = list(zip(pts, pts[1:] + pts[:1]))
        for a, b in pairs:
            pygame.draw.line(s, c(GRASS), a, b, int(rw + 15))
        for p in pts:
            pygame.draw.circle(s, c(GRASS), p, int(rw + 15) // 2)
        for a, b in pairs:
            pygame.draw.line(s, c(KERB), a, b, int(rw + 2.5))
        for a, b in pairs:
            pygame.draw.line(s, c(ROAD), a, b, int(rw))
        for p in pts:
            pygame.draw.circle(s, c(ROAD), p, int(rw) // 2)
        for idx in tr.ice:
            x, y, w, h = self.patch_rect(idx, self.road_w - 6, 30)
            pygame.draw.ellipse(s, c(ICE), (x / G, y / G, w / G, h / G))
        for idx in tr.lava:
            x, y = self.offset(idx, self.road_w // 2 + 22)
            pygame.draw.ellipse(s, c(LAVA), ((x - 22) / G, (y - 16) / G, 44 / G, 32 / G))
        for (x, y), idx in [(self.offset(i, off), i) for i, off in tr.boosts]:
            pygame.draw.circle(s, c(BOOST), (x / G, y / G), 3)
        return pygame.image.tobytes(s, "P")

    def paint_minimap(self, w=46, h=44):
        box = pygame.Surface((w, h)).convert()
        box.fill((16, 16, 30))
        k = (w - 6) / WORLD
        pts = [(3 + p[0] * k, 3 + p[1] * k) for p in self.path[::3]]
        pygame.draw.lines(box, OUT, True, pts, 4)
        pygame.draw.lines(box, (190, 190, 200), True, pts, 2)
        self.minimap_scale = k
        return box


class Crate:
    """An item box. Picked up -> gone for CRATE_RESPAWN frames."""

    def __init__(self, pos, idx):
        self.x, self.y = pos
        self.home = pos                 # a magnet can drag it; it respawns back here
        self.idx = idx
        self.timer = 0

    @property
    def active(self):
        return self.timer == 0

    def take(self):
        self.timer = CRATE_RESPAWN

    def update(self):
        if self.timer:
            self.timer -= 1
            if self.timer == 0:
                self.x, self.y = self.home
