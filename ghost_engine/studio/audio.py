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
    put("alarm", mix(tone(base * 1.5, 0.12, 0.35, "square", 2), tone(base * 1.2, 0.12, 0.35, "square", 2), int(SR * 0.14)))
    put("burn", mix(noise(0.5, 0.45, rnd, 3.0), noise(0.5, 0.25, rnd, 1.0), int(SR * 0.05)))
    put("cure", mix(mix(tone(base * 2, 0.12, 0.3, "sine", 3), tone(base * 2.5, 0.12, 0.3, "sine", 3), int(SR * 0.08)), tone(base * 3, 0.3, 0.3, "sine", 3), int(SR * 0.16)))
    put("infect", tone(base / 3, 0.4, 0.5, "square", 4) if False else [v * (0.6 + 0.4 * math.sin(i * 0.004)) for i, v in enumerate(tone(base / 3, 0.4, 0.45, "square", 4))])
    put("step", noise(0.05, 0.25, rnd, 25.0))
    put("ui_open", tone(base * 1.5, 0.1, 0.25, "sine", 6))
    return files


MOODS = {"calm": {"bpm": 92, "scale": [0, 2, 4, 7, 9], "pad": [0, 4, 7], "kick": [0], "tone": "tri"},
         "tense": {"bpm": 80, "scale": [0, 3, 5, 7, 10], "pad": [0, 3, 7], "kick": [0, 2], "tone": "tri"},
         "dread": {"bpm": 66, "scale": [0, 1, 5, 6, 10], "pad": [0, 1, 6], "kick": [0, 0.75], "tone": "sine"}}


def music(path, seed, bpm=None, bars=8, mood="calm"):
    """Layered loop: drone, pad chord, bass, heartbeat/kick, hats, sparse arpeggio. Mood changes scale, tempo and rhythm."""
    cfg = MOODS.get(mood, MOODS["calm"])
    bpm = bpm or cfg["bpm"]
    rnd = random.Random(seed)
    root = 55 * 2 ** (rnd.randrange(12) / 12)
    beat = 60 / bpm
    total = int(SR * beat * 4 * bars)
    buf = [0.0] * total
    def add(samples, off):
        for i, v in enumerate(samples):
            if 0 <= off + i < total:
                buf[off + i] += v
    add(tone(root, beat * 4 * bars, 0.10, "sine", 0.05), 0)                      # drone under everything
    prog = [rnd.choice(cfg["scale"]) for _ in range(4)]
    for bar in range(bars):
        r = root * 2 ** (prog[bar % 4] / 12)
        t0 = int(SR * beat * 4 * bar)
        for iv in cfg["pad"]:
            add(tone(r * 4 * 2 ** (iv / 12), beat * 4, 0.05, cfg["tone"], 0.6), t0)   # pad chord
        for b in range(4):
            off = int(SR * beat * (bar * 4 + b))
            if b % 2 == 0:
                add(tone(r * 2, beat * 1.4, 0.22, "tri", 2.0), off)                   # bass
            for kp in cfg["kick"]:
                if b == 0 or (mood != "calm" and b == 2):
                    add(tone(52, 0.22, 0.45, "sine", 9.0), off + int(SR * beat * kp * 0.5))   # kick / heartbeat
            add(noise(0.04, 0.05, rnd, 20.0), off + int(SR * beat * 0.5))               # hat
            if rnd.random() < 0.55:
                note = r * 4 * 2 ** (rnd.choice(cfg["scale"]) / 12)
                add(tone(note, beat * 0.45, 0.10, "sine", 4.0), off + int(SR * beat * rnd.choice((0.0, 0.5))))   # arpeggio
    peak = max(abs(x) for x in buf) or 1
    _write(path, [x / peak * 0.7 for x in buf])
    return path


def ambient(path, seed, mood="calm", seconds=12):
    """Slowly breathing noise bed + drone; loops."""
    rnd = random.Random(seed + 7)
    n = int(SR * seconds)
    f0 = 41 * 2 ** (rnd.randrange(7) / 12)
    out, lp = [], 0.0
    for i in range(n):
        t = i / SR
        lp += (rnd.random() * 2 - 1 - lp) * 0.04
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * t / seconds * (2 if mood == "dread" else 1))
        out.append(lp * 0.5 * breath + math.sin(2 * math.pi * f0 * t) * 0.15 + math.sin(2 * math.pi * f0 * 1.5 * t + breath) * 0.05)
    peak = max(abs(x) for x in out) or 1
    _write(path, [x / peak * 0.6 for x in out])
    return path
