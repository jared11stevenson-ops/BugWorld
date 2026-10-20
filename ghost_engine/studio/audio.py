"""Procedural audio (stdlib only): deterministic SFX + a looping music track per game, seeded by the universe. 22.05 kHz mono 16-bit WAV."""
import math, os, random, struct, wave

SR = 22050


def _write(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples))


def tone(freq, dur, vol=0.5, shape="sine", decay=3.0):
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        ph = 2 * math.pi * freq * t
        v = math.sin(ph) if shape == "sine" else (1 if math.sin(ph) > 0 else -1) * 0.6 if shape == "square" else math.sin(ph) + 0.4 * math.sin(2 * ph) + 0.2 * math.sin(3 * ph)
        env = min(1.0, i / (SR * 0.005)) * math.exp(-decay * t / max(dur, 1e-3))
        out.append(v * vol * env)
    return out


def mix(a, b, offset=0):
    n = max(len(a), offset + len(b))
    out = list(a) + [0.0] * (n - len(a))
    for i, v in enumerate(b):
        out[offset + i] += v
    return out


def noise(dur, vol, rnd, decay=8.0):
    n = int(SR * dur)
    return [(rnd.random() * 2 - 1) * vol * math.exp(-decay * i / n) for i in range(n)]


def sfx(outdir, seed):
    rnd = random.Random(seed)
    base = 440 * 2 ** (rnd.choice([0, 2, 3, 5, 7]) / 12)
    files = {}
    def put(name, samples):
        p = os.path.join(outdir, f"{name}.wav"); _write(p, samples); files[name] = p
    put("click", tone(base * 2, 0.06, 0.4, "sine", 5))
    put("hit", mix(noise(0.18, 0.5, rnd), tone(base / 4, 0.18, 0.5, "square", 6)))
    put("pickup", mix(tone(base * 2, 0.08, 0.4), tone(base * 3, 0.12, 0.4), int(SR * 0.07)))
    put("win", mix(mix(mix(tone(base, 0.15, 0.4, "tri"), tone(base * 1.25, 0.15, 0.4, "tri"), int(SR * 0.12)),
                       tone(base * 1.5, 0.15, 0.4, "tri"), int(SR * 0.24)), tone(base * 2, 0.4, 0.4, "tri"), int(SR * 0.36)))
    put("lose", mix(mix(tone(base, 0.2, 0.4, "square", 4), tone(base * 0.8, 0.2, 0.4, "square", 4), int(SR * 0.18)), tone(base * 0.6, 0.45, 0.4, "square", 4), int(SR * 0.36)))
    put("pulse", tone(base / 2, 0.35, 0.5, "sine", 3))
    return files


def music(path, seed, bpm=96, bars=8):
    rnd = random.Random(seed)
    root = 110 * 2 ** (rnd.randrange(12) / 12)
    scale = [0, 3, 5, 7, 10] if rnd.random() < 0.5 else [0, 2, 4, 7, 9]
    beat = 60 / bpm
    total = int(SR * beat * 4 * bars)
    buf = [0.0] * total
    prog = [rnd.choice(scale) for _ in range(4)]
    for bar in range(bars):
        r = root * 2 ** (prog[bar % 4] / 12)
        for b in range(4):
            off = int(SR * beat * (bar * 4 + b))
            if b % 2 == 0:
                for i, v in enumerate(tone(r / 2, beat * 1.6, 0.28, "tri", 1.5)):
                    if off + i < total: buf[off + i] += v
            for h in range(2):
                note = r * 2 ** (rnd.choice(scale) / 12) * 2
                o2 = off + int(SR * beat * h / 2)
                for i, v in enumerate(tone(note, beat * 0.5, 0.16, "sine", 3)):
                    if o2 + i < total: buf[o2 + i] += v
    peak = max(abs(x) for x in buf) or 1
    _write(path, [x / peak * 0.7 for x in buf])
    return path
