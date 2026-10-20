"""Difficulty tuning by evolutionary search over headless Godot simulations of the arcade game (skilled + novice bots).
Fitness targets (design assumptions, stated): skilled bot clears the whole game 55-85% of the time, novice <=10%, skilled clears stage 1 >=90%."""
import json, os, random, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")
ARCADE_BOUNDS = {"law_strength": (0.4, 2.0, 0.1), "spawn_every": (8, 26, 1), "spawn_step": (1, 4, 1), "hazard_speed": (90.0, 230.0, 10.0),
                 "goal": (3, 6, 1), "stage_secs": (24.0, 45.0, 3.0), "max_hazards": (10, 30, 2)}
CORDON_BOUNDS = {"beta": (30, 110, 5), "flow": (2, 16, 1), "mort": (4, 30, 2), "rec": (5, 20, 1), "meds": (3, 16, 1), "win_pct": (40, 75, 5),
                 "q_days": (3, 6, 1), "seeds": (1, 4, 1), "ap": (2, 4, 1), "leak": (0, 60, 5), "jump": (0, 15, 1)}
VOLLEY_BOUNDS = {"gravity": (0.30, 0.60, 0.02), "jump": (9.0, 13.0, 0.5), "restitution": (0.85, 1.2, 0.05), "ai_lag": (2, 24, 1), "ai_err": (5.0, 100.0, 5.0), "ai_aggr": (0.2, 1.0, 0.05), "points": (5, 9, 1)}
SPLASH_BOUNDS = {"team_size": (1, 3, 1), "splash_r": (50.0, 80.0, 4.0), "splash_dmg": (30.0, 60.0, 5.0), "speed": (2.6, 3.8, 0.2), "en_lead": (0.0, 0.6, 0.1),
                 "en_err": (10.0, 90.0, 10.0), "en_aggr": (0.3, 1.0, 0.05), "en_dodge": (0.0, 1.0, 0.1), "ally_level": (0, 2, 1), "throw_cd": (20, 45, 5)}
def _ph_splash(law, ph):
    """Universe physics -> splash constants (falls back to the single-law mapping used before the element model)."""
    if ph is None:
        return {"slick": 1 if law == "slick" else 0, "wind": 0.04 if law == "gust" else 0.0}
    return {"slick": int(ph.get("slick", 0)), "wind": float(ph.get("wind", 0.0)) * 1.3}


def _ph_volley(law, ph):
    if ph is None:
        return {"wind": 0.03 if law == "gust" else 0.0, "slick": 1 if law == "slick" else 0, "gravity": 0.42, "restitution": 1.0}
    return {"wind": float(ph.get("wind", 0.0)), "slick": int(ph.get("slick", 0)), "gravity": round(0.42 * ph.get("gravity_scale", 1.0), 3),
            "restitution": round(1.0 * ph.get("restitution_scale", 1.0), 3), "burst_r": round(130.0 * ph.get("burst_radius", 1.0), 1)}


ARTILLERY_BOUNDS = {"hp": (60.0, 160.0, 10.0), "blast_r": (30.0, 70.0, 4.0), "blast_dmg": (35.0, 90.0, 5.0), "ai_err": (0.5, 20.0, 1.0), "ai_pow": (0.0, 0.3, 0.02), "max_turns": (12, 40, 2)}


def _ph_artillery(law, ph):
    ph = ph or {}
    return {"gravity": round(0.3 * ph.get("gravity_scale", 1.0), 4), "wind": round(float(ph.get("wind", 0.0)) * 0.5, 4), "armor": float(ph.get("armor_factor", 1.0))}


BASTION_BOUNDS = {"hp0": (14.0, 50.0, 2.0), "hp_growth": (1.1, 1.32, 0.02), "lives": (5, 16, 1), "money": (80, 220, 10), "speed": (1.0, 2.4, 0.2), "cannon_dmg": (6.0, 18.0, 1.0), "count_step": (1, 4, 1), "cost": (30, 60, 5)}


