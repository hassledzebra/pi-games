"""Make an AI jam track for a Pi Strum exercise with MusicGen and install it as the backing.

Run on a PC/Mac, not the Pi (needs PyTorch):
    python tools/jam_track.py "songs/path/4-3 E Minor Pentatonic.mid" --key "E minor" --style "blues rock"

The clip is generated at the exercise's tempo, trimmed so a beat lands at time zero, cut to whole
bars and looped to cover the song, then written next to the MIDI as its backing WAV (44.1 kHz
stereo). The arranged backing is kept as <name>.arranged.wav so it can be restored.
"""
import argparse
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from games.guitar.song import load_song  # noqa: E402

PROMPT = "{style} backing track at {bpm} bpm in {key}, steady drums, bass and rhythm guitar, no lead melody, no vocals, loopable"


def generate(prompt, seconds, model_name="facebook/musicgen-small", seed=None):
    import torch
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    if seed is not None:
        torch.manual_seed(seed)
    processor = AutoProcessor.from_pretrained(model_name)
    model = MusicgenForConditionalGeneration.from_pretrained(model_name)
    inputs = processor(text=[prompt], padding=True, return_tensors="pt")
    audio = model.generate(**inputs, do_sample=True, guidance_scale=3.0, max_new_tokens=int(seconds * 50))
    return audio[0, 0].numpy(), model.config.audio_encoder.sampling_rate


def to_grid(y, sr, bpm, beats_per_bar, length_seconds, out_sr=44100):
    """Trim to the first beat, keep whole bars, loop to cover length_seconds, resample."""
    import librosa
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    if beats.size < 2:
        raise SystemExit("no beats found in the generated clip")
    beat = 60.0 / bpm
    bar = beat * beats_per_bar
    # the first strong beat: the earliest detected beat with the biggest low-frequency onset
    onset = librosa.onset.onset_strength(y=y, sr=sr, fmax=200)
    frames = librosa.time_to_frames(beats[:beats_per_bar * 2], sr=sr)
    start = float(beats[int(np.argmax(onset[np.clip(frames, 0, len(onset) - 1)]))])
    usable = (len(y) / sr - start - 0.05)
    bars = int(usable // bar)
    if bars < 1:
        raise SystemExit("clip too short for one bar")
    seg = y[int(start * sr): int((start + bars * bar) * sr)]
    # loop with a short crossfade until it covers the song plus one bar of tail
    need = int((length_seconds + bar) * sr)
    fade = int(0.02 * sr)
    out = seg.copy()
    while len(out) < need:
        head, tail = seg[:fade] * np.linspace(0, 1, fade), out[-fade:] * np.linspace(1, 0, fade)
        out = np.concatenate((out[:-fade], head + tail, seg[fade:]))
    out = out[:need]
    out = librosa.resample(out, orig_sr=sr, target_sr=out_sr)
    out = out / max(1e-6, float(np.abs(out).max())) * 0.89
    return np.stack((out, out), axis=1).astype(np.float32), tempo, start, bars


def main():
    ap = argparse.ArgumentParser(description="AI jam track for an exercise")
    ap.add_argument("midi")
    ap.add_argument("--key", required=True, help='e.g. "E minor", "C major"')
    ap.add_argument("--style", default="upbeat acoustic pop")
    ap.add_argument("--seconds", type=float, default=24.0, help="clip length to generate (max 30)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--model", default="facebook/musicgen-small")
    args = ap.parse_args()

    from games.guitar.backing import write_wav
    song = load_song(args.midi)
    prompt = PROMPT.format(style=args.style, bpm=round(song.bpm), key=args.key)
    print("prompt:", prompt)
    t0 = time.time()
    y, sr = generate(prompt, min(30.0, args.seconds), args.model, args.seed)
    print("generated %.1f s in %.0f s" % (len(y) / sr, time.time() - t0))
    audio, tempo, start, bars = to_grid(y, sr, song.bpm, song.beats_per_bar, song.duration)
    print("detected tempo %.1f bpm (exercise %d), first downbeat at %.2f s, %d bars looped to %.1f s"
          % (tempo, round(song.bpm), start, bars, len(audio) / 44100))
    if abs(tempo - song.bpm) / song.bpm > 0.04 and abs(tempo * 2 - song.bpm) / song.bpm > 0.04 and abs(tempo / 2 - song.bpm) / song.bpm > 0.04:
        print("WARNING: tempo is off by more than 4%%; try another --seed")
    base = os.path.splitext(song.midi_path)[0]
    out = base + ".wav"
    if os.path.exists(out) and not os.path.exists(base + ".arranged.wav"):
        os.replace(out, base + ".arranged.wav")
    write_wav(out, audio, 44100)
    print("installed", out)


if __name__ == "__main__":
    main()
