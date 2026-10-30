"""Racers, items and tracks for Pi Rush.

Stats are 1..5 and map onto real numbers in kart.py. Tracks are a handful of
control points (in a 1024x1024 world), a road width and a theme; world.py turns
them into the centreline, the painted ground and the surface grid.
"""

WIDTH, HEIGHT = 480, 270   # 4x on a 1080p screen; 384x216 (5x) is the cheaper option
WORLD = 1024              # world size in px (square)
LAPS = 3


class Racer:
    def __init__(self, name, species, vehicle, shape, body, trim, skin, speed, accel, handling, weight, blurb):
        self.name, self.species, self.vehicle, self.shape = name, species, vehicle, shape
        self.body, self.trim, self.skin = body, trim, skin      # kart colour, kart trim, character colour
        self.speed, self.accel, self.handling, self.weight = speed, accel, handling, weight
        self.blurb = blurb


# species (head drawing in art.py): frog, robot, cat, penguin, dino, alien
# shape (vehicle drawing in art.py): kart, buggy, mower, boat, trike, saucer
ROSTER = [
    Racer("MITZI", "cat", "Comet", "kart", (235, 70, 150), (255, 230, 240), (250, 240, 230),
          5, 3, 3, 2, "Fastest paws on the grid."),
    Racer("GIZMO", "robot", "Spark Buggy", "buggy", (255, 210, 40), (40, 40, 48), (170, 180, 200),
          3, 5, 3, 2, "Off the line first. Beep."),
    Racer("WADDLE", "penguin", "Lawn Hog", "mower", (90, 170, 70), (200, 150, 80), (40, 44, 60),
          2, 3, 5, 3, "Slow, but grips like turf."),
    Racer("CHOMP", "dino", "Tugboat", "boat", (50, 80, 150), (220, 60, 50), (80, 190, 120),
          4, 2, 2, 5, "Heavy. Bumps win."),
    Racer("HOPPER", "frog", "Rocket Trike", "trike", (255, 130, 40), (80, 220, 240), (110, 200, 70),
          3, 4, 4, 1, "Light and twitchy."),
    Racer("ZORB", "alien", "Saucer", "saucer", (140, 80, 200), (90, 230, 200), (200, 210, 160),
          4, 4, 2, 3, "Drifts for days."),
]


# ------------------------------------------------------------------ items
# kind: name, short HUD label, "behind" items are dropped where they make sense
ITEMS = {
    "banana": {"label": "BANANA", "blurb": "Slip on it: spin out"},
    "chicken": {"label": "CHICKEN", "blurb": "Squawks ahead and bonks the first kart"},
    "pie": {"label": "PIE", "blurb": "Splat! The victim's screen gets creamed"},
    "gum": {"label": "GUM", "blurb": "Drop behind: sticks whoever drives over it"},
    "balloon": {"label": "BALLOON", "blurb": "Lob it: the splash soaks everyone near"},
    "pepper": {"label": "PEPPER", "blurb": "Hot! Big speed boost, flames out the back"},
    "shield": {"label": "SHIELD", "blurb": "A bubble that absorbs the next hit"},
    "pogo": {"label": "POGO", "blurb": "Big jump: clears hazards and small walls"},
    "magnet": {"label": "MAGNET", "blurb": "Pulls crates and dropped items to you"},
}
# roll weights by race position (1st .. 6th): leaders get defensive junk, tail gets the good stuff
ITEM_WEIGHTS = [
    # banana chicken pie gum balloon pepper shield pogo magnet
    (5, 0, 1, 4, 1, 0, 4, 1, 1),    # 1st
    (4, 1, 2, 3, 2, 1, 3, 1, 1),    # 2nd
    (3, 2, 2, 2, 2, 2, 2, 1, 1),    # 3rd
    (2, 3, 3, 1, 2, 3, 1, 1, 1),    # 4th
    (1, 3, 3, 0, 2, 4, 1, 2, 1),    # 5th
    (0, 3, 3, 0, 2, 5, 0, 2, 1),    # 6th
]
ITEM_ORDER = ("banana", "chicken", "pie", "gum", "balloon", "pepper", "shield", "pogo", "magnet")
CRATE_RESPAWN = 300       # frames (5 s)


class Track:
    def __init__(self, name, theme, points, road_w, blurb, ice=(), lava=(), boosts=(), ramp=None,
                 tunnel=None, crates=()):
        self.name, self.theme, self.points, self.road_w, self.blurb = name, theme, points, road_w, blurb
        self.ice = ice          # centreline indices (of ~240) with an ice patch
        self.lava = lava        # centreline indices with a lava pool beside the road
        self.boosts = boosts    # (index, lateral offset) boost pads
        self.ramp = ramp        # centreline index of a jump ramp
        self.tunnel = tunnel    # (start index, end index) darkened tunnel
        self.crates = crates    # centreline indices with a row of 3 item crates


TRACKS = [
    Track("HARBOR LOOP", "harbor",
          [(200, 170), (520, 130), (780, 230), (860, 470), (700, 650), (520, 570),
           (420, 770), (200, 830), (120, 610), (260, 430)],
          56, "Docks and cranes. Wide and friendly.",
          boosts=((60, 0), (150, -10), (205, 10)), crates=(25, 105, 185)),
    Track("CINDER PASS", "cinder",
          [(160, 200), (420, 120), (640, 190), (560, 370), (780, 430), (860, 640),
           (640, 820), (420, 700), (260, 860), (120, 640), (240, 420)],
          44, "Basalt S-bends past the lava. One jump.",
          lava=(30, 95, 140, 200), boosts=((20, 0), (170, 0)), ramp=112, crates=(50, 130, 225)),
    Track("FROSTBITE RIDGE", "frost",
          [(180, 160), (500, 110), (820, 170), (880, 420), (760, 560), (840, 760),
           (560, 880), (330, 760), (420, 540), (180, 460)],
          50, "Ice patches and a tunnel. Hold your line.",
          ice=(45, 110, 175, 215), boosts=((80, 0), (190, 0)), tunnel=(130, 150), crates=(20, 95, 165)),
    Track("NEON ROOFTOPS", "neon",
          [(140, 150), (430, 100), (760, 150), (900, 360), (800, 560), (580, 480),
           (640, 720), (420, 880), (180, 760), (120, 520), (320, 360), (260, 250)],
          48, "Night city. Boost pads on the bridges.",
          boosts=((35, -8), (36, 8), (120, 0), (195, -8), (196, 8)), crates=(60, 150, 230)),
    Track("ORCHARD OVAL", "orchard",
          [(200, 300), (512, 180), (824, 300), (824, 724), (512, 844), (200, 724)],
          60, "A simple oval for practice.", boosts=((100, 0), (220, 0)), crates=(40, 160)),
]
GP_TRACKS = (0, 1, 2, 3)
GP_POINTS = (10, 7, 5, 3, 2, 1)
