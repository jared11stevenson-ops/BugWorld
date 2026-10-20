"""Causal Laboratory: paired A/B world experiments, counterfactual branches, exploit fuzzing, rule sensitivity.
Everything is seeded; results are measured from simulation state, never narrated."""
import math, random, statistics
from ..kernel import rules as RU, world as W
from ..kernel.timeline import Timeline
from . import tournament as T


def gini(xs):
    xs = sorted(xs)
    n = len(xs)
    tot = sum(xs)
    if n == 0 or tot == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * tot)


def world_metrics(s, since_event=0):
    evs = s["events"][since_event:]
    cnt = lambda t: sum(1 for e in evs if e[2] == t)
    alive = [n for n in s["npcs"] if n["alive"]]
    gold = [n["gold"] for n in alive]
    tot = sum(gold)
    return {"alive": len(alive), "kills": cnt(W.EV_KILL), "fights": cnt(W.EV_FIGHT), "wars": cnt(W.EV_WAR),
            "peaces": cnt(W.EV_PEACE), "trades": cnt(W.EV_BUY) + cnt(W.EV_SELL),
            "gini": gini(gold), "richest_share": (max(gold) / tot) if tot else 0.0,
            "gold_supply": W.total_gold(s), "supply_growth": W.total_gold(s) / max(1, s["gold0"]),
            "bankrupt_towns": sum(1 for t in s["towns"] if t["treasury"] == 0),
            "conservation_error": W.conservation_error(s)}


def run_world(rules, seed, ticks):
    s = W.new_world(seed, rules)
    W.run(s, ticks)
    return s


def mean_ci(xs):
    n = len(xs)
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if n > 1 else 0.0
    return {"mean": m, "ci95": 1.96 * sd / math.sqrt(n) if n > 1 else 0.0, "n": n}


def ab_test(rules_a, rules_b, seeds, ticks):
    """Same initial worlds (seed), different rules. Paired difference b - a per metric."""
    rows_a, rows_b = [], []
    for sd in seeds:
        rows_a.append(world_metrics(run_world(rules_a, sd, ticks)))
        rows_b.append(world_metrics(run_world(rules_b, sd, ticks)))
    out = {}
    for k in rows_a[0]:
        diffs = [b[k] - a[k] for a, b in zip(rows_a, rows_b)]
        out[k] = {"a": statistics.mean(r[k] for r in rows_a), "b": statistics.mean(r[k] for r in rows_b),
                  "diff": mean_ci(diffs)}
    return out


def counterfactual(rules, seeds, t0, horizon, kind):
    """Branch each world at t0. Baseline branch continues untouched; alt branch gets an intervention.
    Effect = paired difference over the window (t0, t0+horizon]."""
    rows = []
    for sd in seeds:
        main = Timeline(W.new_world(sd, rules))
        main.step(t0)
        alt = main.fork("alt")
        target = max(main.s["npcs"], key=lambda n: (n["kills"] * 1000 + n["gold"] if kind == "kill_deadliest" else n["gold"], -n["id"]))
        if kind == "kill_deadliest":
            alt.intervene("kill", [target["id"]])
        elif kind == "kill_richest":
            alt.intervene("kill", [target["id"]])
        elif kind == "windfall":
            alt.intervene("give_gold", [target["id"], 500])
        elif kind == "force_war":
            alt.intervene("set_rel", [0, 1, -90])
        e0 = len(main.s["events"])
        a0 = len(alt.s["events"])
        main.step(horizon)
        alt.step(horizon)
        ma, mb = world_metrics(main.s, e0), world_metrics(alt.s, a0)
        diverged = W.digest(main.s) != W.digest(alt.s)
        rows.append((ma, mb, diverged))
    out = {"kind": kind, "t0": t0, "horizon": horizon, "n": len(rows), "diverged_fraction": sum(r[2] for r in rows) / len(rows), "effects": {}}
    for k in ("kills", "fights", "wars", "alive", "trades", "gini", "richest_share"):
        diffs = [b[k] - a[k] for a, b, _ in rows]
        out["effects"][k] = {"baseline": statistics.mean(a[k] for a, _, _ in rows), "branch": statistics.mean(b[k] for _, b, _ in rows),
                             "paired_diff": mean_ci(diffs)}
    return out


