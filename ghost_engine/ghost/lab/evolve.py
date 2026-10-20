"""Evolution Engine: evolve the combat mechanic. Module-level crossover combines compatible discoveries;
elitism preserves successful mechanics; a hall of fame archives module variants; ablation measures what mattered.
Selection uses TRAIN seeds; reported results use disjoint HOLDOUT seeds to expose overfitting."""
import json, os, random, statistics
from ..kernel import rules as RU
from . import tournament as T

TRAIN_SEEDS = (1, 2)
HOLDOUT_SEEDS = tuple(range(101, 109))


def proposals():
    """Hand-authored design hypotheses (the 'AI designer' proposals). Evaluated like everything else; not trusted."""
    def mk(name, **kw):
        c = dict(RU.BASELINE["combat"]); c.update(kw)
        return {"name": name, "combat": RU.clamp_combat(c)}
    return [
        mk("claude_rps", guard_reduce_pct=60, guard_counter_pct=40, guard_pierce_pct=50, power_mult_pct=180, power_interrupt_pct=50),
        mk("claude_attrition", potion_heal=40, heal_vuln_pct=50, start_potions=4, fatigue_pct=10),
        mk("claude_glass", crit_pct=30, crit_mult_pct=220, power_mult_pct=130, guard_reduce_pct=50),
    ]


def mutate(c, rnd, rate=0.35):
    c = dict(c)
    for k, (lo, hi, st) in RU.COMBAT_BOUNDS.items():
        if rnd.random() < rate:
            if rnd.random() < 0.15:
                c[k] = lo + st * rnd.randint(0, (hi - lo) // st)
            else:
                c[k] = c[k] + st * rnd.choice((-2, -1, 1, 2))
    return RU.clamp_combat(c)


def crossover(a, b, rnd):
    c = dict(a)
    for mod, keys in RU.MODULES.items():
        src = a if rnd.random() < 0.5 else b
        for k in keys:
            c[k] = src[k]
    return c


def evolve(seed=1, generations=12, pop=16, elite=4, fights=16, log=None):
    rnd = random.Random(seed)
    base = dict(RU.BASELINE["combat"])
    population = [base] + [p["combat"] for p in proposals()]
    while len(population) < pop:
        population.append(mutate(base, rnd, 0.6))
    history = []
    hall = {m: [] for m in RU.MODULES}
    cache = {}

    def score(c):
        key = json.dumps(c, sort_keys=True)
        if key not in cache:
            cache[key] = T.fitness(c, TRAIN_SEEDS, fights)
        return cache[key]

    for gen in range(generations + 1):
        ranked = sorted(population, key=lambda c: -score(c)[0])
        fits = [score(c)[0] for c in ranked]
        rec = {"gen": gen, "best": fits[0], "mean": statistics.mean(fits), "worst": fits[-1],
               "best_combat": ranked[0], "best_metrics": {k: v for k, v in score(ranked[0])[1].items() if k != "top"},
               "unique": len({json.dumps(c, sort_keys=True) for c in population}), "evaluations": len(cache)}
        history.append(rec)
        if log:
            log(rec)
        for mod, keys in RU.MODULES.items():
            hall[mod].append({"gen": gen, "fitness": fits[0], "values": {k: ranked[0][k] for k in keys}})
        if gen == generations:
            break
        nxt = [dict(c) for c in ranked[:elite]]
        def pick():
            return min(rnd.sample(ranked, 3), key=lambda c: -score(c)[0])
        while len(nxt) < pop:
            child = crossover(pick(), pick(), rnd) if rnd.random() < 0.6 else dict(pick())
            nxt.append(mutate(child, rnd))
        population = nxt
    best = ranked[0]
    return best, history, hall


def validate(candidates, fights=24):
    """Held-out comparison: mean +- std over disjoint seeds, plus paired differences vs the first candidate."""
    out = {}
    base_scores = None
    for name, c in candidates.items():
        per_seed = []
        raw = []
        for sd in HOLDOUT_SEEDS:
            f, agg = T.fitness(c, (sd,), fights)
            per_seed.append(f)
            raw.append(agg)
        entry = {"mean": statistics.mean(per_seed), "std": statistics.pstdev(per_seed), "per_seed": per_seed,
                 "metrics": {k: statistics.mean(r[k] for r in raw) for k in ("dominance", "top_score", "distinct_best_responses", "cycles", "stalemate", "length", "skill", "live_actions")},
                 "parts": {k: statistics.mean(r["parts"][k] for r in raw) for k in T.WEIGHTS}}
        if base_scores is None:
            base_scores = per_seed
        else:
            diffs = [a - b for a, b in zip(per_seed, base_scores)]
            entry["paired_gain_mean"] = statistics.mean(diffs)
            entry["paired_gain_std"] = statistics.pstdev(diffs)
            entry["seeds_improved"] = sum(1 for d in diffs if d > 0)
        out[name] = entry
    return out


def ablate(best, fights=24):
    """Revert each mechanic module to baseline; the holdout fitness drop is that module's measured contribution."""
    full, _ = T.fitness(best, HOLDOUT_SEEDS, fights)
    rows = {}
    for mod, keys in RU.MODULES.items():
        c = dict(best)
        for k in keys:
            c[k] = RU.BASELINE["combat"][k]
        f, _ = T.fitness(c, HOLDOUT_SEEDS, fights)
        rows[mod] = {"fitness_without": f, "contribution": full - f, "evolved": {k: best[k] for k in keys},
                     "baseline": {k: RU.BASELINE["combat"][k] for k in keys}}
    return {"full": full, "modules": rows}
