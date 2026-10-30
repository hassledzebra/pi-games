"""Real-time monophonic pitch tracking in plain numpy.

- ``yin`` is the YIN algorithm (de Cheveigne & Kawahara 2002) with the difference function
  computed by FFT, so a 2048-sample frame costs well under a millisecond on a Pi 4.
- ``PitchTracker`` turns a stream of audio blocks into per-hop frames of
  (time, frequency, confidence, level) plus pluck onsets.
- ``AudioInput`` reads the USB audio interface with sounddevice on a background thread.
  It is imported lazily so the rest of the game runs on machines without PortAudio.
"""
import math
import queue
import threading
import time

import numpy as np

RATE = 44100
FRAME = 2048          # analysis window: 46 ms, enough for low E (82 Hz) with margin
HOP = 512             # new pitch estimate every 11.6 ms
FMIN, FMAX = 70.0, 1400.0
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def freq_to_midi(freq):
    return 69.0 + 12.0 * math.log2(freq / 440.0)


def midi_to_freq(midi):
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def note_name(midi):
    m = int(round(midi))
    return "%s%d" % (NOTE_NAMES[m % 12], m // 12 - 1)


def yin(x, rate=RATE, fmin=FMIN, fmax=FMAX, threshold=0.15):
    """Fundamental frequency of one frame. Returns (freq_hz, confidence 0..1); freq is 0 when
    nothing periodic was found."""
    x = np.asarray(x, dtype=np.float64)
    w = len(x)
    n = w // 2
    tau_min = max(2, int(rate / fmax))
    tau_max = min(n, int(rate / fmin) + 1)
    if tau_max - tau_min < 3:
        return 0.0, 0.0
    a = x[:n]
    size = 1 << (2 * w - 1).bit_length()
    corr = np.fft.irfft(np.conj(np.fft.rfft(a, size)) * np.fft.rfft(x, size), size)[: n + 1]
    sq = np.concatenate(([0.0], np.cumsum(x * x)))
    lag = np.arange(n + 1)
    energy = sq[n + lag] - sq[lag]            # energy of x[tau : tau + n]
    d = sq[n] + energy - 2.0 * corr             # squared difference function
    d[0] = 0.0
    cum = np.cumsum(d[1:])
    cmndf = np.ones(n + 1)
    cmndf[1:] = d[1:] * lag[1:] / np.maximum(cum, 1e-12)
    seg = cmndf[tau_min:tau_max]
    below = np.flatnonzero(seg < threshold)
    if below.size:
        i = int(below[0])
        while i + 1 < len(seg) and seg[i + 1] < seg[i]:
            i += 1
    else:
        i = int(np.argmin(seg))
        if seg[i] > 0.5:
            return 0.0, float(max(0.0, 1.0 - seg[i]))
    tau = tau_min + i
    if 0 < tau < n:  # parabolic interpolation around the minimum
        s0, s1, s2 = cmndf[tau - 1], cmndf[tau], cmndf[tau + 1]
        denom = 2.0 * (s0 - 2.0 * s1 + s2)
        if abs(denom) > 1e-12:
            tau += (s0 - s2) / denom
    return rate / tau, float(max(0.0, min(1.0, 1.0 - cmndf[tau_min + i])))


class PitchFrame:
    __slots__ = ("time", "freq", "midi", "conf", "db", "onset")

    def __init__(self, t, freq, conf, db, onset):
        self.time = t
        self.freq = freq
        self.midi = freq_to_midi(freq) if freq > 0 else None
        self.conf = conf
        self.db = db
        self.onset = onset


class PitchTracker:
    """Feed audio blocks in, get PitchFrames out (one per HOP samples).

    An onset is a sudden rise in level (a pluck). The judge uses onsets and pitch changes to
    tell repeated notes apart, so one long E is not counted as four E's.
    """

    def __init__(self, rate=RATE, frame=FRAME, hop=HOP, gate_db=-50.0, conf_min=0.7,
                 onset_db=5.0, onset_gap=0.06):
        self.rate, self.frame, self.hop = rate, frame, hop
        self.gate_db, self.conf_min = gate_db, conf_min
        self.onset_db, self.onset_gap = onset_db, onset_gap
        self.buf = np.zeros(frame, dtype=np.float64)
        self.pending = np.zeros(0, dtype=np.float64)
        self.levels = []            # recent dB levels (one per hop) for onset detection
        self.last_onset = -1.0
        self.history = []           # last few midi values, for the smoothed display value
        self.current = None         # smoothed midi of the note being held, or None
        self.current_freq = 0.0
        self.frames_done = 0

    def feed(self, samples, t_end):
        """samples: float array ending at wall-clock time t_end. Returns new PitchFrames."""
        out = []
        self.pending = np.concatenate((self.pending, np.asarray(samples, dtype=np.float64)))
        n_hops = len(self.pending) // self.hop
        total = n_hops * self.hop
        for k in range(n_hops):
            block = self.pending[k * self.hop:(k + 1) * self.hop]
            self.buf = np.roll(self.buf, -self.hop)
            self.buf[-self.hop:] = block
            t = t_end - (total - (k + 1) * self.hop) / self.rate
            out.append(self._analyse(t))
        self.pending = self.pending[total:]
        return out

    def _analyse(self, t):
        rms = float(np.sqrt(np.mean(self.buf[-self.hop:] ** 2))) + 1e-9
        db = 20.0 * math.log10(rms)
        # a pluck: the level jumps over the last ~35 ms. A decaying string only loses a fraction
        # of a dB per hop, so a re-pluck of the same note still stands out.
        floor = min(self.levels[-3:]) if self.levels else -120.0
        self.levels.append(db)
        if len(self.levels) > 9:
            self.levels.pop(0)
        onset = db > self.gate_db and db - floor > self.onset_db and t - self.last_onset > self.onset_gap
        if onset:
            self.last_onset = t
        freq, conf = 0.0, 0.0
        if db > self.gate_db:
            freq, conf = yin(self.buf, self.rate)
            if conf < self.conf_min:
                freq = 0.0
        fr = PitchFrame(t, freq, conf, db, onset)
        self.history.append(fr.midi)
        if len(self.history) > 3:
            self.history.pop(0)
        valid = [m for m in self.history if m is not None]
        if len(valid) >= 2:
            self.current = float(np.median(valid))
            self.current_freq = midi_to_freq(self.current)
        else:
            self.current, self.current_freq = None, 0.0
        self.frames_done += 1
        return fr


class AudioInput:
    """Opens the capture device and queues blocks; call ``poll`` from the main loop."""

    def __init__(self, device=None, rate=RATE, blocksize=HOP, channel=0):
        import sounddevice as sd  # lazy: needs PortAudio
        self.rate = rate
        self.q = queue.Queue()
        self.channel = channel
        self.overflows = 0
        self.lock = threading.Lock()
        info = sd.query_devices(device, "input")
        channels = max(1, min(2, int(info["max_input_channels"])))
        self.name = info["name"]
        self.stream = sd.InputStream(device=device, samplerate=rate, channels=channels,
                                     blocksize=blocksize, dtype="float32", callback=self._cb)
        self.stream.start()

    def _cb(self, indata, frames, time_info, status):
        if status and status.input_overflow:
            self.overflows += 1
        self.q.put((indata[:, min(self.channel, indata.shape[1] - 1)].copy(), time.monotonic()))

    def poll(self):
        """All blocks captured since the last call, as (samples, t_end) pairs."""
        blocks = []
        while True:
            try:
                blocks.append(self.q.get_nowait())
            except queue.Empty:
                return blocks

    def close(self):
        self.stream.stop()
        self.stream.close()

    @staticmethod
    def list_devices():
        import sounddevice as sd
        lines = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                lines.append("%2d  %s  (%d in, %.0f Hz)" % (i, d["name"], d["max_input_channels"],
                                                           d["default_samplerate"]))
        return lines

    @staticmethod
    def pick_device():
        """Prefer a USB guitar interface over a laptop microphone."""
        import sounddevice as sd
        devs = sd.query_devices()
        for i, d in enumerate(devs):
            n = d["name"].lower()
            if d["max_input_channels"] > 0 and any(k in n for k in
                                                   ("umc", "um2", "u-phoria", "scarlett", "focusrite",
                                                    "usb audio", "rocksmith", "guitar", "codec")):
                return i
        return None
