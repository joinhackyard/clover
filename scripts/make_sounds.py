#!/usr/bin/env python3
"""Clover's sound pack, synthesized from scratch so every sample is Hackyard's own. Run: python3 scripts/make_sounds.py

Pip    start listening   a tiny rising droplet
Hop    request sent      a soft bounce
Bloom  answer ready      three sparkly notes, like a clover opening
Hush   stopped           a gentle falling sigh
Chirp  wake word heard   a little bird saying "yes?"
"""
import math
import os
import struct
import wave

RATE = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ui', 'sounds')


def env(t, length, attack=0.006, curve=5.0):
    """Quick attack, exponential tail: a struck, bell-like shape."""
    if t < attack: return t / attack
    return math.exp(-curve * (t - attack) / max(1e-6, length - attack))


def tone(freq, length, gain=1.0, glide=None, attack=0.006, curve=5.0, sparkle=0.0, delay=0.0):
    """One voice: sine + a hint of the 2nd/3rd harmonic, an optional pitch glide, optional shimmer."""
    out, phase = [], 0.0
    n = int((length + delay) * RATE)
    for i in range(n):
        t = i / RATE - delay
        if t < 0: out.append(0.0); continue
        f = freq if glide is None else freq * (glide / freq) ** min(1.0, t / length)
        phase += 2 * math.pi * f / RATE
        wave_ = math.sin(phase) + 0.18 * math.sin(2 * phase) + 0.06 * math.sin(3 * phase)
        if sparkle: wave_ += sparkle * math.sin(4.01 * phase) * math.exp(-12 * t)
        out.append(gain * wave_ * env(t, length, attack, curve))
    return out


def mix(*voices):
    n = max(len(v) for v in voices)
    return [sum(v[i] for v in voices if i < len(v)) for i in range(n)]


def save(name, samples, peak=0.42):
    top = max(abs(s) for s in samples) or 1
    fade = int(0.004 * RATE)   # no click at the end
    data = [s / top * peak * (min(1, (len(samples) - i) / fade)) for i, s in enumerate(samples)]
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name + '.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, s)) * 32767)) for s in data))


def chirp_voice(start, end, length, delay):
    out, phase = [], 0.0
    for i in range(int((length + delay) * RATE)):
        t = i / RATE - delay
        if t < 0: out.append(0.0); continue
        x = t / length
        f = start + (end - start) * math.sin(x * math.pi / 2) + 90 * math.sin(2 * math.pi * 38 * t)   # a little warble
        phase += 2 * math.pi * f / RATE
        out.append(math.sin(phase) * math.sin(math.pi * min(1, x)) ** 0.7)
    return out


def main():
    save('Pip', tone(1046.5, 0.11, glide=1568.0, curve=4.0, sparkle=0.25))
    save('Hop', mix(tone(784.0, 0.09, glide=622.3, curve=3.5), tone(1174.7, 0.12, gain=0.8, glide=1318.5, delay=0.055, curve=4.5)))
    save('Bloom', mix(tone(783.99, 0.32, gain=0.7, sparkle=0.35),
                      tone(1046.5, 0.34, gain=0.7, delay=0.075, sparkle=0.35),
                      tone(1318.5, 0.42, gain=0.75, delay=0.15, sparkle=0.45),
                      tone(2637.0, 0.30, gain=0.12, delay=0.15, curve=7)))
    save('Hush', mix(tone(659.25, 0.12, gain=0.8, curve=3), tone(523.25, 0.2, gain=0.7, glide=493.9, delay=0.08, curve=3.5)), peak=0.32)
    save('Chirp', mix(chirp_voice(1900, 3100, 0.07, 0.0), chirp_voice(2100, 3500, 0.085, 0.095)), peak=0.3)


if __name__ == '__main__':
    main()
