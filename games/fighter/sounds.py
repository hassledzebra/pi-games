"""Sound effects, synthesised at startup (about half a second on a Pi 3)."""
import math
import random


def build(sfx):
    rng = random.Random(1)

    def noise():
        return rng.uniform(-1, 1)

    def square(f, t):
        return 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0

    sfx.synth("light", 0.07, lambda t, k: noise() * (1 - k) ** 2, 0.5)
    sfx.synth("heavy", 0.16, lambda t, k: (noise() * 0.6 + math.sin(2 * math.pi * 90 * t)) * (1 - k) ** 2, 0.6)
    sfx.synth("block", 0.06, lambda t, k: square(1100, t) * (1 - k) ** 3 * 0.5 + noise() * 0.3 * (1 - k), 0.35)
    sfx.synth("whoosh", 0.09, lambda t, k: noise() * math.sin(math.pi * k) * 0.5, 0.2)
    sfx.synth("special", 0.28, lambda t, k: math.sin(2 * math.pi * (180 + 500 * k) * t) * (1 - k), 0.35)
    sfx.synth("thud", 0.14, lambda t, k: (math.sin(2 * math.pi * 60 * t) + noise() * 0.4) * (1 - k) ** 2, 0.6)
    sfx.synth("ko", 0.7, lambda t, k: (math.sin(2 * math.pi * (240 - 160 * k) * t) + noise() * 0.3) * (1 - k), 0.5)
    sfx.synth("select", 0.05, lambda t, k: square(880, t) * (1 - k), 0.15)
    sfx.synth("confirm", 0.12, lambda t, k: square(660 if k < 0.5 else 990, t) * (1 - k), 0.18)
    sfx.synth("round", 0.3, lambda t, k: square(523 if k < 0.4 else 784, t) * (1 - k) * 0.8, 0.18)
    # crowd: filtered noise that swells and fades, the roar is longer and deeper
    sfx.synth("cheer", 0.45, lambda t, k: (noise() * 0.5 + math.sin(2 * math.pi * (300 + 80 * math.sin(t * 40)) * t)
                                          * 0.3) * math.sin(math.pi * k) ** 0.5, 0.22)
    sfx.synth("roar", 1.4, lambda t, k: (noise() * 0.6 + math.sin(2 * math.pi * (160 + 40 * math.sin(t * 9)) * t)
                                        * 0.35) * min(1.0, k * 4) * (1 - k) ** 0.7, 0.3)