def _ph_bastion(law, ph):
    ph = ph or {}
    return {"gravity": round(0.3 * ph.get("gravity_scale", 1.0), 4), "armor": float(ph.get("armor_factor", 1.0))}


SPECS = {
    "bastion": {"script": "res://ghost/tune_bastion.gd", "bounds": BASTION_BOUNDS, "probes": [{}, {"hp0": 17.0, "hp_growth": 1.15}, {"hp0": 27.0, "hp_growth": 1.21}],
                "base": lambda law, ph=None, mod=None: {**_ph_bastion(law, ph), **(mod or {}), "hp0": 22.0, "hp_growth": 1.18, "lives": 10, "money": 120, "waves": 8, "count0": 6, "count_step": 2, "speed": 1.6,
                                                        "cannon_dmg": 10.0, "mortar_dmg": 9.0, "mortar_r": 46.0, "chill_slow": 0.5, "cost": 40, "bounty": 8, "wave_bonus": 25}},
    "artillery": {"script": "res://ghost/tune_artillery.gd", "bounds": ARTILLERY_BOUNDS,
                  "base": lambda law, ph=None, mod=None: {**_ph_artillery(law, ph), **(mod or {}), "hp": 100.0, "blast_r": 44.0, "blast_dmg": 60.0, "pmax": 18.0, "max_turns": 24, "ai_err": 5.0, "ai_pow": 0.08, "ai_wind": 1}},
    "splash": {"script": "res://ghost/tune_splash.gd", "bounds": SPLASH_BOUNDS,
               "base": lambda law, ph=None, mod=None: {**_ph_splash(law, ph), **(mod or {}), "splash_dmg": 45.0, "splash_r": 62.0 * (ph or {}).get("burst_radius", 1.0), "throw_cd": 30, "refill_ticks": 40,
                                    "max_ammo": 3, "team_size": 2, "max_ticks": 2400, "range": 320.0, "speed": 3.4, "en_lead": 0.5, "en_err": 40.0, "en_aggr": 0.65, "en_dodge": 0.5, "ally_level": 1}},
    "volley": {"script": "res://ghost/tune_volley.gd", "bounds": VOLLEY_BOUNDS,
               "base": lambda law, ph=None, mod=None: {**_ph_volley(law, ph), **(mod or {}), "jump": 10.5, "points": 7,
                                    "ai_lag": 11, "ai_err": 40.0, "ai_aggr": 0.65, "serve_pause": 40, "max_ticks": 14400, "move_acc": 1.5}},
    "arcade": {"script": "res://ghost/tune.gd", "bounds": ARCADE_BOUNDS,
               "base": lambda law, ph=None, mod=None: {"law": law, "law_strength": 1.0, "spawn_every": 14, "spawn_step": 3, "hazard_speed": 150.0, "goal": 4, "stage_secs": 32.0, "max_hazards": 22}},
    "cordon": {"script": "res://ghost/tune_contain.gd", "bounds": CORDON_BOUNDS,
               "base": lambda law, ph=None, mod=None: {**(mod or {}), "nodes": 12, "days": 30, "beta": 70, "flow": 6, "mort": 18, "rec": 10, "ap": 3, "meds": 8, "treat": 150, "q_days": 4, "seeds": 2, "win_pct": 60, "purge_cap": 15, "purge_ap": 2, "leak": 25, "jump": 4}},
}


def band(x, lo, hi, width):
    return 1.0 if lo <= x <= hi else max(0.0, 1 - ((lo - x) if x < lo else (x - hi)) / width)


def fitness(r):
    """Targets (design assumptions): expert 70-95%, average human 35-65%, novice <=10%. Older results without an 'average' tier use the legacy form."""
    sk, nov = r["skilled"], r["novice"]
    b = 1.0 if nov <= 0.10 else max(0.0, 1 - (nov - 0.10) / 0.4)
    if "average" in r:
        return _fair_pace(r) * (0.40 * band(r["average"], 0.35, 0.65, 0.35) + 0.25 * band(sk, 0.70, 0.95, 0.40) + 0.20 * b + 0.15 * min(1.0, max(0.0, (sk - nov) / 0.5)))
    s1 = r["skilled_stage1"]
    a = max(0.0, 1 - abs(sk - 0.70) / 0.70) if not (0.55 <= sk <= 0.85) else 1.0
    c = min(1.0, s1 / 0.9)
    g = min(1.0, max(0.0, (sk - nov) / 0.4))
    return 0.4 * a + 0.2 * b + 0.2 * c + 0.2 * g


