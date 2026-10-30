"""Characters, poses and frame data.

Poses are skeletons of 11 joints relative to the fighter's feet, facing right,
y negative = up. Fighters are drawn from these with a few thick lines and
circles, so there are no sprite sheets to load and they stay cheap to draw.

Frame data (startup / active / recovery) is in 1/60 s frames.
Hitboxes are (x, y, w, h) in the same space as the poses.
Signature moves are animated with keyframes: [(frame, pose), ...].
"""


def pose(base, **changes):
    p = dict(base)
    p.update(changes)
    return p


IDLE = dict(head=(3, -57), neck=(1, -49), hip=(-1, -29),
            elb_f=(10, -41), hand_f=(16, -48), elb_b=(-3, -39), hand_b=(7, -44),
            knee_f=(8, -15), foot_f=(12, 0), knee_b=(-7, -14), foot_b=(-11, 0))
WALK_A = pose(IDLE, knee_f=(10, -15), foot_f=(16, 0), knee_b=(-9, -13), foot_b=(-16, 0))
WALK_B = pose(IDLE, knee_f=(5, -16), foot_f=(2, 0), knee_b=(-1, -16), foot_b=(-4, 0))
CROUCH = dict(head=(6, -37), neck=(3, -30), hip=(-2, -15),
              elb_f=(12, -24), hand_f=(18, -30), elb_b=(1, -22), hand_b=(10, -27),
              knee_f=(14, -13), foot_f=(12, 0), knee_b=(4, -5), foot_b=(-12, 0))
JUMP = dict(head=(3, -57), neck=(1, -49), hip=(0, -31),
            elb_f=(10, -42), hand_f=(15, -49), elb_b=(-4, -41), hand_b=(5, -46),
            knee_f=(10, -26), foot_f=(4, -15), knee_b=(0, -21), foot_b=(-9, -14))

JAB = pose(IDLE, head=(6, -56), neck=(4, -48), elb_f=(17, -46), hand_f=(29, -47),
           elb_b=(0, -40), hand_b=(8, -45))
KICK_UP = pose(IDLE, knee_f=(12, -28), foot_f=(6, -16), head=(1, -57), neck=(-1, -49))
KICK = pose(IDLE, head=(-5, -56), neck=(-4, -48), hip=(-2, -30),
            knee_f=(14, -34), foot_f=(32, -40), knee_b=(-4, -15), foot_b=(-6, 0),
            elb_f=(4, -42), hand_f=(10, -50), elb_b=(-10, -40), hand_b=(-4, -46))
CJAB = pose(CROUCH, head=(8, -36), neck=(5, -29), elb_f=(16, -28), hand_f=(28, -29))
SWEEP = pose(CROUCH, head=(2, -35), neck=(0, -28), hip=(-4, -13),
             knee_f=(14, -6), foot_f=(34, -2), knee_b=(0, -5), foot_b=(-14, 0),
             elb_f=(8, -22), hand_f=(12, -14), elb_b=(-4, -18), hand_b=(-8, -4))
AIR_P = pose(JUMP, head=(5, -56), neck=(3, -48), elb_f=(13, -42), hand_f=(24, -36))
AIR_K = pose(JUMP, knee_f=(12, -24), foot_f=(26, -14), knee_b=(-2, -24), foot_b=(-10, -18))

THROW_UP = pose(IDLE, head=(0, -56), neck=(-2, -48), elb_f=(-4, -36), hand_f=(-8, -32),
                elb_b=(-8, -36), hand_b=(-10, -30))
THROW = pose(IDLE, head=(7, -56), neck=(5, -48), elb_f=(16, -44), hand_f=(27, -44),
             elb_b=(15, -40), hand_b=(26, -39), knee_f=(12, -15), foot_f=(17, 0),
             knee_b=(-8, -13), foot_b=(-15, 0))
RISING = pose(JUMP, hip=(0, -34), neck=(-3, -52), head=(-6, -60),
              elb_f=(10, -50), hand_f=(16, -58), knee_f=(10, -42), foot_f=(16, -66),
              knee_b=(-2, -20), foot_b=(-6, -6))
