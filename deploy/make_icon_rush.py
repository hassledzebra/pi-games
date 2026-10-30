"""Draw the Pi Rush desktop icon (Mitzi and Gizmo racing for a crate) with the game's own sprites.

    python deploy/make_icon_rush.py [out.png]      (default: deploy/pi-rush.png)
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from games.racing import art  # noqa: E402
from games.racing.data import ROSTER  # noqa: E402

CELL = 96       # icon size in game pixels
ZOOM = 3        # scaled up with hard edges, like the game itself on HDMI


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "deploy", "pi-rush.png")
    pygame.init()
    icon = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    pygame.draw.rect(icon, (60, 120, 210), (0, 0, CELL, CELL), border_radius=16)
    horizon = 38
    for y in range(4, CELL - 4):                            # sky, then grass
        k = y / horizon
        if y < horizon:
            color = (int(60 + 100 * k), int(120 + 90 * k), int(210 + 30 * k))
        else:
            color = (70, 140, 60) if (y // 6) % 2 else (62, 128, 54)
        inset = 4 if 6 < y < CELL - 6 else 6
        pygame.draw.line(icon, color, (inset, y), (CELL - inset - 1, y))
    for hx, r in ((10, 12), (30, 16), (56, 14), (80, 18), (98, 12)):   # distant hills
        pygame.draw.circle(icon, (70, 110, 150), (hx, horizon + 4), r)
    # the road, converging on the horizon, with red/white kerbs and lane dashes
    road = [(2, CELL - 4), (CELL - 2, CELL - 4), (CELL // 2 + 8, horizon), (CELL // 2 - 8, horizon)]
    pygame.draw.polygon(icon, (200, 60, 50), [(p[0] - (6 if i < 2 else 2) * (1 if i in (0, 3) else -1), p[1])
                                              for i, p in enumerate(road)])
    pygame.draw.polygon(icon, (80, 80, 90), road)
    for i, y in enumerate(range(horizon + 4, CELL - 4, 8)):
        k = (y - horizon) / (CELL - horizon)
        w = max(1, int(1 + 3 * k))
        if i % 2 == 0:
            pygame.draw.rect(icon, (200, 200, 190), (CELL // 2 - w // 2, y, w, 4 + int(3 * k)))
    for y in range(horizon, CELL - 4, 5):                   # kerb stripes
        k = (y - horizon) / (CELL - horizon)
        xl, xr = CELL // 2 - 8 - int(38 * k), CELL // 2 + 8 + int(38 * k)
        if (y // 5) % 2:
            pygame.draw.rect(icon, (235, 235, 235), (xl - 4, y, 4, 5))
            pygame.draw.rect(icon, (235, 235, 235), (xr, y, 4, 5))
    # racers: Gizmo a little behind on the left, Mitzi in front on the right, a crate ahead and a banana dropped
    mitzi, gizmo = ROSTER[0], ROSTER[1]
    crate = art.item_sprite("crate")
    icon.blit(pygame.transform.scale(crate, (14, 14)), (CELL // 2 - 7, horizon + 2))
    back = art.kart_rear(gizmo, "normal", lean=1, w=40, h=26)
    icon.blit(art.shadow(40, 8), (12, 70))
    icon.blit(back, (12, 48))
    banana = art.item_sprite("banana")
    icon.blit(banana, (8, CELL - 20))
    front = art.kart_rear(mitzi, "win", w=52, h=34)
    icon.blit(art.shadow(52, 10), (40, CELL - 12))
    icon.blit(front, (40, CELL - 42))
    pygame.draw.rect(icon, (20, 16, 28), (0, 0, CELL, CELL), width=3, border_radius=16)

    pygame.image.save(pygame.transform.scale(icon, (CELL * ZOOM, CELL * ZOOM)), out)
    print("wrote", out)


if __name__ == "__main__":
    main()
