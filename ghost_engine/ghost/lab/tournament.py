"""Experience Intelligence: measurable proxies computed from round-robin policy tournaments.
These are *structural* metrics (dominance, counterplay, cycles, stalemates, skill expression),
NOT measurements of human enjoyment. Weights/bands below are design assumptions, stated openly."""
from ..kernel import rng as R, combat as C, policies as P

K = P.NUM
FIGHTER = {"maxhp": 100, "atk": 20, "def": 5}
WEIGHTS = {"dominance": 1.5, "counterplay": 1.5, "cycles": 1.0, "stalemate": 1.5, "length": 0.5, "skill": 1.0, "liveness": 1.5}
LIVE_SHARE = 0.05   # an action chosen by <5% of the adaptive agents' decisions is a "dead" (trap) option
LENGTH_BAND = (6, 16)   # assumed 'readable' fight length in rounds


def _fighter(c):
    f = dict(FIGHTER)
    f["hp"] = f["maxhp"]
    f["potions"] = c["start_potions"]
    C.reset(f)
    return f


def duel(c, pa, pb, seed, usage=None):
    """Equal-stat duel. Returns (score_for_a in {0,.5,1}, rounds, stalemate)."""
    s = {"rng": R.seed_state(seed)}
    a, b = _fighter(c), _fighter(c)
    ha, hb = P.new_hist(), P.new_hist()
    rounds = 0
    while a["hp"] > 0 and b["hp"] > 0 and rounds < c["round_cap"]:
        xa = P.choose(pa, a, b, ha, c, s)
        xb = P.choose(pb, b, a, hb, c, s)
        xa, xb = C.fight_round(c, a, b, xa, xb, s)
        if usage is not None:
            if pa in P.ADAPTIVE:
                usage[xa] += 1
            if pb in P.ADAPTIVE and pa != pb:
                usage[xb] += 1
        P.observe(ha, xb)
        P.observe(hb, xa)
        rounds += 1
    if a["hp"] > 0 and b["hp"] > 0:
        return 0.5, rounds, True
    if a["hp"] <= 0 and b["hp"] <= 0:
        return 0.5, rounds, False
    return (1.0 if b["hp"] <= 0 else 0.0), rounds, False


def tournament(c, base_seed, fights=24):
    W = [[0.5] * K for _ in range(K)]
    total_rounds = n = stale = pairs = 0
    usage = [0, 0, 0, 0]
    for i in range(K):
        for j in range(i, K):
            acc = 0.0
            st_here = 0
            for k in range(fights):
                sc, rounds, st = duel(c, i, j, base_seed * 1000003 + (i * K + j) * 997 + k, usage)
                acc += sc
                total_rounds += rounds
                st_here += 1 if st else 0
                n += 1
            if i != j:           # mirror matches excluded from the stalemate metric (guardian vs guardian is trivially a stall)
                W[i][j] = acc / fights
                W[j][i] = 1.0 - W[i][j]
                stale += st_here / fights
                pairs += 1
    return W, total_rounds / n, stale / pairs, usage


def metrics(c, base_seed, fights=24):
    W, length, stale, usage = tournament(c, base_seed, fights)
    tot_use = max(1, sum(usage))
    shares = [u / tot_use for u in usage]
    F = P.FIXED
    score = [sum(W[i][j] for j in F if j != i) / (len(F) - 1) for i in F]       # static strategies vs static strategies
    best_resp = []
    for j in F:
        best_resp.append(max((W[i][j], -i) for i in F if i != j)[1])
    cycles = 0
    for x in range(len(F)):
        for y in range(x + 1, len(F)):
            for z in range(y + 1, len(F)):
                i, j, l = F[x], F[y], F[z]
                if (W[i][j] > .55 and W[j][l] > .55 and W[l][i] > .55) or (W[j][i] > .55 and W[l][j] > .55 and W[i][l] > .55):
                    cycles += 1
    skill = sum(W[a][j] for a in P.ADAPTIVE for j in F) / (len(P.ADAPTIVE) * len(F))
    top = F[score.index(max(score))]
    # robust dominance: the best worst-case matchup of any static strategy. >=0.5 means some strategy is never
    # beaten by another static strategy; a balanced game has a counter (>=0.65) for every strategy => value <= 0.35.
    worst = [min(W[i][j] for j in F if j != i) for i in F]
    return {"score": score, "top_score": max(score), "dominance": max(worst), "top_policy": P.NAMES[top],
            "distinct_best_responses": len(set(best_resp)), "cycles": cycles, "stalemate": stale,
            "length": length, "skill": skill, "matrix": W,
            "live_actions": sum(1 for x in shares if x >= LIVE_SHARE), "action_shares": shares}


def fitness_parts(m):
    lo, hi = LENGTH_BAND
    dist = 0 if lo <= m["length"] <= hi else min(abs(m["length"] - lo), abs(m["length"] - hi))
    return {"dominance": 1 - max(0.0, min(1.0, (m["dominance"] - 0.3) / 0.4)),
            "counterplay": min(1.0, (m["distinct_best_responses"] - 1) / 3),
            "cycles": min(m["cycles"], 3) / 3,
            "stalemate": 1 - min(1.0, m["stalemate"] * 5),
            "length": max(0.0, 1 - dist / 10),
            "skill": max(0.0, min(1.0, (m["skill"] - 0.5) * 4)),
            "liveness": max(0.0, min(1.0, (m["live_actions"] - 1) / 3))}


def fitness(c, seeds, fights=24):
    """Mean weighted fitness in [0,1] over seed blocks; also returns averaged raw metrics."""
    tot = 0.0
    agg = {}
    parts_acc = {k: 0.0 for k in WEIGHTS}
    for sd in seeds:
        m = metrics(c, sd, fights)
        parts = fitness_parts(m)
        tot += sum(WEIGHTS[k] * parts[k] for k in WEIGHTS) / sum(WEIGHTS.values())
        for k in parts:
            parts_acc[k] += parts[k] / len(seeds)
        for k in ("dominance", "top_score", "distinct_best_responses", "cycles", "stalemate", "length", "skill", "live_actions"):
            agg[k] = agg.get(k, 0) + m[k] / len(seeds)
        agg.setdefault("top", []).append(m["top_policy"])
    agg["parts"] = parts_acc
    return tot / len(seeds), agg
