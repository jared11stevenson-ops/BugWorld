"""Experience Intelligence for arbitrary concepts. Structural proxies only (not enjoyment). Weights/bands are assumptions."""
from . import dsl, agents as A

WEIGHTS = {"dominance": 1.5, "counterplay": 1.0, "cycles": 0.75, "liveness": 1.5, "decisive": 1.0,
           "length": 0.5, "skill": 1.0, "interaction": 1.5, "leverage": 1.0}
LENGTH_BAND = (5, 18)
LEVERAGE_BAND = (0.15, 0.6)   # assumed sweet spot: below = predetermined, above = chaotic
LIVE_SHARE = 0.05


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def interaction_score(spec, m):
    """Non-additivity of the payoff matrix: 0 = actions are independent solitaire moves, ~1 = outcome is all about the pairing."""
    n = len(spec["actions"])
    legal = [a for a in range(n) if dsl.legal(spec, m, 0, a)]
    M = [[dsl.payoff(spec, m, 0, a, b) for b in range(n)] for a in legal]
    if len(legal) < 2:
        return 0.0
    rows = [sum(r) / n for r in M]
    cols = [sum(M[i][j] for i in range(len(legal))) / len(legal) for j in range(n)]
    g = sum(rows) / len(legal)
    inter = sum(abs(M[i][j] - rows[i] - cols[j] + g) for i in range(len(legal)) for j in range(n)) / (len(legal) * n)
    mag = sum(abs(M[i][j]) for i in range(len(legal)) for j in range(n)) / (len(legal) * n)
    return inter / (mag + 1e-9) if mag > 0 else 0.0


def _continue(spec, m, a0_first, a1_first):
    """Branch helper: apply the given first actions, then both sides play 'cycle' to the end. Returns winner."""
    b = dsl.clone_match(m)
    first = True
    while not b["done"]:
        if first:
            dsl.step(spec, b, a0_first, a1_first)
            first = False
        else:
            n = len(spec["actions"])
            dsl.step(spec, b, b["round"] % n, b["round"] % n)
    return b["winner"]


def leverage(spec, seed, games=3):
    """Causal agency via timeline branching: at each round of sampled games, force every alternative legal action for
    player 0 (everything else equal, cycle continuation) and count how often the final result flips."""
    n = len(spec["actions"])
    flips = total = 0
    inter = []
    for g in range(games):
        m = dsl.new_match(spec, seed * 31 + g)
        h = [A.new_hist(n), A.new_hist(n)]
        while not m["done"] and m["round"] < 12:
            a0 = A.choose(spec, A.ADAPTER, m, 0, h[0])
            a1 = A.choose(spec, A.RANDOM, m, 1, h[1])
            if m["round"] in (0, 2, 4):
                inter.append(interaction_score(spec, m))
            base = _continue(spec, m, a0, a1)
            for alt in range(n):
                if alt != a0 and dsl.legal(spec, m, 0, alt):
                    total += 1
                    flips += 1 if _continue(spec, m, alt, a1) != base else 0
            s0, s1 = dsl.step(spec, m, a0, a1)
            A.observe(h[0], s1); A.observe(h[1], s0)
    return (flips / total if total else 0.0), (sum(inter) / len(inter) if inter else 0.0)


def _score(m):
    return 1.0 if m["winner"] == 0 else (0.5 if m["winner"] == -1 else 0.0)


def dominant_line(spec, seed, fixed):
    """Non-stationary check: does any scripted two-move line (a,b,a,b,...) beat every static baseline >=90%?"""
    n = len(spec["actions"])
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            pid = 100 + 10 * a + b
            ok = True
            for j in fixed:
                wins = sum(_score(A.play(spec, pid, j, seed * 61 + a * 7 + b + k * 13 + j)) for k in range(3)) / 3
                if wins < 0.9:
                    ok = False
                    break
            if ok:
                return [a, b]
    return None


def _uses_rnd(spec):
    return "rnd" in json_dump(spec)


def json_dump(spec):
    import json
    return json.dumps([spec["actions"], spec["passive"]])


def luck(spec, seed, fixed):
    """Seed sensitivity: same two deterministic strategies, different RNG seeds -> how often is the minority outcome seen?
    0 = outcome fixed by the choices; ~0.5 = coin flips. Only specs using 'rnd' can be luck-dominated."""
    if not _uses_rnd(spec):
        return 0.0
    ids = [i for i in fixed if i != A.RANDOM] + [A.ADAPTER]
    tot = n = 0.0
    for x, i in enumerate(ids):
        for j in ids[x + 1:]:
            res = [A.play(spec, i, j, seed * 977 + k * 31 + i + j)["winner"] for k in range(6)]
            wins0 = sum(1 for r in res if r == 0); wins1 = sum(1 for r in res if r == 1)
            tot += min(wins0, wins1) / 6; n += 1
    return tot / n if n else 0.0