def _fair_pace(r):
    """Sports games also need side-fairness and readable rallies (multiplies fitness when the tuner reports them)."""
    if "side_bias" not in r:
        return 1.0
    fair = 1.0 if r["side_bias"] <= 0.12 else max(0.0, 1 - (r["side_bias"] - 0.12) / 0.3)
    pace = band(r.get("rally", 7.0), 3.0, 12.0, 5.0) * (1.0 if r["ticks"] <= 9000 else max(0.0, 1 - (r["ticks"] - 9000) / 6000))
    return 0.55 + 0.25 * fair + 0.20 * pace


def in_target_band(r):
    """Release criterion for tuned games (stricter than the old skilled>=0.3 check)."""
    avg = r.get("average")
    if "side_bias" in r and not (r["side_bias"] <= 0.20 and 2.5 <= r.get("rally", 7.0) <= 16.0):
        return False
    return r["skilled"] >= 0.60 and r["novice"] <= 0.20 and r["skilled"] - r["novice"] >= 0.40 and (avg is None or 0.30 <= avg <= 0.75)


HARD_CAPS = {
    "bastion": {"hp0": (8.0, 90.0), "hp_growth": (1.05, 1.5), "lives": (3, 25), "money": (50, 320), "speed": (0.7, 3.2), "cannon_dmg": (4.0, 30.0), "count_step": (1, 6), "cost": (20, 80)},
    "artillery": {"hp": (40.0, 220.0), "blast_r": (22.0, 90.0), "blast_dmg": (25.0, 110.0), "ai_err": (0.2, 30.0), "ai_pow": (0.0, 0.4), "max_turns": (8, 60)},   # widening limits per kind: bounds may grow, but never beyond what the core can express sensibly
    "arcade": {"law_strength": (0.2, 3.0), "hazard_speed": (60.0, 320.0), "spawn_every": (5, 34), "max_hazards": (6, 40), "goal": (2, 8), "stage_secs": (18.0, 60.0), "spawn_step": (1, 5)},
    "volley": {"gravity": (0.2, 0.8), "jump": (8.0, 15.0), "restitution": (0.7, 1.4), "ai_lag": (1, 40), "ai_err": (0.0, 160.0), "ai_aggr": (0.05, 1.0), "points": (3, 15)},
    "splash": {"team_size": (1, 3), "splash_r": (40.0, 100.0), "splash_dmg": (25.0, 75.0), "speed": (2.2, 4.4), "en_lead": (0.0, 1.0), "en_err": (0.0, 150.0), "en_aggr": (0.1, 1.0), "en_dodge": (0.0, 1.0), "ally_level": (0, 2), "throw_cd": (12, 60)},
    "cordon": {"beta": (20, 160), "mort": (2, 50), "flow": (1, 25), "win_pct": (30, 85), "meds": (1, 20), "ap": (1, 5), "rec": (3, 30), "q_days": (2, 8), "seeds": (1, 6), "leak": (0, 90), "jump": (0, 30)},
}


def widen(kind, bounds, at_bounds):
    """Return bounds widened by 30% of the range in the saturated direction (within HARD_CAPS)."""
    out = dict(bounds)
    caps = HARD_CAPS.get(kind, {})
    for k, side in at_bounds.items():
        lo, hi, st = out[k]
        span = hi - lo
        clo, chi = caps.get(k, (lo, hi))
        if side == "hi":
            hi = min(chi, hi + span * 0.3)
        else:
            lo = max(clo, lo - span * 0.3)
        isf = isinstance(st, float)
        out[k] = (round(lo, 3) if isf else int(round(lo)), round(hi, 3) if isf else int(round(hi)), st)
    return out


