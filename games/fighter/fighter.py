"""A fighter: input reading, state machine, physics, boxes and drawing."""
import math
from collections import deque

import pygame

from . import art
from .data import AIR_BOX, BLOCK, CBLOCK, CHIT, CROUCH, CROUCH_BOX, DOWN, HIT, IDLE, JUMP, \
    STAND_BOX, TUMBLE, WALK_A, WALK_B, WIN

WIDTH, HEIGHT = 384, 216
GROUND_Y = 196
STAGE_LEFT, STAGE_RIGHT = 16, WIDTH - 16
GRAVITY = 0.36
PRESS_BUFFER = 5        # frames a button press stays "live" (input leniency)
MOTION_WINDOW = 18      # frames allowed to complete a special-move motion
CHARGED = 24            # frames of holding the button for a fully charged special

NEUTRAL_STATES = ("idle", "walk", "crouch")


def motion_in(dirs, seq, window=MOTION_WINDOW):
    """True if the numpad directions in `seq` appear in order within the last `window` frames."""
    i = len(seq) - 1
    recent = list(dirs)[-window:]
    for d in reversed(recent):
        if d == seq[i]:
            i -= 1
            if i < 0:
                return True
    return False


def lerp_pose(a, b, k):
    if k <= 0:
        return a
    if k >= 1:
        return b
    return {j: (a[j][0] + (b[j][0] - a[j][0]) * k, a[j][1] + (b[j][1] - a[j][1]) * k) for j in a}


def keyframe_pose(keys, t):
    prev = keys[0]
    for key in keys[1:]:
        if t < key[0]:
            return lerp_pose(prev[1], key[1], (t - prev[0]) / (key[0] - prev[0]))
        prev = key
    return prev[1]


