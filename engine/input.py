"""Maps keyboards and gamepads to abstract actions per player.

Actions: up, down, left, right, a (punch), b (kick), start.
Each input object exposes `held` and `pressed` (pressed this frame) sets, so
game code never touches raw keys - and an AI can drive a fighter through the
same interface (see VirtualInput).
"""
import pygame

KEYMAPS = (
    {  # player 1: left side of the keyboard
        pygame.K_w: "up", pygame.K_s: "down", pygame.K_a: "left", pygame.K_d: "right",
        pygame.K_f: "a", pygame.K_g: "b", pygame.K_ESCAPE: "start",
    },
    {  # player 2: arrows + K/L (numpad 1/2 also work)
        pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
        pygame.K_k: "a", pygame.K_l: "b", pygame.K_KP1: "a", pygame.K_KP2: "b",
        pygame.K_RETURN: "start", pygame.K_KP_ENTER: "start",
    },
)

# Xbox-style layout (SDL on Windows and Linux xpad): A/X punch, B/Y kick.
# 9 is start on most generic USB "SNES" pads.
PAD_BUTTONS = {0: "a", 2: "a", 1: "b", 3: "b", 7: "start", 9: "start"}
DEADZONE = 0.5


class VirtualInput:
    """Input state set by code (AI, demo, tests)."""

    def __init__(self):
        self.held = frozenset()
        self.pressed = frozenset()

    def set(self, held, pressed=()):
        self.held = frozenset(held) | frozenset(pressed)
        self.pressed = frozenset(pressed)


NEUTRAL = VirtualInput()


def read_joystick(js):
    held = set()
    if js.get_numhats():
        hx, hy = js.get_hat(0)
        if hx < 0:
            held.add("left")
        elif hx > 0:
            held.add("right")
        if hy > 0:
            held.add("up")
        elif hy < 0:
            held.add("down")
    if js.get_numaxes() >= 2:
        ax, ay = js.get_axis(0), js.get_axis(1)
        if ax < -DEADZONE:
            held.add("left")
        elif ax > DEADZONE:
            held.add("right")
        if ay < -DEADZONE:
            held.add("up")
        elif ay > DEADZONE:
            held.add("down")
    n = js.get_numbuttons()
    for button, action in PAD_BUTTONS.items():
        if button < n and js.get_button(button):
            held.add(action)
    return held


class PlayerInput:
    def __init__(self, keymap):
        self.keymap = keymap
        self.joystick = None
        self.held = frozenset()
        self.pressed = frozenset()
        self._prev = frozenset()
        self._taps = set()  # presses seen as events, so very short taps are never lost

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in self.keymap:
            self._taps.add(self.keymap[event.key])
        elif (event.type == pygame.JOYBUTTONDOWN and self.joystick is not None
              and event.instance_id == self.joystick.get_instance_id()
              and event.button in PAD_BUTTONS):
            self._taps.add(PAD_BUTTONS[event.button])

    def poll(self, keys):
        held = {action for key, action in self.keymap.items() if keys[key]}
        if self.joystick is not None:
            held |= read_joystick(self.joystick)
        pressed = (held - self._prev) | self._taps
        self._prev = frozenset(held)
        self.held = frozenset(held | self._taps)
        self.pressed = frozenset(pressed)
        self._taps = set()


class CombinedInput:
    """Union of several inputs - used for menus and single-player mode."""

    def __init__(self, sources):
        self.sources = sources
        self.held = frozenset()
        self.pressed = frozenset()

    def refresh(self):
        self.held = frozenset().union(*(s.held for s in self.sources))
        self.pressed = frozenset().union(*(s.pressed for s in self.sources))


class InputManager:
    def __init__(self):
        self.players = [PlayerInput(km) for km in KEYMAPS]
        self.any = CombinedInput(self.players)

    def handle_event(self, event):
        # SDL also sends JOYDEVICEADDED for pads already plugged in at startup.
        if event.type == pygame.JOYDEVICEADDED:
            js = pygame.joystick.Joystick(event.device_index)
            for p in self.players:
                if p.joystick is not None and p.joystick.get_instance_id() == js.get_instance_id():
                    return
            for p in self.players:
                if p.joystick is None:
                    p.joystick = js
                    return
        elif event.type == pygame.JOYDEVICEREMOVED:
            for p in self.players:
                if p.joystick is not None and p.joystick.get_instance_id() == event.instance_id:
                    p.joystick = None
        for p in self.players:
            p.handle_event(event)

    def update(self):
        keys = pygame.key.get_pressed()
        for p in self.players:
            p.poll(keys)
        self.any.refresh()

    def pad_names(self):
        return [p.joystick.get_name() if p.joystick else None for p in self.players]