def evaluate(spec, seed=1, fights=6):
    errs = dsl.validate(spec)
    if errs:
        return {"valid": False, "errors": errs, "flags": ["invalid_spec"], "fitness": 0.0, "metrics": {}, "parts": {}}
    n = len(spec["actions"])
    fixed = list(range(n)) + [A.RANDOM]           # order-invariant static baselines (no 'cycle': it depends on action order)
    ids = fixed + [A.ADAPTER]
    W = {}
    usage = [0] * n
    rounds = games = timeouts = 0
    half = max(1, fights // 2)
    for x, i in enumerate(ids):
        for j in ids[x + 1:]:
            acc = 0.0
            for k in range(2 * half):             # both seats measured: first half i is seat 0, second half seat 1
                s = seed * 7919 + i * 131 + j * 17 + k
                if k < half:
                    m = A.play(spec, i, j, s, usage); acc += _score(m)
                else:
                    m = A.play(spec, j, i, s, usage); acc += 1.0 - _score(m)
                rounds += m["round"]; games += 1; timeouts += 1 if (m["timeout"] and m["winner"] == -1) else 0
            W[(i, j)] = acc / (2 * half)
            W[(j, i)] = 1 - acc / (2 * half)
    seat = [0, 0]
    for k in range(2 * half):                     # adapter mirror: usage, length, SEAT BIAS
        m = A.play(spec, A.ADAPTER, A.ADAPTER, seed * 104729 + k, usage)
        rounds += m["round"]; games += 1; timeouts += 1 if (m["timeout"] and m["winner"] == -1) else 0
        if m["winner"] >= 0:
            seat[m["winner"]] += 1
    seat_bias = abs(seat[0] - seat[1]) / max(1, sum(seat)) if sum(seat) >= 4 else 0.0
    worst = {i: min(W[(i, j)] for j in fixed if j != i) for i in fixed}
    dominance = max(worst.values())
    best_resp = {-max((W[(i, j)], -i) for i in fixed if i != j)[1] for j in fixed}
    cycles = 0
    for x in range(len(fixed)):
        for y in range(x + 1, len(fixed)):
            for z in range(y + 1, len(fixed)):
                i, j, l = fixed[x], fixed[y], fixed[z]
                if (W[(i, j)] > .55 and W[(j, l)] > .55 and W[(l, i)] > .55) or (W[(j, i)] > .55 and W[(l, j)] > .55 and W[(i, l)] > .55):
                    cycles += 1
    tot_use = max(1, sum(usage))
    shares = [u / tot_use for u in usage]
    inert = set(dsl.inert_actions(spec))
    used = {a for a in range(n) if shares[a] >= LIVE_SHARE}
    live_set = (used | {a for a in best_resp if a < n}) - inert       # used by the agent OR a winning pure response; never cosmetic
    live = len(live_set)
    top3 = sorted(fixed, key=lambda i: -sum(W[(i, j)] for j in fixed if j != i))[:3]
    skill = sum(W[(A.ADAPTER, j)] for j in top3) / len(top3)            # adapter vs the STRONGEST static strategies
    lev, inter = leverage(spec, seed)
    inter = min(inter, 1.5)
    line = dominant_line(spec, seed, fixed)
    lk = luck(spec, seed, fixed)
    relevant = dsl.relevant_vars(spec)
    decoy_value = [v for v, _w in spec["value"] if v not in relevant]
    mt = {"dominance": dominance, "distinct_best_responses": len(best_resp), "cycles": cycles, "live_actions": live,
          "n_actions": n, "timeout_rate": timeouts / games, "length": rounds / games, "skill": skill,
          "interaction": inter, "leverage": lev, "action_shares": shares, "seat_bias": seat_bias,
          "inert_actions": sorted(inert), "dominant_line": line, "luck": lk}
    lo, hi = LENGTH_BAND
    dist = 0 if lo <= mt["length"] <= hi else min(abs(mt["length"] - lo), abs(mt["length"] - hi))
    llo, lhi = LEVERAGE_BAND
    lscore = 1.0 if llo <= lev <= lhi else (lev / llo if lev < llo else max(0.0, 1 - (lev - lhi) / (1 - lhi)))
    parts = {"dominance": 1 - _clamp((dominance - 0.3) / 0.4), "counterplay": _clamp((len(best_resp) - 1) / 3),
             "cycles": min(cycles, 3) / 3, "liveness": _clamp((live - 1) / max(1, n - 1)),
             "decisive": 1 - _clamp(mt["timeout_rate"] * 2.5), "length": _clamp(1 - dist / 10),
             "skill": _clamp((skill - 0.5) * 4), "interaction": _clamp(inter / 0.5), "leverage": _clamp(lscore)}
    fitness = sum(WEIGHTS[k] * parts[k] for k in WEIGHTS) / sum(WEIGHTS.values())
    flags = []
    if dominance >= 0.85: flags.append("dominant_strategy")
    if line: flags.append("dominant_line")
    if live < max(2, (n + 1) // 2): flags.append("dead_actions")
    if inert: flags.append("inert_action")
    if decoy_value: flags.append("misleading_value")
    if inter < 0.1: flags.append("no_interaction")
    if mt["timeout_rate"] > 0.3: flags.append("stalemate")
    if mt["length"] < 4: flags.append("too_short")
    if mt["length"] > 22: flags.append("too_long")
    if skill < 0.55: flags.append("no_skill_edge")
    if lev < 0.05: flags.append("predetermined")
    if lev > 0.85: flags.append("chaotic")
    if seat_bias > 0.3: flags.append("seat_bias")
    if lk > 0.2: flags.append("luck_dominated")
    return {"valid": True, "errors": [], "flags": flags, "fitness": fitness, "metrics": mt, "parts": parts}
