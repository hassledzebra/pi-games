"""Draw the desktop icon (Kaze vs Brakk mid-fight) with the game's own sprites.

    python deploy/make_icon.py [out.png]      (default: deploy/pi-brawl.png)
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from games.fighter.data import BRAKK, KAZE  # noqa: E402
from games.fighter.fighter import GROUND_Y, Fighter  # noqa: E402

CELL = 96       # icon size in game pixels
ZOOM = 3        # scaled up with hard edges, like the game itself on HDMI


def pose(fighter, move_key):
    fighter.start_move(fighter.moves[move_key])
    fighter.t = fighter.move.startup + 1        # mid active frames: limbs fully extended


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "deploy", "pi-brawl.png")
    pygame.init()
    stage = pygame.Surface((160, GROUND_Y + 8))
    stage.fill((255, 0, 255))
    stage.set_colorkey((255, 0, 255))
    kaze, brakk = Fighter(KAZE, x=60, facing=1), Fighter(BRAKK, x=104, facing=-1)
    pose(kaze, "stand_k")
    pose(brakk, "stand_p")
    for f in (brakk, kaze):
        f.draw(stage)

    icon = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    # dusk sky in a rounded square, with a floor line
    pygame.draw.rect(icon, (40, 20, 60), (0, 0, CELL, CELL), border_radius=16)
    for y in range(4, CELL - 4):
        k = y / CELL
        color = (int(60 + 180 * k), int(30 + 60 * k), int(90 - 30 * k))
        pygame.draw.line(icon, color, (4 if 6 < y < CELL - 6 else 6, y), (CELL - 5 if 6 < y < CELL - 6 else CELL - 7, y))
    pygame.draw.rect(icon, (60, 40, 50), (4, CELL - 12, CELL - 8, 8), border_bottom_left_radius=8,
                     border_bottom_right_radius=8)
    pygame.draw.rect(icon, (20, 16, 28), (0, 0, CELL, CELL), width=3, border_radius=16)
    # crop the fighters so their feet sit on the floor line
    body = pygame.mask.from_surface(stage).get_bounding_rects()[0]
    src = pygame.Rect(0, 0, CELL - 8, CELL - 14)
    src.midbottom = (body.centerx, GROUND_Y + 2)
    icon.blit(stage, (4, 4), src)

    pygame.image.save(pygame.transform.scale(icon, (CELL * ZOOM, CELL * ZOOM)), out)
    print("wrote", out)


if __name__ == "__main__":
    main()
