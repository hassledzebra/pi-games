"""Window + main loop.

The game draws to a small fixed-resolution surface; pygame.SCALED lets SDL's
GPU renderer scale it to the real screen, which is far cheaper on a Pi than
pygame.transform.scale on the CPU.

Logic is frame-locked: exactly one update per rendered frame at 60 fps. If a
slow Pi drops frames the game runs slower instead of skipping input frames,
which is what fighting games want (frame data stays exact).
"""
import os
import platform
import sys
import time

import pygame

from . import text
from .input import InputManager

FPS = 60


def on_pi():
    return sys.platform.startswith("linux") and platform.machine() in ("aarch64", "armv7l", "armv6l")


class Scene:
    def __init__(self, app):
        self.app = app

    def handle_event(self, event):
        pass

    def update(self):
        """Advance one 1/60 s step."""

    def draw(self, surface):
        pass


class App:
    def __init__(self, title, size, fullscreen=False):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.title = title
        self.size = size
        self.fullscreen = fullscreen
        self.screen = self._open_window()
        self.input = InputManager()
        self.clock = pygame.time.Clock()
        self.scene = None
        self._next_scene = None
        self.running = True
        self.show_fps = False
        self.sfx = None
        self.settings = {}

    def _open_window(self):
        pygame.display.set_caption(self.title)
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        for kwargs in ({"flags": flags, "vsync": 1}, {"flags": flags}, {}):
            try:
                screen = pygame.display.set_mode(self.size, **kwargs)
                break
            except pygame.error:
                continue
        pygame.mouse.set_visible(not self.fullscreen)
        return screen

    def toggle_fullscreen(self):
        pygame.display.toggle_fullscreen()
        self.fullscreen = not self.fullscreen
        pygame.mouse.set_visible(not self.fullscreen)

    def switch(self, scene):
        """Change scene at the start of the next frame."""
        self._next_scene = scene

    def quit(self):
        self.running = False

    def play(self, name):
        if self.sfx:
            self.sfx.play(name)

    def frame(self):
        if self._next_scene is not None:
            self.scene, self._next_scene = self._next_scene, None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            self.input.handle_event(event)
            self.scene.handle_event(event)
        self.input.update()
        self.scene.update()
        self.scene.draw(self.screen)
        if self.show_fps:
            text.draw(self.screen, "%d FPS" % round(self.clock.get_fps()), 14,
                      (255, 255, 0), (self.size[0] - 2, self.size[1] - 12), align="right")
        self.flip_t = time.perf_counter()
        pygame.display.flip()

    def run(self, scene):
        self.scene = scene
        timing = os.environ.get("PI_TIMING")              # PI_TIMING=1: log real frame times to stderr
        work = flip = n = 0.0
        while self.running:
            if timing:
                t0 = time.perf_counter()
                self.frame()
                t1 = time.perf_counter()
                self.clock.tick(FPS)
                work += self.flip_t - t0
                flip += t1 - self.flip_t
                n += 1
                if n >= 300:
                    print("frame %.2f ms update+draw + %.2f ms flip/vsync  (%.0f fps)" %
                          (work / n * 1000, flip / n * 1000, self.clock.get_fps()), file=sys.stderr, flush=True)
                    work = flip = n = 0.0
            else:
                self.frame()
                self.clock.tick(FPS)
        pygame.quit()