# ---------------------------------------------------------------- exploit fuzzing
def random_rules(rnd):
    r = RU.clone(RU.BASELINE)
    r["name"] = "fuzz"
    for k, (lo, hi, st) in RU.COMBAT_BOUNDS.items():
        r["combat"][k] = lo + st * rnd.randint(0, (hi - lo) // st)
    e, w = r["economy"], r["world"]
    e["sell_pct"] = rnd.choice([40, 60, 80, 100, 120, 150])
    e["swing_pct"] = rnd.choice([0, 5, 10, 15, 25, 30])
    e["base_price"] = rnd.choice([4, 10, 20, 40])
    e["wage"] = rnd.choice([0, 1, 2, 4, 8])
    e["burn"] = rnd.choice([0, 1, 3, 6])
    e["restock_ticks"] = rnd.choice([2, 6, 12, 24])
    w["aggro_pct"] = rnd.choice([0, 2, 4, 8, 16, 30])
    w["loot_pct"] = rnd.choice([0, 25, 50, 100])
    w["flee_pct"] = rnd.choice([0, 25, 50, 90])
    w["respawn_delay"] = rnd.choice([5, 20, 60])
    RU.validate(r)
    return r


FLAGS = {
    "dominant_strategy": lambda lab, wm: lab["dominance"] >= 0.9,
    "combat_stalemate": lambda lab, wm: lab["stalemate"] >= 0.15,
    "extinction_risk": lambda lab, wm: wm["alive"] < 8,
    "wealth_runaway": lambda lab, wm: wm["richest_share"] > 0.35,
    "money_inflation": lambda lab, wm: wm["supply_growth"] > 8,
    "bankrupt_economy": lambda lab, wm: wm["bankrupt_towns"] >= 4,
    "ledger_violation": lambda lab, wm: wm["conservation_error"] != 0,
}


def fuzz(n, seed=1, ticks=400):
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        r = random_rules(rnd)
        lab = T.metrics(r["combat"], 500 + i, 8)
        wm = world_metrics(run_world(r, 900 + i, ticks))
        flags = [k for k, f in FLAGS.items() if f(lab, wm)]
        rows.append({"rules": r, "lab": {k: lab[k] for k in ("dominance", "stalemate", "length", "cycles", "distinct_best_responses")},
                     "world": wm, "flags": flags})
    summary = {k: sum(1 for r in rows if k in r["flags"]) for k in FLAGS}
    drivers = {}
    for k in FLAGS:
        hit = [r for r in rows if k in r["flags"]]
        miss = [r for r in rows if k not in r["flags"]]
        if len(hit) < 3 or len(miss) < 3:
            continue
        eff = []
        for sec in ("combat", "economy", "world"):
            for p in rows[0]["rules"][sec]:
                if p == "round_cap":
                    continue
                a = [r["rules"][sec][p] for r in hit]
                b = [r["rules"][sec][p] for r in miss]
                sd = statistics.pstdev(a + b)
                if sd > 0:
                    eff.append((abs(statistics.mean(a) - statistics.mean(b)) / sd, f"{sec}.{p}", statistics.mean(a), statistics.mean(b)))
        eff.sort(reverse=True)
        drivers[k] = [{"param": p, "std_diff": round(d, 2), "flagged_mean": round(ma, 1), "unflagged_mean": round(mb, 1)} for d, p, ma, mb in eff[:3]]
    return {"n": n, "ticks": ticks, "summary": summary, "drivers": drivers, "rows": rows}


def sensitivity(best, fights=16):
    """One-at-a-time +-1 step perturbation of each evolved parameter: which rules actually move quality?"""
    seeds = (101, 102, 103, 104)
    f0, _ = T.fitness(best, seeds, fights)
    rows = []
    for k, (lo, hi, st) in RU.COMBAT_BOUNDS.items():
        deltas = []
        for d in (-2, 2):
            c = dict(best)
            c[k] = max(lo, min(hi, c[k] + d * st))
            if c[k] == best[k]:
                continue
            f, _ = T.fitness(c, seeds, fights)
            deltas.append(f - f0)
        if deltas:
            rows.append({"param": k, "value": best[k], "max_abs_fitness_change": max(abs(x) for x in deltas), "deltas": deltas})
    rows.sort(key=lambda r: -r["max_abs_fitness_change"])
    return {"baseline_fitness": f0, "rows": rows}