STOMP_UP = pose(IDLE, knee_f=(12, -34), foot_f=(14, -24), elb_f=(8, -52), hand_f=(10, -62),
                elb_b=(-6, -52), hand_b=(-2, -62))
STOMP = pose(IDLE, head=(8, -50), neck=(6, -43), hip=(0, -26), knee_f=(14, -13), foot_f=(16, 0),
             elb_f=(16, -28), hand_f=(22, -14), elb_b=(10, -28), hand_b=(16, -14))
RUSH = dict(head=(15, -48), neck=(10, -43), hip=(-2, -27),
            elb_f=(16, -38), hand_f=(10, -32), elb_b=(6, -36), hand_b=(4, -30),
            knee_f=(10, -14), foot_f=(16, 0), knee_b=(-10, -12), foot_b=(-18, 0))

HIT = pose(IDLE, head=(-8, -54), neck=(-6, -47), hip=(-2, -29),
           elb_f=(4, -40), hand_f=(8, -34), elb_b=(-12, -42), hand_b=(-18, -36))
CHIT = pose(CROUCH, head=(-2, -36), neck=(-2, -29))
BLOCK = pose(IDLE, head=(0, -56), neck=(-1, -48), elb_f=(10, -46), hand_f=(10, -56),
             elb_b=(8, -40), hand_b=(12, -48))
CBLOCK = pose(CROUCH, head=(4, -36), elb_f=(12, -30), hand_f=(12, -40), elb_b=(10, -24), hand_b=(14, -34))
TUMBLE = dict(head=(-18, -40), neck=(-12, -36), hip=(0, -26),
              elb_f=(-4, -44), hand_f=(2, -50), elb_b=(-18, -46), hand_b=(-24, -52),
              knee_f=(10, -30), foot_f=(18, -22), knee_b=(6, -20), foot_b=(14, -12))
DOWN = dict(head=(-27, -5), neck=(-19, -4), hip=(1, -4),
            elb_f=(-12, -8), hand_f=(-6, -3), elb_b=(-24, -2), hand_b=(-32, -2),
            knee_f=(10, -8), foot_f=(20, -2), knee_b=(12, -3), foot_b=(22, -1))
WIN = pose(IDLE, elb_f=(8, -60), hand_f=(10, -72), elb_b=(-8, -40), hand_b=(-2, -34), head=(2, -58))


def mirror(p):
    return {j: (-x, y) for j, (x, y) in p.items()}


def lift(p, dy):
    return {j: (x, y - dy) for j, (x, y) in p.items()}


# Kaze - Tempest Orb: gather wind at the hip, charge, two-palm thrust
GATHER = pose(CROUCH, head=(2, -40), neck=(0, -33), hip=(-3, -17), elb_f=(-6, -24), hand_f=(-10, -20),
              elb_b=(-8, -26), hand_b=(-12, -22))
CHARGE = pose(CROUCH, head=(3, -40), neck=(1, -33), hip=(-3, -17), elb_f=(6, -22), hand_f=(10, -20),
              elb_b=(2, -24), hand_b=(9, -24))
PUSH = pose(THROW, elb_f=(16, -42), hand_f=(28, -42), elb_b=(15, -38), hand_b=(27, -37))
# Kaze - Cyclone Kick: two spins on the way up, then an axe kick on the way down
SPIN = pose(RISING, elb_f=(-6, -50), hand_f=(-12, -56), elb_b=(10, -54), hand_b=(14, -62),
            knee_f=(12, -40), foot_f=(26, -50))
SPIN_BACK = mirror(SPIN)
AXE_UP = pose(JUMP, head=(-2, -58), neck=(-2, -50), hip=(0, -32), knee_f=(8, -48), foot_f=(10, -72),
              elb_f=(-8, -50), hand_f=(-14, -44), elb_b=(-10, -46), hand_b=(-16, -40))
AXE_DOWN = pose(JUMP, head=(4, -56), neck=(3, -48), knee_f=(16, -36), foot_f=(26, -24),
                elb_f=(-6, -46), hand_f=(-12, -52))
