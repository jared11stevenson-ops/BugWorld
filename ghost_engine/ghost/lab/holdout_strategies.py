"""Overfitting check: strategies that were NEVER used during evolution (ids >= 8, lab-only, not in the kernel).
Robust dominance is recomputed over (fixed policies + these) to see whether the champion merely beat the training policy set."""
import json, os, statistics
from ..kernel import combat as C, policies as P, rng as R
from ..kernel import rules as RU
from . import tournament as T

H_NAMES = ["alternator", "opener_guard", "greedy_medic", "mirror"]
HOLD = [8, 9, 10, 11]


def choose(pid, me, opp, h, c, s, rounds):
    if pid < 8:
        return P.choose(pid, me, opp, h, c, s)
    if pid == 8:      # cycles attack, power, guard
        return (C.ATTACK, C.POWER, C.GUARD)[rounds % 3]
    if pid == 9:      # power first, then guard while healthy, attack when hurt
        return C.POWER if rounds == 0 else (C.GUARD if me["hp"] * 100 >= 50 * me["maxhp"] else C.ATTACK)
    if pid == 10:     # drinks early and often
        return C.HEAL if me["hp"] * 100 < 70 * me["maxhp"] and me["potions"] > 0 else C.POWER
    return h["last"] if h["last"] >= 0 else C.ATTACK   # mirror: copies the opponent's last action


def duel(c, pa, pb, seed):
    s = {"rng": R.seed_state(seed)}
    a, b = T._fighter(c), T._fighter(c)
    ha, hb = P.new_hist(), P.new_hist()
    rounds = 0
    while a["hp"] > 0 and b["hp"] > 0 and rounds < c["round_cap"]:
        xa = choose(pa, a, b, ha, c, s, rounds)
        xb = choose(pb, b, a, hb, c, s, rounds)
        xa, xb = C.fight_round(c, a, b, xa, xb, s)
        P.observe(ha, xb); P.observe(hb, xa)
        rounds += 1
    if (a["hp"] > 0) == (b["hp"] > 0):
        return 0.5
    return 1.0 if b["hp"] <= 0 else 0.0


def extended_dominance(c, seed, fights=16):
    ids = P.FIXED + HOLD
    W = {}
    for i in ids:
        for j in ids:
            if i < j:
                v = sum(duel(c, i, j, seed * 7919 + i * 131 + j * 17 + k) for k in range(fights)) / fights
                W[(i, j)], W[(j, i)] = v, 1 - v
    worst = {i: min(W[(i, j)] for j in ids if j != i) for i in ids}
    top = max(worst, key=lambda i: (worst[i], -i))
    return worst[top], (P.NAMES + H_NAMES)[top] if top < 8 else H_NAMES[top - 8], worst


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cands = {"baseline_v0": RU.BASELINE["combat"]}
    runs = json.load(open(os.path.join(root, "evidence", "lab", "evolution_runs.json")))
    for r in runs:
        cands[f"evolved_run{r['seed']}"] = r["best"]
    out = {}
    for name, c in cands.items():
        rows = [extended_dominance(c, sd) for sd in range(101, 109)]
        out[name] = {"extended_robust_dominance_mean": statistics.mean(r[0] for r in rows),
                     "std": statistics.pstdev(r[0] for r in rows),
                     "top_strategies": sorted({r[1] for r in rows}),
                     "holdout_worst_case": {H_NAMES[h - 8]: statistics.mean(r[2][h] for r in rows) for h in HOLD}}
        print(name, round(out[name]["extended_robust_dominance_mean"], 3), out[name]["top_strategies"],
              {k: round(v, 2) for k, v in out[name]["holdout_worst_case"].items()})
    with open(os.path.join(root, "evidence", "lab", "holdout_strategies.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
