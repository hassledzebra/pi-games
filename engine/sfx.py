"""Procedurally synthesised sound effects - no audio files to ship.
Silently disabled if the machine has no audio device."""
import array

import pygame


class Sfx:
    def __init__(self, enabled=True):
        self.sounds = {}
        self.enabled = False
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
        except pygame.error:
            return
        init = pygame.mixer.get_init()
        if not init or init[1] != -16:
            return
        self.rate, _, self.channels = init
        self.enabled = True

    def synth(self, name, seconds, fn, volume=0.5):
        """fn(t_seconds, k_progress_0_to_1) -> sample in -1..1"""
        if not self.enabled:
            return
        n = int(self.rate * seconds)
        buf = array.array("h")
        for i in range(n):
            v = fn(i / self.rate, i / n)
            s = int(max(-1.0, min(1.0, v)) * volume * 32767)
            buf.extend([s] * self.channels)
        self.sounds[name] = pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        s = self.sounds.get(name)
        if s is not None:
            s.play()
