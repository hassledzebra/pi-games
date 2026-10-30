"""Kart physics: arcade handling with drift, boost, slopes, airtime, surfaces,
bumping and the slapstick status effects the items inflict.

Units: world px and frames (60/s). heading is in degrees, 0 = up (-y),
clockwise positive, like the pre-rotated sprites. Progress along the lap is a
fractional centreline index that keeps counting up lap after lap.
"""
import math

from .data import LAPS
from .world import BOOST, GRASS, GRID, ICE, KERB, LAVA, ROAD, SPACING, WALL

GRAVITY = 0.13
FRICTION = (1.0, 0.985, 0.985 * 0.985)     # coasting speed factor per step of dt frames
DRIFT_MINI, DRIFT_SUPER = 45, 95      # frames of drift for a small / big boost


def norm_angle(a):
    return (a + 180) % 360 - 180


class Kart:
    RADIUS = 9

    def __init__(self, racer, world, x, y, heading, seg, slot):
        self.racer, self.world, self.slot = racer, world, slot
        self.x, self.y = x, y
        self.heading = heading             # where the nose points
        self.move_dir = heading            # where the kart actually travels (lags when drifting)
        self.speed = 0.0
        self.top = 2.5 + 0.2 * racer.speed             # 2.7..3.5 px/frame
        self.accel = 0.022 + 0.008 * racer.accel        # px/frame^2
        self.turn = 2.0 + 0.3 * racer.handling          # deg/frame at full speed
        self.grip = 0.10 + 0.03 * racer.handling
        self.mass = 1.0 + 0.5 * racer.weight
        # progress
        self.seg = seg
        self.prog = float(seg - world.n)   # starts just behind the line
        self.lap_start = 0                 # frame the current lap started
        self.laps_done = []                # lap times in frames
        self.finished = None               # frame the race was finished
        self.wrong_way = 0
        self.flow = 0.0                    # smoothed progress per frame, for wrong-way detection
        # vertical
        self.alt = world.height_at(self.prog)
        self.vz = 0.0
        self.air = 0
        self.z = 0.0                       # height above the road
        self.bounce = 0.0                  # landing bob (view)
        self.landed = 0                    # frames since landing (dust / camera bob)
        # control & state
        self.gas = self.brake = False
        self.steer = 0                     # -1, 0, 1
        self.drift = 0                     # 0 or direction
        self.drift_t = 0
        self.boost = 0
        self.spin = 0
        self.stuck = 0
        self.soaked = 0
        self.pie = 0                       # pie splat on this player's view
        self.hit_t = 0                     # 'ouch' face timer
        self.lean = 0.0                    # head lean -1..1
        self.look_back = False
        self.fire = False                  # fire item this frame
        self.fire_back = False
        self.item = None
        self.item_lock = 0                 # frames until the next crate can be taken
        self.pepper = 0                    # hot pepper boost (red face, flames)
        self.shield = 0                    # bubble shield frames left
        self.magnet = 0
        self.pogo_air = False              # airborne from a pogo jump: flailing, flies over walls
        self.cap = 1.0                     # CPU speed cap (rubber band)
        self.slipstream = False
        self.surface = 1
        self.shake = 0
        self.dust = []                     # [x, y, life]
        self.frame = 0
        self.on_pad = False
        self.events = []                   # sound names for the scene to play

    # -- input ------------------------------------------------------------
    def control(self, inp):
        held, pressed = inp.held, inp.pressed
        self.gas = "a" in held
        self.steer = ("right" in held) - ("left" in held)
        self.look_back = "down" in held
        if "up" in pressed:
            self.fire = True                   # latched until the item system looks (every other frame)
            self.fire_back = "down" in held
        if "b" in pressed and self.steer and self.speed > 0.55 * self.top and not self.air and not self.drift \
                and not self.spin:
            self.drift, self.drift_t = self.steer, 0
            self.events.append("drift")
        self.brake = "b" in held and not self.drift

    # -- effects ------------------------------------------------------------
    def spin_out(self, frames=40, sound="spin"):
        if self.spin:
            return
        self.spin, self.drift = frames, 0
        self.speed *= 0.3
        self.hit_t = frames + 20
        self.events.append(sound)

    def stick(self, frames=60):
        self.stuck = max(self.stuck, frames)
        self.hit_t = max(self.hit_t, 30)
        self.events.append("gum")

    def soak(self, frames=90):
        self.soaked = max(self.soaked, frames)
        self.hit_t = max(self.hit_t, 20)

    def give_boost(self, frames):
        self.boost = max(self.boost, frames)

    def pop_shield(self):
        self.shield = 0
        self.events.append("pop")

    def pogo(self):
        if self.air:
            return
        self.vz = 4.6
        self.air = 1
        self.pogo_air = True
        self.alt += self.vz
        self.events.append("boing")

    def ahead_of_point(self, x, y):
        dx, dy = x - self.x, y - self.y
        fx, fy = self.dir
        return dx * fx + dy * fy, dx * -fy + dy * fx

    @property
    def expr(self):
        if self.hit_t:
            return "hit"
        if self.pepper:
            return "pepper"
        if self.pogo_air:
            return "flail"
        return "normal"

    @property
    def lap(self):
        return max(1, int(math.floor(self.prog / self.world.n)) + 1)

    @property
    def dir(self):
        a = math.radians(self.heading)
        return math.sin(a), -math.cos(a)

    # -- physics ------------------------------------------------------------
    def update(self, dt=1):
        """One physics step of dt frames (a Pi steps far CPU karts with dt=2).
        Written for speed: locals, inlined grid lookups."""
        w = self.world
        grid = w.grid
        self.frame += dt
        if self.boost:
            self.boost = self.boost - dt if self.boost > dt else 0
        if self.spin:
            self.spin = self.spin - dt if self.spin > dt else 0
        if self.stuck:
            self.stuck = self.stuck - dt if self.stuck > dt else 0
        if self.soaked:
            self.soaked = self.soaked - dt if self.soaked > dt else 0
        if self.pie:
            self.pie = self.pie - dt if self.pie > dt else 0
        if self.hit_t:
            self.hit_t = self.hit_t - dt if self.hit_t > dt else 0
        if self.item_lock:
            self.item_lock = self.item_lock - dt if self.item_lock > dt else 0
        if self.shake:
            self.shake = self.shake - dt if self.shake > dt else 0
        if self.pepper:
            self.pepper = self.pepper - dt if self.pepper > dt else 0
        if self.shield:
            self.shield = self.shield - dt if self.shield > dt else 0
        if self.magnet:
            self.magnet = self.magnet - dt if self.magnet > dt else 0
        if self.landed:
            self.landed = self.landed - dt if self.landed > dt else 0
        if self.bounce:
            self.bounce *= 0.8
        fr = FRICTION[dt]
        x, y = self.x, self.y
        if self.air:
            surf = -1
        else:
            gx, gy = int(x) >> 2, int(y) >> 2
            surf = grid[gy * GRID + gx] if 0 <= gx < GRID and 0 <= gy < GRID else WALL
        self.surface = surf
        speed = self.speed
        top = self.top
        if surf == ROAD or surf == -1:
            pass
        elif surf == GRASS:
            top *= 0.6
        elif surf == KERB:
            top *= 0.92
            self.shake = 2
        elif surf == LAVA:
            top *= 0.4
        elif surf == BOOST and not self.on_pad:
            self.give_boost(50)
            self.events.append("boost")
        self.on_pad = surf == BOOST
        if self.soaked:
            top *= 0.6
        if self.stuck and top > 0.5:
            top = 0.5
        if self.pepper:
            top *= 1.45
        elif self.boost:
            top *= 1.3
        if self.slipstream:
            top *= 1.08
            accel = self.accel * 1.5
        else:
            accel = self.accel
        top *= self.cap
        grip = 0.03 if surf == ICE else self.grip
        heading = self.heading
        if self.spin:                                         # spinning: no control
            heading += 9.0 * dt
            speed *= fr
            self.drift = 0
        elif self.air:
            speed *= 0.998                                    # no steering in the air
        else:
            if self.gas:
                if self.boost or self.pepper:
                    speed = min(top, speed + 0.1 * dt)
                elif speed < top:
                    speed += accel * dt
            elif self.brake:
                speed = max(speed - accel * 2.5 * dt, -0.9)
            else:
                speed *= fr
            if speed > top:
                speed = max(top, speed - 0.03 * dt)
            speed -= w.slopes[int(self.prog) % w.n] * 0.05 * dt   # slower uphill, faster downhill
            k = abs(speed) / (0.45 * self.top)
            if k > 1.0:
                k = 1.0
            if self.drift:
                if self.steer == -self.drift and self.drift_t > 8 or abs(speed) < 0.4 * self.top:
                    self.end_drift()
                else:
                    self.drift_t += dt
                    heading += self.drift * self.turn * (1.25 + 0.45 * self.steer * self.drift) * k * dt
                    grip = 0.05
                    if speed > 0.88 * top:
                        speed -= 0.01 * dt
                    if self.drift_t % 3 == 0:
                        self.puff()
            elif self.steer:
                heading += self.steer * self.turn * k * dt * (1 if speed >= 0 else -1)
        heading %= 360
        self.heading = heading
        # travel direction follows the nose with some lag (more when drifting / on ice)
        md = self.move_dir + ((heading - self.move_dir + 180) % 360 - 180) * grip
        self.move_dir = md
        a = md * 0.017453292519943295
        self.lean += (self.steer * (1.4 if self.drift else 0.8) - self.lean) * 0.2
        # move, blocked by walls (slide along them); a pogo jump sails over walls
        nx, ny = x + math.sin(a) * speed * dt, y - math.cos(a) * speed * dt
        gx, gy = int(nx) >> 2, int(ny) >> 2
        if self.pogo_air or (0 <= gx < GRID and 0 <= gy < GRID and grid[gy * GRID + gx] != WALL):
            self.x, self.y = nx, ny
        elif w.surface_at(nx, y) != WALL:
            self.x = nx
            speed *= 0.9
        elif w.surface_at(x, ny) != WALL:
            self.y = ny
            speed *= 0.9
        else:
            speed *= -0.3
            self.shake = 6
            self.events.append("bump")
        self.speed = speed
        if dt > 1 or (self.frame + self.slot) % 2 == 0 or self.air or self.frame < 300:   # progress every other frame
            self.track_progress()
        self.vertical(dt)
        if self.dust:
            for d in self.dust:
                d[2] -= dt
            if self.dust[0][2] <= 0:
                self.dust.pop(0)

    def end_drift(self):
        if self.drift_t >= DRIFT_SUPER:
            self.give_boost(80)
            self.events.append("boost")
        elif self.drift_t >= DRIFT_MINI:
            self.give_boost(45)
            self.events.append("boost")
        self.drift, self.drift_t = 0, 0

    def puff(self):
        if len(self.dust) < 4:
            dx, dy = self.dir
            self.dust.append([self.x - dx * 8, self.y - dy * 8, 18])

    def track_progress(self):
        w = self.world
        seg = w.nearest_index(self.x, self.y, self.seg, 2)  # steps are < 10 px, points are 9 apart
        delta = (seg - self.seg + w.n // 2) % w.n - w.n // 2
        self.seg = seg
        p, d = w.path[seg], w.dirs[seg]
        frac = ((self.x - p[0]) * d[0] + (self.y - p[1]) * d[1]) / SPACING
        # integer part follows the centreline index, the fraction is the offset along it
        self.prog = math.floor(self.prog + 0.5) + delta + max(-0.5, min(0.5, frac))
        self.flow = self.flow * 0.93 + delta
        self.wrong_way = self.speed > 0.5 and self.flow < -1.2
        n = w.n
        laps = int(math.floor(self.prog / n))
        if laps > len(self.laps_done) and self.prog >= 0:
            self.laps_done.append(self.frame - self.lap_start)
            self.lap_start = self.frame
            self.events.append("lap")
            if laps >= LAPS and self.finished is None:
                self.finished = self.frame
                self.events.append("finish")
        elif self.laps_done and laps < len(self.laps_done):   # crossed the line backwards: un-count it
            self.laps_done.pop()

    def vertical(self, dt=1):
        """Ballistic altitude: airborne whenever the trajectory is above the road."""
        w = self.world
        p = self.prog
        i = math.floor(p)
        f = p - i
        hts, n = w.heights, w.n
        h = hts[i % n] * (1 - f) + hts[(i + 1) % n] * f
        if self.air:
            self.vz -= GRAVITY * dt
            self.alt += self.vz * dt
            self.air += dt
            if self.alt <= h:
                self.alt = h
                self.bounce = min(8.0, -self.vz * 3)
                self.landed = 12 if self.vz < -1.2 else 4
                self.air = 0
                if self.pogo_air:
                    self.pogo_air = False
                    if w.surface_at(self.x, self.y) == WALL:     # landed outside: back on the road
                        self.x, self.y = w.path[self.seg]
                        self.speed *= 0.3
                        self.hit_t = 30
                if self.vz < -1.0:
                    self.events.append("land")
                    for _ in range(3):
                        self.puff()
                self.vz = 0.0
        else:
            proj = self.alt + (self.vz - GRAVITY) * dt
            if proj > h + 0.01 and self.speed > 1.2:
                self.air = 1
                self.vz -= GRAVITY * dt
                self.alt = proj
            else:
                self.vz = (h - self.alt) / dt if self.speed > 0 else 0.0
                self.alt = h
        self.z = max(0.0, self.alt - h)

    # -- helpers used by the AI, the items and the views ---------------------
    def ahead_of(self, other):
        """Signed distance of `other` along this kart's heading (+ = ahead) and lateral offset."""
        dx, dy = other.x - self.x, other.y - self.y
        fx, fy = self.dir
        return dx * fx + dy * fy, dx * -fy + dy * fx


def collide(karts):
    """Push overlapping karts apart; the heavier one wins the shove."""
    r2 = (2 * Kart.RADIUS) ** 2
    for i, a in enumerate(karts):
        for b in karts[i + 1:]:
            dx, dy = b.x - a.x, b.y - a.y
            d2 = dx * dx + dy * dy
            if d2 >= r2 or d2 == 0 or abs(a.z - b.z) > 6:
                continue
            d = math.sqrt(d2)
            overlap = 2 * Kart.RADIUS - d
            nx, ny = dx / d, dy / d
            ka = b.mass / (a.mass + b.mass)
            a.x -= nx * overlap * ka
            a.y -= ny * overlap * ka
            b.x += nx * overlap * (1 - ka)
            b.y += ny * overlap * (1 - ka)
            # speed exchange: the lighter kart gets knocked harder; a bubble shield takes the bump
            if a.shield:
                a.pop_shield()
            else:
                a.speed *= 1 - 0.25 * ka
            if b.shield:
                b.pop_shield()
            else:
                b.speed *= 1 - 0.25 * (1 - ka)
            a.shake = b.shake = 4
            if a.frame % 8 == 0:
                a.events.append("bump")


def slipstreams(karts):
    """A kart close behind another, going the same way, gets a tow."""
    for a in karts:
        a.slipstream = False
        for b in karts:
            if a is b:
                continue
            fwd, side = a.ahead_of(b)
            if 14 < fwd < 70 and abs(side) < 14 and abs(norm_angle(a.heading - b.heading)) < 30 and b.speed > 1.0:
                a.slipstream = True
                break