# Brakk - Earthsplitter: fists overhead, hop, double-fist slam
FISTS_UP = pose(IDLE, head=(-2, -58), neck=(-3, -50), elb_f=(2, -62), hand_f=(4, -74), elb_b=(-6, -62),
                hand_b=(-2, -74), knee_f=(10, -16), foot_f=(14, 0))
SLAM = pose(CROUCH, head=(10, -32), neck=(6, -26), hip=(-4, -16), elb_f=(14, -14), hand_f=(20, -2),
            elb_b=(10, -14), hand_b=(17, -2))
# Brakk - Ram Charge: paw the ground, shoulder charge, follow-up headbutt
PAW = pose(IDLE, head=(9, -50), neck=(5, -44), hip=(-2, -28), knee_b=(-12, -10), foot_b=(-20, -2),
           elb_f=(10, -38), hand_f=(10, -30), elb_b=(2, -36), hand_b=(4, -30))
PAW_BACK = pose(PAW, knee_b=(-14, -12), foot_b=(-26, -1))
SHOULDER = pose(RUSH, head=(5, -45), neck=(7, -40), elb_f=(15, -33), hand_f=(7, -27),
                knee_f=(14, -14), foot_f=(20, 0), knee_b=(-12, -10), foot_b=(-22, 0))
HEAD_BACK = pose(SHOULDER, head=(2, -50), neck=(4, -44))
HEADBUTT = pose(IDLE, head=(16, -48), neck=(10, -45), hip=(0, -28), elb_f=(10, -36), hand_f=(16, -30),
                elb_b=(0, -36), hand_b=(4, -30))

# Hurtboxes (x, y, w, h)
STAND_BOX = (-11, -64, 22, 64)
CROUCH_BOX = (-12, -40, 26, 40)
AIR_BOX = (-10, -60, 20, 46)


class Move:
    def __init__(self, name, pose, startup, active, recovery, damage, hitbox=None,
                 hitstun=14, blockstun=10, push=2.5, level="mid", knockdown=False,
                 windup=None, chip=0, sfx="light", hitstop=6, impulse=None, drive=0.0,
                 invuln=0, projectile=None, cancel=False, air=False, crouch=False,
                 launch=(2.0, 4.5), anim=None, hits=1, rehit=8, charge=0, followup=None, fx=None):
        self.name = name
        self.pose = pose
        self.windup = windup
        self.startup = startup
        self.active = active
        self.recovery = recovery
        self.total = startup + active + recovery
        self.damage = damage        # one number, or one per hit for multi-hit moves
        self.hitbox = hitbox
        self.hitstun = hitstun
        self.blockstun = blockstun
        self.push = push
        self.level = level          # mid: block high or low; low: crouch-block; high: stand-block
        self.knockdown = knockdown
        self.chip = chip            # damage dealt even when blocked
        self.sfx = sfx
        self.hitstop = hitstop
        self.impulse = impulse      # (vx, vy) applied on first active frame
        self.drive = drive          # forward speed held during active frames
        self.invuln = invuln        # invulnerable frames from the start
        self.projectile = projectile
        self.cancel = cancel        # can be cancelled into a special after contact
        self.air = air
        self.crouch = crouch
        self.launch = launch        # (vx, vy) when this knocks down
        self.anim = anim            # keyframes [(frame, pose), ...] instead of windup/pose blending
        self.hits = hits            # multi-hit: up to this many hits, `rehit` frames apart
        self.rehit = rehit
        self.charge = charge        # hold the button at the end of startup for up to this many frames
        self.followup = followup    # move key started automatically when this hits (not on block)
        self.fx = fx                # extra effects drawn with the fighter (see art.py)
        self.special = projectile is not None or impulse is not None or drive > 0

    def damage_for(self, hit):
        return self.damage[min(hit, len(self.damage) - 1)] if isinstance(self.damage, tuple) else self.damage


class Special:
    def __init__(self, name, motion, button, key, notation):
        self.name = name
        self.motion = motion        # numpad notation relative to facing: 6 = forward, 2 = down
        self.button = button
        self.key = key
        self.notation = notation


