"""Guitar effects: hear your own playing through the speakers, with a little amp in the way.

The input callback hands every captured block to a ``Monitor``, which runs it through an effect chain
(drive, tone, chorus, echo, reverb - all vectorised numpy, block by block) and plays it on a second
stream. Off by default: it costs CPU on a Pi 3, and with a microphone instead of a direct guitar cable
the speakers would feed back, so use a direct cable or headphones.

    --fx crunch        start with an effect (off clean crunch lead chorus space)
    E                  cycle the effect while playing
"""
import collections
import os
import time
import math
import threading

import numpy as np

from .pitch import HOP, RATE

# Each preset: noise gate threshold (dBFS rms), pre-amp tone, two gain stages, speaker cabinet, then
# the time effects (mix 0..1) and the output level.
CAB_4X12 = [(40, -40), (70, -16), (90, 0), (115, 7), (160, 3), (250, -1), (400, -2), (700, 0), (1200, 1),
            (2000, 3), (3000, 4), (4000, 1), (5000, -8), (6500, -20), (8000, -32), (12000, -45), (20000, -60)]
CAB_1X12 = [(40, -40), (70, -14), (100, 2), (130, 5), (250, 2), (500, -1), (1000, 0), (2500, 3), (4000, 0),
            (6000, -10), (9000, -30), (14000, -45), (20000, -60)]
TIGHT = [(20, -40), (70, -14), (110, -4), (250, 0), (700, 3), (1500, 1), (6000, -2), (20000, -6)]      # tube-screamer-ish
MID_PUSH = [(20, -40), (70, -18), (140, -6), (400, 2), (800, 6), (1600, 3), (3500, 0), (8000, -4), (20000, -10)]

PRESETS = {
    "clean":  dict(gate=-62, pre=None, g1=0.0, g2=0.0, bias=0.0, cab=CAB_1X12, chorus=0.0, echo=0.0, reverb=0.16, level=1.0),
    "crunch": dict(gate=-50, pre=TIGHT, g1=4.0, g2=2.5, bias=0.12, cab=CAB_4X12, chorus=0.0, echo=0.0, reverb=0.10, level=0.7),
    "lead":   dict(gate=-45, pre=MID_PUSH, g1=9.0, g2=4.5, bias=0.25, cab=CAB_4X12, chorus=0.0, echo=0.22, reverb=0.20, level=0.45),
    "chorus": dict(gate=-62, pre=None, g1=0.0, g2=0.0, bias=0.0, cab=CAB_1X12, chorus=0.6, echo=0.0, reverb=0.15, level=1.0),
    "space":  dict(gate=-62, pre=None, g1=0.0, g2=0.0, bias=0.0, cab=CAB_1X12, chorus=0.25, echo=0.30, reverb=0.40, level=1.0),
}
NAMES = ["off"] + list(PRESETS)
COMB_DELAYS = (1557, 1617, 1491, 1422)       # samples at 44.1 kHz, all longer than one block
ECHO_DELAY = 0.28                            # seconds


