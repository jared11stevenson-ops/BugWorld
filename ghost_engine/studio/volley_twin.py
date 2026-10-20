"""Python port of templates/volley_core.gd (floats limited to + - * / sqrt so results match Godot bit for bit)."""
import math
from ghost.kernel import rng as R

W, GROUND, NET_X, NET_HALF, NET_TOP, PR, BR = 1000.0, 440.0, 500.0, 5.0, 300.0, 38.0, 16.0
LEVELS = {0: [22, 100.0, 0.35], 1: [11, 40.0, 0.65], 2: [3, 6.0, 0.95]}
DEFAULTS = {"wind": 0.0, "slick": 0, "gravity": 0.42, "jump": 10.5, "restitution": 1.0, "points": 7, "ai_lag": 11, "ai_err": 40.0, "ai_aggr": 0.65,
            "serve_pause": 40, "max_ticks": 14400, "move_acc": 1.5}


def new_match(seed, p):
    s = {"rng": R.seed_state(seed), "p": p, "t": 0, "bx": 250.0, "by": 200.0, "bvx": 0.0, "bvy": 0.0, "px": [250.0, 750.0], "py": [GROUND, GROUND],
         "pvx": [0.0, 0.0], "pvy": [0.0, 0.0], "score": [0, 0], "server": ((seed & 0x7FFFFFFF) * 2654435761 // 7) % 2, "touches": 0, "last_side": -1,
         "pause": int(p["serve_pause"]), "rally": 0, "rallies": 0, "rally_hits": 0, "over": 0, "winner": -1, "hist": []}
    _serve(s)
    return s


def _serve(s):
    off = float(R.rand(s, 60)) - 30.0
    s["bx"] = (250.0 if s["server"] == 0 else 750.0) + off
    s["by"] = 180.0; s["bvx"] = 0.0; s["bvy"] = 0.0
    s["px"] = [250.0, 750.0]; s["py"] = [GROUND, GROUND]; s["pvx"] = [0.0, 0.0]; s["pvy"] = [0.0, 0.0]
    s["touches"] = 0; s["last_side"] = -1; s["rally"] = 0; s["pause"] = int(s["p"]["serve_pause"])


def _point(s, side):
    s["score"][side] += 1; s["rallies"] += 1; s["rally_hits"] += s["rally"]; s["server"] = side
    if s["score"][side] >= int(s["p"]["points"]):
        s["over"] = 1; s["winner"] = side
        return
    _serve(s)


def _tri(t):
    ph = t % 240
    return (float(ph) if ph < 120 else float(240 - ph)) / 60.0 - 1.0


def step(s, in0, in1):
    if s["over"]:
        return
    p = s["p"]
    s["t"] += 1
    g = float(p["gravity"])
    ins = [in0, in1]
    for i in range(2):
        acc = float(p["move_acc"]) * (0.25 if int(p["slick"]) != 0 else 1.0)
        fr = 0.95 if int(p["slick"]) != 0 else 0.8
        s["pvx"][i] = (s["pvx"][i] + float(ins[i][0]) * acc) * fr
        s["px"][i] += s["pvx"][i]
        lo = PR if i == 0 else NET_X + NET_HALF + PR
        hi = NET_X - NET_HALF - PR if i == 0 else W - PR
        if s["px"][i] < lo:
            s["px"][i] = lo; s["pvx"][i] = 0.0
        if s["px"][i] > hi:
            s["px"][i] = hi; s["pvx"][i] = 0.0
        if ins[i][1] and s["py"][i] >= GROUND:
            s["pvy"][i] = -float(p["jump"])
        s["pvy"][i] += g
        s["py"][i] += s["pvy"][i]
        if s["py"][i] >= GROUND:
            s["py"][i] = GROUND; s["pvy"][i] = 0.0
    s["hist"].append([s["bx"], s["by"], s["bvx"], s["bvy"]])
    if len(s["hist"]) > 40:
        s["hist"].pop(0)
    if s["pause"] > 0:
        s["pause"] -= 1
        return
    s["bvx"] += float(p["wind"]) * _tri(s["t"])
    s["bvy"] += g * 0.8
    for _sub in range(2):
        s["bx"] += s["bvx"] / 2.0
        s["by"] += s["bvy"] / 2.0
        if s["bx"] < BR:
            s["bx"] = BR; s["bvx"] = abs(s["bvx"])
        if s["bx"] > W - BR:
            s["bx"] = W - BR; s["bvx"] = -abs(s["bvx"])
        if s["by"] < BR:
            s["by"] = BR; s["bvy"] = abs(s["bvy"]) * 0.8
        if abs(s["bx"] - NET_X) < NET_HALF + BR and s["by"] > NET_TOP - BR:
            if s["by"] < NET_TOP and s["bvy"] > 0.0:
                s["by"] = NET_TOP - BR; s["bvy"] = -abs(s["bvy"]) * 0.7
            else:
                left = s["bx"] < NET_X
                s["bx"] = NET_X - NET_HALF - BR if left else NET_X + NET_HALF + BR
                s["bvx"] = -abs(s["bvx"]) * 0.7 if left else abs(s["bvx"]) * 0.7
        for i in range(2):
            dx = s["bx"] - s["px"][i]
            dy = s["by"] - s["py"][i]
            r = PR + BR
            d2 = dx * dx + dy * dy
            if d2 < r * r and dy < 10.0:
                d = math.sqrt(d2)
                nx, ny = 0.0, -1.0
                if d > 0.001:
                    nx = dx / d; ny = dy / d
                s["bx"] = s["px"][i] + nx * r
                s["by"] = s["py"][i] + ny * r
                rvx = s["bvx"] - s["pvx"][i]
                rvy = s["bvy"] - s["pvy"][i]
                vn = rvx * nx + rvy * ny
                if vn < 0.0:
                    e = 1.0 + float(p["restitution"])
                    s["bvx"] -= e * vn * nx
                    s["bvy"] -= e * vn * ny
                s["bvx"] += s["pvx"][i] * 0.3
                s["bvy"] += s["pvy"][i] * 0.3
                sp = math.sqrt(s["bvx"] * s["bvx"] + s["bvy"] * s["bvy"])
                if sp > 15.0:
                    s["bvx"] *= 15.0 / sp; s["bvy"] *= 15.0 / sp
                if sp < 5.0 and sp > 0.001:
                    s["bvx"] *= 5.0 / sp; s["bvy"] *= 5.0 / sp
                if s["last_side"] != i:
                    s["touches"] = 0; s["last_side"] = i
                s["touches"] += 1
                s["rally"] += 1
                if s["touches"] > 3:
                    _point(s, 1 - i)
                    return
        if s["by"] >= GROUND - BR:
            _point(s, 1 if s["bx"] < NET_X else 0)
            return
    if s["t"] >= int(p["max_ticks"]):
        s["over"] = 1
        s["winner"] = 0 if s["score"][0] > s["score"][1] else (1 if s["score"][1] > s["score"][0] else -1)


def _noise(s, side):
    return float((s["t"] // 8 * 7919 + side * 131 + 17) % 200) / 100.0 - 1.0


def ai_input(s, side, a):
    h = s["hist"]
    if not h:
        return [0, False]
    obs = h[max(0, len(h) - 1 - int(a[0]))]
    g = float(s["p"]["gravity"]) * 0.8
    lo = PR if side == 0 else NET_X + NET_HALF + PR
    hi = NET_X - NET_HALF - PR if side == 0 else W - PR
    home = 250.0 if side == 0 else 750.0
    on_my_side = (obs[0] < NET_X) == (side == 0)
    target = home
    yh = GROUND - 70.0
    if on_my_side or (abs(float(obs[0]) - NET_X) < 140.0 and (((obs[2] > 0.0) == (side == 1)) or True) and ((obs[2] < 0.0) == (side == 1))):
        disc = float(obs[3]) * float(obs[3]) + 2.0 * g * (yh - float(obs[1]))
        tl = 0.0
        if disc > 0.0:
            tl = (-float(obs[3]) + math.sqrt(disc)) / g
        if tl < 0.0:
            tl = 0.0
        xl = float(obs[0]) + float(obs[2]) * tl
        if xl < 0.0:
            xl = -xl
        if xl > W:
            xl = 2.0 * W - xl
        behind = 26.0 + 10.0 * float(s["touches"] if s["last_side"] == side else 0)
        target = xl + (-behind if side == 0 else behind) + float(a[1]) * _noise(s, side)
    target = max(lo, min(hi, target))
    d = 0
    dx = target - float(s["px"][side])
    if dx > 8.0:
        d = 1
    elif dx < -8.0:
        d = -1
    jump = False
    bdx = float(s["bx"]) - float(s["px"][side])
    bdy = float(s["by"]) - float(s["py"][side])
    if on_my_side and abs(bdx) < 70.0 and bdy < -40.0 and bdy > -190.0 and s["bvy"] > -2.0:
        jump = float((s["t"] * 2654435761 + side * 97) % 100) < float(a[2]) * 100.0
    return [d, jump]


def play(seed, p, left_level, right):
    s = new_match(seed, p)
    while not s["over"]:
        step(s, ai_input(s, 0, LEVELS[left_level]), ai_input(s, 1, right))
    return s


def digest(s):
    parts = [s["t"], s["score"][0], s["score"][1], s["touches"], s["rally"], s["rallies"], s["rally_hits"], s["over"], s["winner"], s["server"], s["rng"],
             int(s["bx"] * 1000.0), int(s["by"] * 1000.0), int(s["bvx"] * 1000.0), int(s["bvy"] * 1000.0),
             int(s["px"][0] * 1000.0), int(s["px"][1] * 1000.0), int(s["py"][0] * 1000.0), int(s["py"][1] * 1000.0)]
    return "%08x" % R.fnv32_str(",".join(str(int(x)) for x in parts))
