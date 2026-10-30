"""Cached text rendering. Font.render is slow on a Pi, so each distinct string
is rendered once and reused."""
import pygame

_fonts = {}
_cache = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        f = _fonts[size] = pygame.font.Font(None, size)
    return f


def render(s, size, color, shadow=(0, 0, 0)):
    key = (s, size, color, shadow)
    surf = _cache.get(key)
    if surf is None:
        if len(_cache) > 500:
            _cache.clear()
        fg = font(size).render(s, False, color)
        if shadow:
            back = font(size).render(s, False, shadow)
            surf = pygame.Surface((fg.get_width() + 1, fg.get_height() + 1), pygame.SRCALPHA)
            surf.blit(back, (1, 1))
            surf.blit(fg, (0, 0))
        else:
            surf = fg
        _cache[key] = surf
    return surf


def draw(surface, s, size, color, pos, align="center", shadow=(0, 0, 0)):
    surf = render(s, size, color, shadow)
    x, y = pos
    if align == "center":
        x -= surf.get_width() // 2
    elif align == "right":
        x -= surf.get_width()
    surface.blit(surf, (x, y))
    return surf.get_width()
