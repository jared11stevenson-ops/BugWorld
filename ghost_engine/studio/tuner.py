"""Difficulty tuning by evolutionary search over headless Godot simulations of the arcade game (skilled + novice bots).
Fitness targets (design assumptions, stated): skilled bot clears the whole game 55-85% of the time, novice <=10%, skilled clears stage 1 >=90%."""
import json, os, random, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")
BOUNDS = {"law_strength": (0.4, 2.0, 0.1), "spawn_every": (8, 26, 1), "spawn_step": (1, 4, 1), "hazard_speed": (90.0, 230.0, 10.0),
          "goal": (3, 6, 1), "stage_secs": (24.0, 45.0, 3.0), "max_hazards": (10, 30, 2)}


def fitness(r):
    sk, nov, s1 = r["skilled"], r["novice"], r["skilled_stage1"]
    a = max(0.0, 1 - abs(sk - 0.70) / 0.70) if not (0.55 <= sk <= 0.85) else 1.0
    b = 1.0 if nov <= 0.10 else max(0.0, 1 - (nov - 0.10) / 0.5)
    c = min(1.0, s1 / 0.9)
    g = min(1.0, max(0.0, (sk - nov) / 0.4))          # skill must matter: skilled bot clearly beats the novice
    return 0.4 * a + 0.2 * b + 0.2 * c + 0.2 * g


def run_batch(project, sets, workers=4):
    chunks = [sets[i::workers] for i in range(workers)]
    def one(chunk):
        if not chunk:
            return []
        with tempfile.TemporaryDirectory() as d:
            ip, op = os.path.join(d, "in.json"), os.path.join(d, "out.json")
            json.dump(chunk, open(ip, "w"))
            r = subprocess.run([GODOT, "--headless", "--path", project, "--script", "res://ghost/tune.gd", "--", ip, op], capture_output=True, text=True, timeout=900)
            if not os.path.exists(op):
                raise RuntimeError("tuner failed: " + r.stdout[-800:] + r.stderr[-800:])
            return json.load(open(op))
    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(one, chunks))
    out = [None] * len(sets)
    for w in range(workers):
        for k, res in enumerate(parts[w]):
            out[w + k * workers] = res
    return out


def mutate(p, rnd, rate=0.4):
    p = dict(p)
    for k, (lo, hi, st) in BOUNDS.items():
        if rnd.random() < rate:
            v = p[k] + st * rnd.choice((-2, -1, 1, 2))
            p[k] = max(lo, min(hi, round(v, 3) if isinstance(st, float) else int(v)))
    return p


def tune(project, law, seed, pop=16, gens=8, init=None, log=print):
    """Winner's-curse-safe: every generation uses fresh evaluation seeds, elites are re-evaluated, ranking uses the running mean."""
    rnd = random.Random(seed)
    base = {"law": law, "law_strength": 1.0, "spawn_every": 14, "spawn_step": 3, "hazard_speed": 150.0, "goal": 4, "stage_secs": 32.0, "max_hazards": 22}
    popn = [base] + ([dict(init, law=law)] if init and init.get("law") == law else []) + [mutate(base, rnd, 0.8) for _ in range(pop)]
    popn = popn[:pop]
    hist, curve = {}, []
    key = lambda p: json.dumps(p, sort_keys=True)
    def mean_fit(p):
        rs = hist[key(p)]
        return sum(fitness(r) for r in rs) / len(rs)
    def mean_res(p):
        rs = hist[key(p)]
        return {k: sum(r[k] for r in rs) / len(rs) for k in rs[0]}
    ranked = popn
    for g in range(gens + 1):
        res = run_batch(project, [{"p": p, "seed_base": 1000 + 100 * g} for p in popn])
        for p, r in zip(popn, res):
            hist.setdefault(key(p), []).append(r)
        ranked = sorted(popn, key=lambda p: -mean_fit(p))
        b = mean_res(ranked[0])
        curve.append({"gen": g, "best_fitness": mean_fit(ranked[0]), "skilled": b["skilled"], "novice": b["novice"], "evals_of_best": len(hist[key(ranked[0])])})
        log(f"  tune gen {g}: fitness {mean_fit(ranked[0]):.3f} skilled {b['skilled']:.2f} novice {b['novice']:.2f} stage1 {b['skilled_stage1']:.2f} (n={len(hist[key(ranked[0])])})")
        if g == gens:
            break
        elite = ranked[:4]
        popn = list(elite)
        while len(popn) < pop:
            a, b2 = rnd.sample(elite, 2)
            c = {k: (a[k] if rnd.random() < .5 else b2[k]) for k in a}
            popn.append(mutate(c, rnd))
    best = ranked[0]
    held = run_batch(project, [{"p": best, "seed_base": 7000}, {"p": base, "seed_base": 7000}])
    return {"params": best, "curve": curve, "default_params": base, "holdout_best": held[0], "holdout_default": held[1],
            "start_fitness": curve[0]["best_fitness"], "final_fitness": curve[-1]["best_fitness"], "evaluations": sum(len(v) for v in hist.values())}