QCF = (2, 3, 6)
QCB = (2, 1, 4)
DP = (6, 2, 3)


class Character:
    def __init__(self, name, title, blurb, style, look, alt_look, scale, health, walk, back,
                 jump_vx, jump_vy, moves, specials, power, speed):
        self.name = name
        self.title = title
        self.blurb = blurb
        self.style = style          # which drawing function in art.py
        self.look = look            # colours, see art.py
        self.alt_look = alt_look    # second colours for mirror matches
        self.scale = scale
        self.health = health
        self.walk = walk
        self.back = back
        self.jump_vx = jump_vx
        self.jump_vy = jump_vy
        self.moves = moves
        self.specials = specials
        self.power = power          # 1-5, shown on select screen
        self.speed = speed


KAZE = Character(
    "KAZE", "Storm Runner", "Fast. Zones with orbs, anti-airs with a rising kick.", "kaze",
    dict(skin=(232, 190, 150), gi=(40, 120, 205), gi_hi=(110, 175, 240), band=(250, 210, 60),
         hair=(30, 30, 40), belt=(28, 22, 30), wrap=(235, 235, 245)),
    dict(skin=(232, 190, 150), gi=(40, 170, 90), gi_hi=(120, 215, 150), band=(240, 240, 240),
         hair=(120, 60, 20), belt=(28, 22, 30), wrap=(250, 210, 60)),
    scale=1.0, health=1000, walk=1.9, back=1.5, jump_vx=2.4, jump_vy=6.2,
    moves={
        "stand_p": Move("Jab", JAB, 3, 3, 7, 40, (16, -52, 18, 10), cancel=True, push=2.0),
        "stand_k": Move("Snap Kick", KICK, 7, 4, 14, 80, (16, -46, 22, 12), windup=KICK_UP,
                        hitstun=18, blockstun=13, push=3.0, sfx="heavy", hitstop=9),
        "crouch_p": Move("Low Jab", CJAB, 4, 3, 7, 35, (16, -34, 16, 10), cancel=True, crouch=True, push=2.0),
        "crouch_k": Move("Sweep", SWEEP, 8, 4, 20, 70, (14, -10, 24, 10), level="low", knockdown=True,
                         crouch=True, sfx="heavy", hitstop=8, launch=(1.0, 3.0)),
        "air_p": Move("Air Punch", AIR_P, 4, 6, 0, 55, (12, -44, 16, 12), level="high", air=True,
                      hitstun=16, blockstun=12),
        "air_k": Move("Air Kick", AIR_K, 5, 8, 0, 75, (12, -26, 22, 14), level="high", air=True,
                      hitstun=18, blockstun=13, sfx="heavy", hitstop=8),
        # 2 hits, or 3 when charged by holding P
        "sp1": Move("Tempest Orb", PUSH, 12, 2, 22, 50, hitstun=20, blockstun=16, push=1.5, chip=8,
                    sfx="heavy", hitstop=7, charge=40, fx="tempest",
                    anim=[(0, IDLE), (6, GATHER), (12, CHARGE), (13, PUSH), (24, PUSH), (36, IDLE)],
                    projectile=dict(speed=3.2, x=28, y=42, w=16, h=14, style="orb", hits=2)),
        # 3 hits: two rising spins, then an axe kick on the way down that also hits crouchers
        "sp2": Move("Cyclone Kick", SPIN, 3, 23, 14, (40, 40, 55), [(0, (-6, -70, 30, 62)), (17, (4, -44, 28, 44))],
                    knockdown=True, invuln=7, impulse=(1.5, 5.0), sfx="heavy", hitstop=8, chip=8,
                    push=1.0, hitstun=16, launch=(2.0, 5.5), hits=3, rehit=8, fx="cyclone",
                    anim=[(0, IDLE), (3, CROUCH), (6, SPIN), (9, SPIN_BACK), (12, SPIN), (15, SPIN_BACK),
                          (18, AXE_UP), (24, AXE_DOWN), (34, AXE_DOWN), (40, CROUCH)]),
    },
    specials=[
        Special("Cyclone Kick", DP, "b", "sp2", "F, D, DF + K"),
        Special("Tempest Orb", QCF, "a", "sp1", "D, DF, F + P (hold P)"),
    ],
    power=2, speed=4,
)

