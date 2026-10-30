"""Sound effects, synthesised at startup (about a second on a Pi 3)."""
import math
import random


def build(sfx):
    rng = random.Random(2)

    def noise():
        return rng.uniform(-1, 1)

    def square(f, t):
        return 1.0 if math.sin(2 * math.pi * f * t) > 0 else -1.0

    def sine(f, t):
        return math.sin(2 * math.pi * f * t)

    # menus and race flow
    sfx.synth("select", 0.05, lambda t, k: square(880, t) * (1 - k), 0.15)
    sfx.synth("confirm", 0.12, lambda t, k: square(660 if k < 0.5 else 990, t) * (1 - k), 0.18)
    sfx.synth("count", 0.12, lambda t, k: sine(440, t) * (1 - k), 0.3)
    sfx.synth("go", 0.4, lambda t, k: sine(880, t) * (1 - k) ** 0.5, 0.3)
    sfx.synth("lap", 0.25, lambda t, k: square(523 if k < 0.5 else 784, t) * (1 - k) * 0.7, 0.2)
    sfx.synth("finish", 0.8, lambda t, k: square((523, 659, 784, 1046)[min(3, int(k * 4))], t) * (1 - k) * 0.6, 0.22)
    # driving
    sfx.synth("drift", 0.18, lambda t, k: noise() * (1 - k) * 0.6, 0.18)
    sfx.synth("boost", 0.35, lambda t, k: sine(200 + 900 * k, t) * (1 - k) + noise() * 0.2 * (1 - k), 0.3)
    sfx.synth("bump", 0.1, lambda t, k: (sine(80, t) + noise() * 0.5) * (1 - k) ** 2, 0.4)
    sfx.synth("land", 0.12, lambda t, k: (sine(60, t) + noise() * 0.3) * (1 - k) ** 2, 0.4)
    sfx.synth("spin", 0.4, lambda t, k: sine(600 - 400 * k, t) * (1 - k), 0.25)
    # items
    sfx.synth("pickup", 0.15, lambda t, k: sine(660 if k < 0.5 else 1320, t) * (1 - k), 0.2)
    sfx.synth("drop", 0.08, lambda t, k: sine(300 - 150 * k, t) * (1 - k), 0.25)
    sfx.synth("throw", 0.15, lambda t, k: noise() * math.sin(math.pi * k) * 0.6, 0.25)
    sfx.synth("squawk", 0.35, lambda t, k: square(700 + 300 * math.sin(t * 60), t) * (1 - k) ** 0.5 * 0.6, 0.22)
    sfx.synth("slip", 0.3, lambda t, k: sine(900 - 700 * k, t) * (1 - k), 0.25)
    sfx.synth("splat", 0.22, lambda t, k: (noise() * 0.7 + sine(90, t) * 0.5) * (1 - k) ** 2, 0.4)
    sfx.synth("gum", 0.25, lambda t, k: sine(150 + 100 * math.sin(t * 30), t) * (1 - k), 0.3)
    sfx.synth("splash", 0.4, lambda t, k: noise() * (1 - k) ** 1.5 * 0.6 + sine(200, t) * 0.2 * (1 - k), 0.3)
    sfx.synth("sizzle", 0.6, lambda t, k: (noise() * 0.5 + sine(150 + 1200 * k, t) * 0.6) * (1 - k) ** 0.7, 0.3)
    sfx.synth("shield", 0.3, lambda t, k: sine(400 + 500 * k, t) * (1 - k) * 0.6 + sine(800 + 1000 * k, t) * 0.3 * (1 - k), 0.25)
    sfx.synth("pop", 0.1, lambda t, k: (noise() * 0.5 + sine(500 - 300 * k, t)) * (1 - k) ** 2, 0.35)
    sfx.synth("boing", 0.35, lambda t, k: sine(220 + 500 * (1 - k) ** 2 * math.sin(k * 12), t) * (1 - k), 0.3)
    sfx.synth("hum", 0.5, lambda t, k: (sine(110, t) * 0.6 + sine(220, t) * 0.3) * math.sin(math.pi * k), 0.2)
    sfx.synth("cheer", 0.6, lambda t, k: (noise() * 0.5 + sine(300 + 80 * math.sin(t * 40), t) * 0.3) * math.sin(math.pi * k) ** 0.5, 0.22)