def min_phase_fir(points, rate=RATE, taps=191, size=4096):
    """A short FIR with the given frequency response [(Hz, dB), ...] and no added delay (minimum phase)."""
    f = np.fft.rfftfreq(size, 1.0 / rate)
    xs, ys = zip(*points)
    mag_db = np.interp(np.log10(np.maximum(f, 1.0)), np.log10(xs), ys)
    cep = np.fft.irfft(np.log(10 ** (mag_db / 20.0)), size)                  # cepstrum of the log magnitude
    fold = np.zeros(size)
    fold[0], fold[size // 2] = cep[0], cep[size // 2]
    fold[1:size // 2] = 2.0 * cep[1:size // 2]                               # keep the causal half: minimum phase
    h = np.fft.irfft(np.exp(np.fft.rfft(fold)), size)[:taps]
    fade = int(taps * 0.3)
    h[-fade:] *= np.hanning(2 * fade)[fade:]
    return h


class Fir:
    """Block-by-block FIR filter that remembers its tail."""

    def __init__(self, h):
        self.h = np.asarray(h, dtype=np.float64)
        self.tail = np.zeros(len(self.h) - 1)

    def __call__(self, x):
        ext = np.concatenate((self.tail, x))
        self.tail = ext[len(x):]
        return np.convolve(ext, self.h, mode="valid")


def lowpass_fir(cutoff, rate, taps=31):
    n = np.arange(taps) - (taps - 1) / 2
    k = np.sinc(2 * cutoff / rate * n) * np.hanning(taps + 2)[1:-1]
    return k / k.sum()


class Gate:
    """Closes on hum and hiss between notes; opens fast, closes slowly so decays are not chopped."""

    def __init__(self, threshold_db, rate=RATE, sub=64):
        self.thr = 10 ** (threshold_db / 20.0)
        self.sub, self.gain, self.hold = sub, 1.0, 0
        self.rate = rate

    def __call__(self, x):
        n = len(x)
        k = n // self.sub
        rms = np.sqrt((x[:k * self.sub].reshape(k, self.sub) ** 2).mean(axis=1))
        g = np.empty(k)
        for i in range(k):
            if rms[i] > self.thr:
                self.hold = int(0.12 * self.rate / self.sub)
            target = 1.0 if self.hold > 0 else 0.0
            self.hold = max(0, self.hold - 1)
            self.gain += (target - self.gain) * (0.5 if target > self.gain else 0.06)
            g[i] = self.gain
        env = np.interp(np.arange(n), (np.arange(k) + 0.5) * self.sub, g) if k else np.ones(n)
        return x * env


class Chain:
    """One preset's processing state. ``process`` takes a block of mono floats, returns stereo floats."""

    def __init__(self, name, rate=RATE, block=HOP):
        p = PRESETS[name]
        self.name, self.rate, self.block = name, rate, block
        self.p = p
        self.gate = Gate(p["gate"], rate)
        self.pre = Fir(min_phase_fir(p["pre"], rate, 127)) if p["pre"] else None
        self.cab = Fir(min_phase_fir(p["cab"], rate, 191)) if p["cab"] else None
        self.inter = Fir(lowpass_fir(6500, 2 * rate, 21))        # between the two gain stages, at 2x rate
        self.down = Fir(lowpass_fir(0.44 * rate, 2 * rate, 31))  # keeps the distortion's top end from folding back
        self.prev = 0.0
        self.dc = 0.0
        self.reverb_in = Fir(lowpass_fir(4500, rate, 21))
        self.combs = [np.zeros(d) for d in COMB_DELAYS]
        self.echo = np.zeros(int(ECHO_DELAY * rate))
        self.chorus_hist = np.zeros(2048)
        self.phase = 0.0

    def _amp(self, x):
        """Two asymmetric soft-clipping stages at twice the sample rate (the clip makes harmonics that would alias)."""
        p, n = self.p, len(x)
        up = np.empty(2 * n)
        up[0::2] = 0.5 * (np.concatenate(([self.prev], x[:-1])) + x)     # midpoint between the previous and this sample
        up[1::2] = x
        self.prev = x[-1]
        bias = p["bias"]
        y = np.tanh(p["g1"] * up + bias) - math.tanh(bias)
        y = self.inter(y)
        y = np.tanh(p["g2"] * y - bias) + math.tanh(bias)
        self.dc = 0.995 * self.dc + 0.005 * float(y.mean())              # tube-style asymmetry leaves DC: remove it
        y = y - self.dc
        y = self.down(y)[::2]
        return y

    def process(self, x):
        x = np.asarray(x, dtype=np.float64)
        n = len(x)
        y = self.gate(x)
        if self.pre is not None:
            y = self.pre(y)
        if self.p["g1"] > 0:
            y = self._amp(y)
        if self.cab is not None:
            y = self.cab(y)
        y = y * self.p["level"]
        dry = y
        wet = np.zeros(n)
        mix = self.p["chorus"]
        if mix > 0:
            hist = np.concatenate((self.chorus_hist, dry))
            t = (np.arange(n) + self.phase) / self.rate
            delay = (0.011 + 0.004 * np.sin(2 * np.pi * 0.8 * t)) * self.rate          # 7-15 ms
            pos = len(self.chorus_hist) + np.arange(n) - delay
            wet = wet + mix * np.interp(pos, np.arange(len(hist)), hist)
            self.chorus_hist = hist[-len(self.chorus_hist):]
            self.phase += n
        out = dry * (1.0 - 0.3 * mix) + wet
        if self.p["echo"] > 0:
            e = self.echo[:n]
            new = out + 0.4 * e
            self.echo = np.concatenate((self.echo[n:], new))
            out = out + self.p["echo"] * e
        if self.p["reverb"] > 0:
            send = self.reverb_in(out)
            acc = np.zeros(n)
            for i, buf in enumerate(self.combs):
                new = send + 0.78 * buf[:n]
                self.combs[i] = np.concatenate((buf[n:], new))
                acc += new
            out = out + self.p["reverb"] * acc / len(self.combs)
        out = np.tanh(out * 1.1) * 0.9                                   # a soft ceiling instead of hard clipping
        return np.stack((out, out), axis=1).astype(np.float32)


class Monitor:
    """Plays the processed input. ``push`` is called from the input callback, the stream pulls."""

    def __init__(self, device=None, rate=RATE, block=HOP, log=print):
        self.device, self.rate, self.block, self.log = device, rate, block, log
        self.name = "off"
        self.chain = None
        self.stream = None
        self.buf = np.zeros((0, 2), np.float32)   # processed samples waiting for the output clock
        self.low, self.high = block * 2, block * 4  # input and output clocks drift: hold ~2-4 blocks, trim by samples
        self.primed = False
        self.drops = 0
        self.lock = threading.Lock()
        self.underruns = 0

    def set(self, name):
        """Switch effect; 'off' closes the output stream. Returns the name actually in use."""
        if name not in NAMES:
            name = "off"
        with self.lock:
            self.buf = self.buf[:0]
            self.primed = False
            self.name = name
            self.chain = Chain(name, self.rate, self.block) if name != "off" else None
        if name == "off":
            self._close()
        elif self.stream is None and not self._open():
            self.name, self.chain = "off", None
        return self.name

    def next(self):
        return self.set(NAMES[(NAMES.index(self.name) + 1) % len(NAMES)])

    def _open(self):
        try:
            import sounddevice as sd
            self.stream = sd.OutputStream(device=self.device, samplerate=self.rate, channels=2, blocksize=self.block,
                                          dtype="float32", latency="low", callback=self._pull)
            self.stream.start()
            return True
        except Exception as e:
            self.log("effects unavailable (%s)" % (str(e).strip().splitlines() or [type(e).__name__])[-1])
            self.stream = None
            return False

    def _close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def push(self, block):
        chain = self.chain
        if chain is not None:
            t0 = time.perf_counter()
            out = chain.process(block)
            self.cost = max(getattr(self, "cost", 0.0), time.perf_counter() - t0)
            self.pushes = getattr(self, "pushes", 0) + 1
            if os.environ.get("PI_FX_DEBUG") and self.pushes % 430 == 0:
                self.log("fx: underruns %d trims %d worst block %.1f ms of %.1f" % (
                    self.underruns, self.drops, self.cost * 1e3, self.block / self.rate * 1e3))
                self.cost = 0.0
            with self.lock:
                buf = np.concatenate((self.buf, out))
                if len(buf) > self.high:                  # output clock slower: skip a few samples, not a whole block
                    self.drops += 1
                    buf = buf[len(buf) - self.low:]
                self.buf = buf

    def _pull(self, outdata, frames, time_info, status):
        with self.lock:
            if not self.primed and len(self.buf) >= self.low:
                self.primed = True
            if self.primed and len(self.buf) >= frames:
                outdata[:] = self.buf[:frames]
                self.buf = self.buf[frames:]
                return
            if self.primed:                               # ran dry: refill to the cushion before playing again
                self.underruns += 1
                self.primed = False
        outdata.fill(0)

    def close(self):
        self._close()