BRAKK = Character(
    "BRAKK", "Iron Ram", "Slow and heavy. Big damage, rock pillars and a charging ram.", "brakk",
    dict(skin=(196, 140, 100), vest=(190, 50, 40), trim=(235, 185, 60), pants=(72, 58, 66),
         iron=(150, 156, 168), leather=(112, 72, 42), boot=(40, 32, 34), hair=(22, 20, 22), ink=(70, 40, 60)),
    dict(skin=(196, 140, 100), vest=(110, 70, 160), trim=(230, 230, 240), pants=(50, 54, 70),
         iron=(200, 170, 80), leather=(70, 50, 40), boot=(30, 30, 36), hair=(200, 200, 200), ink=(40, 60, 90)),
    scale=1.15, health=1150, walk=1.4, back=1.2, jump_vx=2.0, jump_vy=5.8,
    moves={
        "stand_p": Move("Hammer Jab", JAB, 5, 3, 9, 60, (16, -52, 18, 10), cancel=True, push=2.5),
        "stand_k": Move("Boot", KICK, 9, 4, 16, 105, (16, -46, 22, 12), windup=KICK_UP,
                        hitstun=19, blockstun=14, push=3.5, sfx="heavy", hitstop=10),
        "crouch_p": Move("Low Hook", CJAB, 5, 3, 9, 50, (16, -34, 16, 10), cancel=True, crouch=True, push=2.5),
        "crouch_k": Move("Leg Sweep", SWEEP, 10, 4, 22, 90, (14, -10, 24, 10), level="low", knockdown=True,
                         crouch=True, sfx="heavy", hitstop=9, launch=(1.0, 3.0)),
        "air_p": Move("Air Hammer", AIR_P, 5, 6, 0, 70, (12, -44, 16, 12), level="high", air=True,
                      hitstun=16, blockstun=12),
        "air_k": Move("Drop Kick", AIR_K, 6, 8, 0, 95, (12, -26, 22, 14), level="high", air=True,
                      hitstun=18, blockstun=13, sfx="heavy", hitstop=9),
        # rock pillars that hit twice; the second one launches. Must be blocked low.
        "sp1": Move("Earthsplitter", SLAM, 18, 2, 24, (55, 60), hitstun=22, blockstun=16, push=1.0, chip=8,
                    sfx="heavy", hitstop=9, level="low", knockdown=True, launch=(1.5, 5.0), fx="slam",
                    anim=[(0, IDLE), (8, FISTS_UP), (13, lift(FISTS_UP, 8)), (18, SLAM), (30, SLAM), (44, IDLE)],
                    projectile=dict(speed=2.4, x=24, y=10, w=20, h=20, style="pillars", hits=2)),
        # shoulder charge; when it hits (not on block) Brakk follows up with a headbutt
        "sp2": Move("Ram Charge", SHOULDER, 14, 16, 16, 80, (6, -54, 20, 32), push=1.0, chip=8,
                    hitstun=26, drive=4.2, sfx="heavy", hitstop=10, followup="ram_head", fx="ram",
                    anim=[(0, IDLE), (5, PAW), (8, PAW_BACK), (11, PAW), (14, RUSH), (17, SHOULDER),
                          (30, SHOULDER), (46, IDLE)]),
        "ram_head": Move("Headbutt", HEADBUTT, 5, 3, 20, 60, (8, -60, 20, 16), knockdown=True, drive=1.5,
                         sfx="heavy", hitstop=12, launch=(3.0, 4.5), fx="headbutt",
                         anim=[(0, SHOULDER), (4, HEAD_BACK), (6, HEADBUTT), (12, HEADBUTT), (28, IDLE)]),
    },
    specials=[
        Special("Earthsplitter", QCF, "a", "sp1", "D, DF, F + P"),
        Special("Ram Charge", QCB, "b", "sp2", "D, DB, B + K"),
    ],
    power=5, speed=2,
)

ROSTER = [KAZE, BRAKK]