class Fighter:
    def __init__(self, char, x=100, facing=1, alt=False):
        self.char = char
        self.s = char.scale
        self.look = art.prepare(char.alt_look if alt else char.look)
        self.flash_look = art.flash(self.look)
        self.moves = char.moves
        self.wins = 0
        self.anim = 0
        self.reset(x, facing)

    def reset(self, x, facing):
        self.x = float(x)
        self.y = 0.0
        self.vx = self.vy = 0.0
        self.recoil = 0.0
        self.facing = facing
        self.health = self.red_health = self.char.health
        self.state = "idle"
        self.t = 0
        self.move = None
        self.move_contact = False
        self.hits_done = 0
        self.rehit_at = 0
        self.charge = 0
        self.followup = None
        self.stun = 0
        self.stun_low = False
        self.invuln = 0
        self.air_used = False
        self.landed = False
        self.guarding = False
        self.threatened = False
        self.combo_taken = 0
        self.projectile = None
        self.dir = 5
        self.dirs = deque([5] * MOTION_WINDOW, maxlen=MOTION_WINDOW)
        self.buttons = {"a": 0, "b": 0}
        self.held_buttons = frozenset()

    # ------------------------------------------------------------------ input
    def read_input(self, inp):
        held = inp.held
        dx = (("right" in held) - ("left" in held)) * self.facing
        dy = 1 if "up" in held else (-1 if "down" in held else 0)
        self.dir = 5 + dx + 3 * dy
        self.dirs.append(self.dir)
        self.held_buttons = held & {"a", "b"}
        for b in ("a", "b"):
            if b in inp.pressed:
                self.buttons[b] = PRESS_BUFFER
            elif self.buttons[b]:
                self.buttons[b] -= 1

    def take(self, b):
        if self.buttons[b]:
            self.buttons[b] = 0
            return True
        return False

    def check_special(self):
        for sp in self.char.specials:
            if self.buttons[sp.button] and motion_in(self.dirs, sp.motion):
                move = self.moves[sp.key]
                if move.projectile and self.projectile is not None:
                    continue
                self.buttons[sp.button] = 0
                return move
        return None

    # ------------------------------------------------------------------ state
    @property
    def crouching(self):
        if self.state == "crouch":
            return True
        if self.state in ("hitstun", "blockstun"):
            return self.stun_low
        if self.state == "attack":
            return self.move.crouch
        return False

    @property
    def airborne(self):
        return self.y > 0 or self.vy > 0

    def set_state(self, state):
        if state != self.state:
            self.state = state
            self.t = 0

    def face(self, other):
        if other.x > self.x + 1:
            self.facing = 1
        elif other.x < self.x - 1:
            self.facing = -1

    def start_move(self, move):
        self.state = "attack"
        self.t = 0
        self.move = move
        self.move_contact = False
        self.hits_done = 0
        self.rehit_at = 0
        self.charge = 0
        self.followup = None
        if not move.air:
            self.vx = 0.0
        if move.invuln:
            self.invuln = move.invuln

    def is_active(self):
        m = self.move
        return self.state == "attack" and m.startup < self.t <= m.startup + m.active

    def can_hit(self):
        return self.is_active() and self.hits_done < self.move.hits and self.t >= self.rehit_at

    @property
    def charged(self):
        return self.charge >= CHARGED

    def threatens(self, other):
        if self.state == "attack" and abs(self.x - other.x) < 110:
            return True
        p = self.projectile
        return p is not None and abs(p.x - other.x) < 130 and (other.x - p.x) * p.vx > 0

    def update(self, opp, match):
        self.t += 1
        self.anim += 1
        if self.invuln:
            self.invuln -= 1
        st = self.state
        if st in NEUTRAL_STATES:
            self._neutral(opp)
        elif st == "jump":
            self._jump()
        elif st == "attack":
            self._attack(match)
        elif st in ("hitstun", "blockstun"):
            self.stun -= 1
            if self.stun <= 0:
                self.set_state("crouch" if self.dir in (1, 2, 3) else "idle")
        elif st == "land":
            if self.t >= self.stun:
                self.set_state("idle")
        elif st == "knockdown" and self.landed and self.t >= 40:
            self.state, self.t, self.stun, self.invuln = "getup", 0, 18, 18
        elif st == "getup" and self.t >= self.stun:
            self.set_state("idle")
        if self.state in NEUTRAL_STATES or self.state == "jump":
            self.combo_taken = 0
        self._physics(match)

    def _neutral(self, opp):
        self.face(opp)
        move = self.check_special()
        if move:
            return self.start_move(move)
        low = self.dir in (1, 2, 3)
        if self.take("a"):
            return self.start_move(self.moves["crouch_p" if low else "stand_p"])
        if self.take("b"):
            return self.start_move(self.moves["crouch_k" if low else "stand_k"])
        if self.dir in (7, 8, 9):
            self.state, self.t = "jump", 0
            self.vy = self.char.jump_vy
            self.vx = (self.dir - 8) * self.char.jump_vx * self.facing
            self.air_used = False
            return
        self.guarding = self.dir in (1, 4) and self.threatened
        if low:
            self.set_state("crouch")
            self.vx = 0.0
        elif self.dir == 6:
            self.set_state("walk")
            self.vx = self.char.walk * self.facing
        elif self.dir == 4 and not self.guarding:
            self.set_state("walk")
            self.vx = -self.char.back * self.facing
        else:
            self.set_state("idle")
            self.vx = 0.0

    def _jump(self):
        if not self.air_used:
            for b, key in (("a", "air_p"), ("b", "air_k")):
                if self.take(b):
                    self.air_used = True
                    return self.start_move(self.moves[key])

    def _attack(self, match):
        m, f = self.move, self.t
        if self.followup:  # the last hit connected: go straight into the follow-up
            move, self.followup = self.followup, None
            return self.start_move(move)
        if m.charge and f == m.startup and self.held_buttons and self.charge < m.charge:
            self.t -= 1  # hold at the end of startup while the button is held
            self.charge += 1
            return
        if f == m.startup + 1:
            if m.impulse:
                self.vx = m.impulse[0] * self.facing
                self.vy = m.impulse[1]
            if m.projectile and self.projectile is None:
                match.spawn_projectile(self, m)
            if m.fx == "slam":
                match.shake = max(match.shake, 6)
                match.dust(self.x + 22 * self.s * self.facing)
            match.app.play("special" if m.special else "whoosh")
        if m.drive:
            if self.is_active():
                self.vx = m.drive * self.facing
            elif f > m.startup:
                self.vx *= 0.7
        if m.cancel and self.move_contact and f > m.startup:
            special = self.check_special()
            if special:
                return self.start_move(special)
        if f >= m.total:
            self.move = None
            if self.airborne:
                self.state, self.t, self.air_used = "jump", 0, True
            else:
                self.vx = 0.0
                self.state, self.t = ("crouch" if self.dir in (1, 2, 3) else "idle"), 0

    def _physics(self, match):
        self.x += self.vx + self.recoil
        self.recoil *= 0.75
        if abs(self.recoil) < 0.05:
            self.recoil = 0.0
        if self.airborne:
            self.y += self.vy
            self.vy -= GRAVITY
            if self.y <= 0:
                self.y = self.vy = 0.0
                self._land(match)
        self.x = min(max(self.x, STAGE_LEFT), STAGE_RIGHT)

    def _land(self, match):
        st = self.state
        if st == "jump" or (st == "attack" and self.move.air):
            self.state, self.t, self.stun, self.vx, self.move = "land", 0, 3, 0.0, None
        elif st == "attack":
            self.vx = 0.0
        elif st in ("knockdown", "ko"):
            self.vx = 0.0
            self.landed = True
            self.t = 0
            match.app.play("thud")
            match.dust(self.x)

    # ------------------------------------------------------------------ getting hit
    def can_block(self, level):
        if self.airborne or self.state not in ("idle", "walk", "crouch", "blockstun"):
            return False
        if self.dir not in (1, 4):
            return False
        if level == "low" and self.dir != 1:
            return False
        if level == "high" and self.dir != 4:
            return False
        return True

    def enter_stun(self, state, frames, push):
        self.stun_low = self.dir in (1, 2, 3) if state == "blockstun" else self.crouching
        self.state, self.t, self.stun = state, 0, frames
        self.move = None
        self.vx = 0.0
        self.recoil = push

    def knock(self, sign, launch, ko=False):
        self.state = "ko" if ko else "knockdown"
        self.t = 0
        self.move = None
        self.landed = False
        self.vx = launch[0] * sign
        self.vy = launch[1]
        self.y = max(self.y, 1.0)
        self.recoil = 0.0

    # ------------------------------------------------------------------ boxes
    def rect(self, box):
        bx, by, bw, bh = (v * self.s for v in box)
        left = self.x + bx if self.facing == 1 else self.x - bx - bw
        return pygame.Rect(int(left), int(GROUND_Y - self.y + by), int(bw), int(bh))

    def hurtboxes(self):
        if self.invuln or self.state in ("knockdown", "ko", "getup"):
            return []
        if self.airborne:
            base = AIR_BOX
        elif self.crouching:
            base = CROUCH_BOX
        else:
            base = STAND_BOX
        boxes = [self.rect(base)]
        box = self.current_box()
        if box and self.t > self.move.startup:
            x, y, w, h = box  # the extended limb can be hit too
            boxes.append(self.rect((x + 2, y + 2, max(1, w - 6), max(1, h - 4))))
        return boxes

    def current_box(self):
        """The move's hitbox; multi-part moves list (frame from the first active frame, box)."""
        if self.state != "attack":
            return None
        box = self.move.hitbox
        if isinstance(box, list):
            t = self.t - self.move.startup - 1
            box = [b for start, b in box if start <= t][-1] if t >= 0 else box[0][1]
        return box

    def hitbox(self):
        box = self.current_box()
        if box and self.is_active():
            return self.rect(box)
        return None

    # ------------------------------------------------------------------ drawing
    def current_pose(self):
        st = self.state
        if st == "idle":
            if self.guarding:
                return BLOCK
            bob = round(math.sin(self.anim * 0.12))
            return {j: (p[0], p[1] + bob) if j in ("head", "neck", "elb_f", "hand_f", "elb_b", "hand_b")
                    else p for j, p in IDLE.items()}
        if st == "walk":
            return lerp_pose(WALK_A, WALK_B, 0.5 + 0.5 * math.sin(self.anim * 0.25))
        if st == "crouch":
            return CBLOCK if self.guarding else CROUCH
        if st == "jump":
            return JUMP
        if st == "land":
            return lerp_pose(IDLE, CROUCH, 0.5)
        if st == "attack":
            return self._attack_pose()
        if st == "hitstun":
            return CHIT if self.stun_low else HIT
        if st == "blockstun":
            return CBLOCK if self.stun_low else BLOCK
        if st in ("knockdown", "ko"):
            return DOWN if self.landed else TUMBLE
        if st == "getup":
            return lerp_pose(DOWN, CROUCH, self.t / max(1, self.stun))
        if st == "win":
            return WIN
        return IDLE

    def _attack_pose(self):
        m, f = self.move, self.t
        if m.anim:
            return keyframe_pose(m.anim, f)
        base = CROUCH if m.crouch else (JUMP if m.air else IDLE)
        if f <= m.startup:
            k = f / max(1, m.startup)
            if m.windup:
                return lerp_pose(base, m.windup, min(1.0, k * 1.6))
            return lerp_pose(base, m.pose, k * 0.5)
        if f <= m.startup + m.active:
            return m.pose
        return lerp_pose(m.pose, base, (f - m.startup - m.active) / max(1, m.recovery))

    def draw_shadow(self, surf, ox=0, oy=0):
        w = int(30 * self.s * max(0.4, 1 - self.y / 120))
        pygame.draw.ellipse(surf, (25, 18, 30), (self.x + ox - w // 2, GROUND_Y + oy - 3, w, 6))

    def draw(self, surf, ox=0, oy=0):
        s, f = self.s, self.facing
        bx, by = self.x + ox, GROUND_Y - self.y + oy
        p = {j: (bx + v[0] * s * f, by + v[1] * s) for j, v in self.current_pose().items()}
        look = self.flash_look if self.state == "hitstun" and self.t < 3 else self.look
        art.draw_fx(surf, self, p, behind=True)
        art.DRAW[self.char.style](surf, p, f, self.anim, look)
        art.draw_fx(surf, self, p, behind=False)


class Projectile:
    def __init__(self, owner, move):
        spec = move.projectile
        self.owner = owner
        self.move = move
        self.x = self.x0 = owner.x + spec["x"] * owner.s * owner.facing
        self.y = spec["y"] * owner.s
        self.vx = spec["speed"] * owner.facing
        self.w, self.h = spec["w"], spec["h"]
        self.style = spec["style"]
        self.hits_left = spec.get("hits", 1)
        self.hits_done = 0
        self.charged = owner.charged
        if self.charged:
            self.hits_left += 1
            self.w, self.h = self.w + 6, self.h + 6
        self.rehit = 0
        self.linger = None  # frames left after the first hit (it slows down and keeps hitting)
        self.t = 0
        self.dead = False

    def rect(self):
        return pygame.Rect(int(self.x - self.w / 2), int(GROUND_Y - self.y - self.h / 2), self.w, self.h)

    def can_hit(self):
        return not self.dead and self.rehit == 0

    def connected(self):
        """Called for every hit or block; multi-hit projectiles slow down and hit again."""
        self.hits_done += 1
        self.hits_left -= 1
        if self.hits_left <= 0:
            self.dead = True
            return
        self.rehit = 8
        self.vx *= 0.25
        if self.linger is None:
            self.linger = 26

    def update(self):
        self.x += self.vx
        self.t += 1
        if self.rehit:
            self.rehit -= 1
        if self.linger is not None:
            self.linger -= 1
            if self.linger <= 0:
                self.dead = True
        if self.x < -20 or self.x > WIDTH + 20:
            self.dead = True

    def draw(self, surf, ox=0, oy=0):
        art.draw_projectile(surf, self, ox, oy, GROUND_Y)
