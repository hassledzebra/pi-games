"""Draw the Pi Strum desktop icon: a slice of the note highway with the game's own string colours.

    python deploy/make_icon_strum.py [out.png]      (default: deploy/pi-strum.png)
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from games.guitar.scenes import BG, GOLD, GREEN, STRING_COLORS, WHITE  # noqa: E402

CELL = 96
ZOOM = 3


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "deploy", "pi-strum.png")
    pygame.init()
    import math
    font = pygame.font.Font(None, 17)
    icon = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    pygame.draw.rect(icon, BG, (0, 0, CELL, CELL), border_radius=16)
    for y in range(6, CELL - 6):                                # subtle vertical gradient
        k = y / CELL
        pygame.draw.line(icon, (int(18 + 14 * k), int(20 + 16 * k), int(28 + 26 * k)), (4, y), (CELL - 5, y))
    # six strings, high e at the top, thicker towards the bass strings
    lanes = [14 + i * 13 for i in range(6)]
    for i, y in enumerate(lanes):
        s = 5 - i
        pygame.draw.line(icon, tuple(c // 2 for c in STRING_COLORS[s]), (4, y), (CELL - 5, y), 1 + (s < 3))
    # beat grid and the "now" line
    for x in (46, 70, 94):
        pygame.draw.line(icon, (44, 48, 62), (x, 8), (x, CELL - 9))
    pygame.draw.line(icon, WHITE, (22, 6), (22, CELL - 7), 2)
    # notes: two already hit (green), the rest on their way in string colours
    notes = [(2, 10, 3, GREEN, 18), (4, 22, 0, GREEN, 16), (3, 40, 2, None, 22), (5, 56, 0, None, 18),
             (1, 72, 5, None, 20), (4, 84, 3, None, 12)]
    for lane_from_top, x, fret, col, w in notes:
        y = lanes[lane_from_top]
        col = col or STRING_COLORS[5 - lane_from_top]
        pygame.draw.rect(icon, tuple(c // 2 for c in col), (x, y - 3, w, 7), border_radius=3)
        pygame.draw.circle(icon, col, (x, y), 7)
        label = font.render(str(fret), False, (20, 20, 20))
        icon.blit(label, (x - label.get_width() // 2 + 1, y - label.get_height() // 2 + 1))
    # a pick top right and a gold star bottom left
    pick = [(62, 8), (84, 8), (73, 24)]
    pygame.draw.polygon(icon, (235, 200, 90), pick)
    pygame.draw.polygon(icon, (120, 90, 30), pick, 2)
    star = []
    for k in range(10):
        r = 8 if k % 2 == 0 else 3.5
        a = -math.pi / 2 + k * math.pi / 5
        star.append((13 + r * math.cos(a), 86 + r * math.sin(a)))
    pygame.draw.polygon(icon, GOLD, star)
    pygame.draw.rect(icon, (20, 16, 28), (0, 0, CELL, CELL), width=3, border_radius=16)
    pygame.image.save(pygame.transform.scale(icon, (CELL * ZOOM, CELL * ZOOM)), out)
    print("wrote", out)


if __name__ == "__main__":
    main()
