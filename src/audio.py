#!/usr/bin/env python3
"""sinereel - builds the reel's soundtrack from the same config the picture uses.

No samples, no loops, no licensing: every sound here is a few sine waves and an
envelope. Because the scene list drives it, re-timing a scene re-times the music.

Usage: python3 src/audio.py [config.json] [-o build/music.wav]
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000

args = [a for a in sys.argv[1:] if not a.startswith("-")]
config_path = Path(args[0] if args else "reel.config.json")
out_path = Path(sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "build/music.wav")

cfg = json.loads(config_path.read_text())
music = cfg.get("music", {})
scenes = cfg["scenes"]
BEAT = 60.0 / music.get("bpm", 120)
ROOT = music.get("root", 41.2)          # drone fundamental, Hz (E1 by default)

# Scene boundaries, in seconds. Everything below is expressed against these,
# which is what keeps the music glued to the cut.
starts, clock = [], 0.0
for s in scenes:
    starts.append(clock)
    clock += s["dur"]
DUR = clock
n = int(SR * DUR)
mix = np.zeros(n)


def add(sig, at):
    i = int(at * SR)
    if i >= n:
        return
    j = min(n, i + len(sig))
    mix[i:j] += sig[: j - i]


def kick(amp=1.0):
    x = np.arange(int(0.42 * SR)) / SR
    f = 118 * np.exp(-x / 0.035) + 44                      # pitch drop
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / 0.16)
    click = np.random.RandomState(1).randn(len(x)) * np.exp(-x / 0.004) * 0.25
    return (body + click) * amp


def hat(amp=0.16, ln=0.045):
    x = np.arange(int(ln * SR)) / SR
    nz = np.random.RandomState(int(ln * 10000)).randn(len(x))
    nz = np.diff(np.concatenate([[0], nz]))                 # crude high-pass
    return nz * np.exp(-x / 0.012) * amp


def tone(freq, ln, amp, decay=0.5, harm=(1, 0.35, 0.12)):
    x = np.arange(int(ln * SR)) / SR
    s = sum(h * np.sin(2 * np.pi * freq * (i + 1) * x) for i, h in enumerate(harm))
    return s * np.exp(-x / decay) * amp


def blip(freq, ln=0.18, amp=0.22):
    x = np.arange(int(ln * SR)) / SR
    return np.sin(2 * np.pi * freq * x) * np.exp(-x / 0.05) * amp


def mood_at(t):
    for start, s in zip(starts, scenes):
        if start <= t < start + s["dur"]:
            return s.get("mood", "build")
    return scenes[-1].get("mood", "build")


if music.get("enabled", True):
    t = np.arange(n) / SR

    # Continuous drone, fading up over the first three seconds.
    drone = (np.sin(2 * np.pi * ROOT * t) * 0.50
             + np.sin(2 * np.pi * ROOT * 2 * t) * 0.22
             + np.sin(2 * np.pi * ROOT * 3 * t) * 0.07)
    mix += drone * (np.clip(t / 3.0, 0, 1) * 0.20 + 0.06)

    # Kick and hats follow the mood of whichever scene the beat lands in.
    KICK_AMP = {"intro": 0.0, "build": 0.85, "tension": 0.0, "payoff": 1.0}
    beat = 0.0
    while beat < DUR:
        amp = KICK_AMP.get(mood_at(beat), 0.85)
        if amp:
            add(kick(amp), beat)
        if mood_at(beat) not in ("intro", "tension"):
            add(hat(0.15), beat + BEAT / 2)
        beat += BEAT

    # Ostinato under every build and payoff scene.
    notes = [ROOT * 2, ROOT * 2 * 1.189, ROOT * 2 * 1.335, ROOT * 2]   # i - III - IV - i
    i = 0
    beat = 0.0
    while beat < DUR:
        if mood_at(beat) in ("build", "payoff"):
            add(tone(notes[i % 4], 0.46, 0.17, decay=0.22), beat)
            i += 1
        beat += BEAT

    # One blip on every cut, and a low impact where a tension scene resolves.
    for idx, (start, s) in enumerate(zip(starts, scenes)):
        add(blip(1320 if idx == 0 else 920), start)
        if s.get("mood") == "tension":
            hit = start + s["dur"] * 0.55
            add(tone(ROOT * 1.4, 1.6, 0.55, decay=0.5, harm=(1, 0.2)), hit)
            add(blip(220, 0.4, 0.30), hit)

    for delay, g in [(0.09, 0.16), (0.17, 0.09)]:           # two short echoes
        sh = int(delay * SR)
        mix[sh:] += mix[:-sh] * g

    fade_in = int(0.12 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)
    fade_out = int(0.9 * SR)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)
    mix = np.tanh(mix * 1.1) * 0.82                          # soft limiter

pcm = (mix * 32767).astype(np.int16)
stereo = np.repeat(pcm[:, None], 2, axis=1).flatten()
out_path.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(out_path), "w") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(stereo.tobytes())
print(f"  {out_path} — {DUR:.1f}s, {len(scenes)} scenes at {music.get('bpm', 120)} bpm")
