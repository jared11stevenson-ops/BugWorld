"""Play-time policies that work for ANY spec. ids: 0-5 always-action-i, 6 cycle, 7 random, 8 adapter (best 1-ply response
to the opponent's empirical action mix, using the spec's value heuristic), 9 counter (best response to last action),
10 mirror, 11 greedy (best 1-ply vs a uniform opponent)."""
from ..kernel import rng as R
from . import dsl

ALWAYS = list(range(6))
CYCLE, RANDOM, ADAPTER, COUNTER, MIRROR, GREEDY = 6, 7, 8, 9, 10, 11
NAMES = {0: "always0", 1: "always1", 2: "always2", 3: "always3", 4: "always4", 5: "always5", 6: "cycle", 7: "random",
         8: "adapter", 9: "counter", 10: "mirror", 11: "greedy"}


def new_hist(n):
    return {"counts": [0] * n, "last": -1}


def observe(h, a):
    h["counts"][a] += 1
    h["last"] = a


def _best(spec, m, me, weights):
    best_a, best_v = 0, None
    for a in range(len(spec["actions"])):
        if not dsl.legal(spec, m, me, a):
            continue
        v = 0
        for b in range(len(weights)):
            if weights[b]:
                v += weights[b] * dsl.payoff(spec, m, me, a, b)
        if best_v is None or v > best_v:
            best_a, best_v = a, v
    return best_a


def choose(spec, pid, m, me, h):
    n = len(spec["actions"])
    if pid >= 100:          # scripted two-move line (lab-only): alternate a, b, a, b ...  (pid = 100 + 10*a + b)
        a, b = (pid - 100) // 10, (pid - 100) % 10
        want = a if m["round"] % 2 == 0 else b
        return want if want < n and dsl.legal(spec, m, me, want) else _best(spec, m, me, [1] * n)
    if pid < 6:
        # 'always action i'; when i is illegal or absent, fall back to the best greedy legal move (order-invariant)
        return pid if pid < n and dsl.legal(spec, m, me, pid) else _best(spec, m, me, [1] * n)
    if pid == CYCLE:
        return m["round"] % n
    if pid == RANDOM:
        return R.rand(m, n)
    if pid == ADAPTER:
        return _best(spec, m, me, [c + 1 for c in h["counts"]])
    if pid == COUNTER:
        w = [0] * n
        w[h["last"] if h["last"] >= 0 else 0] = 1
        return _best(spec, m, me, w)
    if pid == MIRROR:
        return h["last"] if h["last"] >= 0 else 0
    return _best(spec, m, me, [1] * n)


def play(spec, p0, p1, seed, record_usage=None):
    """Full match. Returns the finished match dict."""
    n = len(spec["actions"])
    m = dsl.new_match(spec, seed)
    h = [new_hist(n), new_hist(n)]
    while not m["done"]:
        a0 = choose(spec, p0, m, 0, h[0])
        a1 = choose(spec, p1, m, 1, h[1])
        s0, s1 = dsl.step(spec, m, a0, a1)
        observe(h[0], s1)
        observe(h[1], s0)
        if record_usage is not None:
            if p0 == ADAPTER:
                record_usage[s0] += 1
            if p1 == ADAPTER and p0 != ADAPTER:
                record_usage[s1] += 1
    return m
