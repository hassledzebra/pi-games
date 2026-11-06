"""Guitar effects: hear your own playing through the speakers, with a little amp in the way.

The input callback hands every captured block to a ``Monitor``, which runs it through an effect chain
(drive, tone, chorus, echo, reverb - all vectorised numpy, block by block) and plays it on a second
stream. Off by default: it costs CPU on a Pi 3, and with a microphone instead of a direct guitar cable
the speakers would feed back, so use a direct cable or headphones.

    --fx crunch        start with an effect (off clean crunch lead chorus space)
    E                  cycle the effect while playing
"""
import collections
import math
import threading

import numpy as np

from .pitch import HOP, RATE

PRESETS = {
    #            drive  tone Hz  chorus  echo  reverb   (mixes 0..1, drive is input gain)
    "clean":  dict(drive=0.0, tone=0, chorus=0.0, echo=0.0, reverb=0.18),
    "crunch": dict(drive=5.0, tone=4200, chorus=0.0, echo=0.0, reverb=0.12),
    "lead":   dict(drive=16.0, tone=3200, chorus=0.0, echo=0.22, reverb=0.22),
    "chorus": dict(drive=0.0, tone=0, chorus=0.55, echo=0.0, reverb=0.16),
    "space":  dict(drive=0.0, tone=0, chorus=0.25, echo=0.30, reverb=0.40),
}
NAMES = ["off"] + list(PRESETS)
COMB_DELAYS = (1557, 1617, 1491, 1422)       # samples at 44.1 kHz, all longer than one block
ECHO_DELAY = 0.28                            # seconds


class Chain:
    """One preset's processing state. ``process`` takes a block of mono floats, returns stereo floats."""

    def __init__(self, name, rate=RATE, block=HOP):
        p = PRESETS[name]
        self.name, self.rate, self.block = name, rate, block
        self.drive, self.chorus_mix, self.echo_mix, self.reverb_mix = p["drive"], p["chorus"], p["echo"], p["reverb"]
        self.kernel = self._lowpass(p["tone"]) if p["tone"] else None
        self.tail = np.zeros(len(self.kernel) - 1 if self.kernel is not None else 0)
        self.combs = [np.zeros(d) for d in COMB_DELAYS]
        self.echo = np.zeros(int(ECHO_DELAY * rate))
        self.chorus_hist = np.zeros(2048)
        self.phase = 0.0

    def _lowpass(self, cutoff, taps=15):
        n = np.arange(taps) - (taps - 1) / 2
        k = np.sinc(2 * cutoff / self.rate * n) * np.hanning(taps + 2)[1:-1]
        return k / k.sum()

    def process(self, x):
        x = np.asarray(x, dtype=np.float64)
        n = len(x)
        y = x.copy()
        if self.drive > 0:
            y = np.tanh(self.drive * y) / math.tanh(self.drive) * 0.4
            if self.kernel is not None:
                ext = np.concatenate((self.tail, y))
                y = np.convolve(ext, self.kernel, mode="valid")[:n]
                self.tail = ext[-(len(self.kernel) - 1):]
        dry = y
        wet = np.zeros(n)
        if self.chorus_mix > 0:
            hist = np.concatenate((self.chorus_hist, dry))
            t = (np.arange(n) + self.phase) / self.rate
            delay = (0.011 + 0.004 * np.sin(2 * np.pi * 0.8 * t)) * self.rate          # 7-15 ms
            pos = len(self.chorus_hist) + np.arange(n) - delay
            wet = wet + self.chorus_mix * np.interp(pos, np.arange(len(hist)), hist)
            self.chorus_hist = hist[-len(self.chorus_hist):]
            self.phase += n
        out = dry * (1.0 - 0.3 * self.chorus_mix) + wet
        if self.echo_mix > 0:
            e = self.echo[:n]
            new = out + 0.4 * e
            self.echo = np.concatenate((self.echo[n:], new))
            out = out + self.echo_mix * e
        if self.reverb_mix > 0:
            acc = np.zeros(n)
            for i, buf in enumerate(self.combs):
                new = out + 0.78 * buf[:n]
                self.combs[i] = np.concatenate((buf[n:], new))
                acc += new
            out = out + self.reverb_mix * acc / len(self.combs)
        out = np.clip(out, -0.98, 0.98)
        return np.stack((out, out), axis=1).astype(np.float32)


class Monitor:
    """Plays the processed input. ``push`` is called from the input callback, the stream pulls."""

    def __init__(self, device=None, rate=RATE, block=HOP, log=print):
        self.device, self.rate, self.block, self.log = device, rate, block, log
        self.name = "off"
        self.chain = None
        self.stream = None
        self.q = collections.deque(maxlen=2)      # at most ~23 ms waiting: older blocks are dropped, not played late
        self.lock = threading.Lock()
        self.underruns = 0

    def set(self, name):
        """Switch effect; 'off' closes the output stream. Returns the name actually in use."""
        if name not in NAMES:
            name = "off"
        with self.lock:
            self.q.clear()
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
            out = chain.process(block)
            with self.lock:
                self.q.append(out)

    def _pull(self, outdata, frames, time_info, status):
        with self.lock:
            block = self.q.popleft() if self.q else None
        if block is None or len(block) != frames:
            outdata.fill(0)
            if block is None:
                self.underruns += 1
        else:
            outdata[:] = block

    def close(self):
        self._close()