def run_batch(project, sets, script, workers=4):
    chunks = [sets[i::workers] for i in range(workers)]
    def one(chunk):
        if not chunk:
            return []
        with tempfile.TemporaryDirectory() as d:
            ip, op = os.path.join(d, "in.json"), os.path.join(d, "out.json")
            json.dump(chunk, open(ip, "w"))
            r = subprocess.run([GODOT, "--headless", "--path", project, "--script", script, "--", ip, op], capture_output=True, text=True, timeout=900)
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


def mutate(p, rnd, bounds, rate=0.4):
    p = dict(p)
    for k, (lo, hi, st) in bounds.items():
        if rnd.random() < rate:
            v = p[k] + st * rnd.choice((-2, -1, 1, 2))
            p[k] = max(lo, min(hi, round(v, 3) if isinstance(st, float) else int(v)))
    return p


def tune(project, kind, law, seed, pop=16, gens=8, init=None, bounds_override=None, log=print, physics=None, mods=None):
    """Winner's-curse-safe: every generation uses fresh evaluation seeds, elites are re-evaluated, ranking uses the running mean."""
    spec = SPECS[kind]
    bounds, script = dict(spec["bounds"]), spec["script"]
    if bounds_override:
        bounds.update({k: tuple(v) for k, v in bounds_override.items() if k in bounds})
    rnd = random.Random(seed)
    base = spec["base"](law, physics, mods)
    popn = [base] + ([dict(init)] if init else []) + [mutate(base, rnd, bounds, 0.8) for _ in range(pop)]
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
        res = run_batch(project, [{"p": p, "seed_base": 1000 + 100 * g} for p in popn], script)
        for p, r in zip(popn, res):
            hist.setdefault(key(p), []).append(r)
        ranked = sorted(popn, key=lambda p: -mean_fit(p))
        b = mean_res(ranked[0])
        curve.append({"gen": g, "best_fitness": mean_fit(ranked[0]), "skilled": b["skilled"], "novice": b["novice"], "evals_of_best": len(hist[key(ranked[0])])})
        log(f"  tune[{kind}] gen {g}: fitness {mean_fit(ranked[0]):.3f} skilled {b['skilled']:.2f} novice {b['novice']:.2f} (n={len(hist[key(ranked[0])])})")
        if g == gens:
            break
        elite = ranked[:4]
        popn = list(elite)
        while len(popn) < pop:
            a, b2 = rnd.sample(elite, 2)
            c = {k: (a[k] if rnd.random() < .5 else b2[k]) for k in a}
            popn.append(mutate(c, rnd, bounds))
    # Selection on a first held-out seed set among the top candidates, then CONFIRMATION of the chosen one on a second, unseen set (winner's-curse-safe release check).
    top = ranked[:4]
    held = run_batch(project, [{"p": c, "seed_base": 7000} for c in top] + [{"p": base, "seed_base": 7000}], script)
    cand = list(zip(top, held[:len(top)]))
    inb = [x for x in cand if in_target_band(x[1])]
    best, sel = max(inb or cand, key=lambda x: fitness(x[1]))
    confirm = run_batch(project, [{"p": best, "seed_base": 9000}], script)[0]
    held = [confirm, held[-1]]
    at_bounds = {k: ("hi" if best[k] >= bounds[k][1] else "lo") for k in bounds if k in best and (best[k] >= bounds[k][1] or best[k] <= bounds[k][0])}
    return {"params": best, "curve": curve, "at_bounds": at_bounds, "bounds_used": {k: list(v) for k, v in bounds.items()}, "in_band": in_target_band(held[0]), "default_params": base, "holdout_best": held[0], "holdout_default": held[1], "selection_holdout": sel,
            "start_fitness": curve[0]["best_fitness"], "final_fitness": curve[-1]["best_fitness"], "evaluations": sum(len(v) for v in hist.values())}
