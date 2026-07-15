#!/usr/bin/env python3
"""Synthesize the three badge SFX offline (matches the approved Web Audio recipes).

Writes 48kHz stereo 16-bit WAVs, padded to the clip length, sound onset at t=0:
  twitch.wav   recorder start  — mechanical clunk + motor whir + warm REC beep
  subscribe.wav bright two-tone "ding"
  discord.wav  short poppy blip
"""
import numpy as np, wave, struct, sys, os

SR = 48000
DUR = 4.0                      # match the 120-frame / 30fps clip
N = int(SR * DUR)

def _env(a, d, length):
    """linear attack to 1, exponential decay to ~0 over (a+d)."""
    e = np.zeros(length)
    na = max(1, int(a * SR)); nd = max(1, int(d * SR))
    na = min(na, length); e[:na] = np.linspace(0, 1, na)
    rest = min(nd, length - na)
    if rest > 0:
        e[na:na + rest] = np.exp(np.linspace(0, -6.5, rest))
    return e

def _osc(freq, n, kind):
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    if kind == 'sine':     return np.sin(ph)
    if kind == 'triangle': return 2 / np.pi * np.arcsin(np.sin(ph))
    if kind == 'square':   return np.sign(np.sin(ph))
    if kind == 'sawtooth': return 2 * (freq * tt - np.floor(0.5 + freq * tt))
    raise ValueError(kind)

def _place(buf, sig, when):
    s = int(when * SR)
    e = min(len(buf), s + len(sig))
    if e > s:
        buf[s:e] += sig[:e - s]

def tone(buf, freq, a, d, kind, peak, when=0.0):
    n = int((a + d) * SR)
    _place(buf, _osc(freq, n, kind) * _env(a, d, n) * peak, when)

def glide(buf, f0, f1, dur, kind, peak, when=0.0):
    n = int(dur * SR)
    fr = np.exp(np.linspace(np.log(f0), np.log(f1), n))       # exponential sweep
    ph = 2 * np.pi * np.cumsum(fr) / SR
    wav = np.sin(ph) if kind == 'sine' else 2 / np.pi * np.arcsin(np.sin(ph))
    _place(buf, wav * _env(0.008, dur - 0.008, n) * peak, when)

def thump(buf, freq, dur, peak, when=0.0):
    n = int(dur * SR)
    fr = np.exp(np.linspace(np.log(freq * 1.7), np.log(freq * 0.7), n))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    _place(buf, np.sin(ph) * np.exp(np.linspace(0, -6.5, n)) * peak, when)

def whir(buf, dur, f0, f1, peak, when=0.0):
    n = int(dur * SR)
    ramp = int(n * 0.7)
    fr = np.concatenate([np.linspace(f0, f1, ramp), np.full(n - ramp, f1)])
    ph = 2 * np.pi * np.cumsum(fr) / SR
    saw = 2 * (ph / (2 * np.pi) - np.floor(0.5 + ph / (2 * np.pi)))
    # gentle one-pole lowpass for a warm motor (no harsh high end)
    a = np.exp(-2 * np.pi * 470 / SR)
    lp = np.zeros(n)
    for i in range(1, n):
        lp[i] = (1 - a) * saw[i] + a * lp[i - 1]
    env = np.ones(n)
    at = int(0.06 * SR); env[:at] = np.linspace(0, 1, at)
    dc = n - ramp; env[ramp:] = np.exp(np.linspace(0, -6.5, dc))
    _place(buf, lp * env * peak, when)

def noise(buf, dur, peak, hp, when=0.0):
    n = int(dur * SR)
    x = np.random.uniform(-1, 1, n)
    a = np.exp(-2 * np.pi * hp / SR)              # one-pole highpass
    lp = np.zeros(n)
    for i in range(1, n):
        lp[i] = (1 - a) * x[i] + a * lp[i - 1]
    hpsig = x - lp
    _place(buf, hpsig * np.exp(np.linspace(0, -6.5, n)) * peak, when)

def twitch(buf):
    thump(buf, 120, 0.18, 0.55)
    noise(buf, 0.045, 0.09, 240)
    whir(buf, 0.5, 52, 122, 0.10, when=0.02)
    tone(buf, 784, 0.008, 0.17, 'triangle', 0.30, when=0.17)
    tone(buf, 392, 0.008, 0.17, 'sine', 0.15, when=0.17)

def subscribe(buf):
    tone(buf, 1568, 0.004, 0.28, 'sine', 0.5)
    tone(buf, 3136, 0.004, 0.22, 'sine', 0.18)
    tone(buf, 2093, 0.004, 0.5, 'sine', 0.5, when=0.12)
    tone(buf, 4186, 0.004, 0.4, 'sine', 0.16, when=0.12)

def discord(buf):
    glide(buf, 520, 1050, 0.085, 'triangle', 0.32)
    tone(buf, 1500, 0.001, 0.045, 'sine', 0.10, when=0.02)
    noise(buf, 0.028, 0.05, 1600)

def write_wav(path, mono):
    peak = np.max(np.abs(mono)) or 1.0
    mono = mono / peak * 0.89                      # normalize, headroom
    stereo = np.repeat((mono * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(path, 'w') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(stereo.tobytes())
    print(f"  wrote {os.path.basename(path)}  ({len(mono)/SR:.2f}s)")

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    np.random.seed(7)
    for name, fn in (('twitch', twitch), ('subscribe', subscribe), ('discord', discord)):
        buf = np.zeros(N)
        fn(buf)
        write_wav(os.path.join(out, f'{name}.wav'), buf)
    print("done.")
