"""Decision policies ('player archetypes'). Used by NPCs in the world and by the lab tournament."""
from . import combat as C, rng as R

NAMES = ["attacker", "turtle", "bruiser", "medic", "chaos", "adapter", "counter", "guardian"]
NUM = len(NAMES)
ADAPTER, CHAOS, COUNTER = 5, 4, 6
FIXED = [0, 1, 2, 3, 4, 7]
ADAPTIVE = [5, 6]


def new_hist():
    return {"counts": [0, 0, 0, 0], "last": -1}


def observe(h, act):
    h["counts"][act] += 1
    h["last"] = act


def _best(c, me, opp, weights):
    best_a, best_v = 0, None
    for a in range(4):
        if a == C.HEAL and me["potions"] <= 0:
            continue
        v = 0
        for b in range(4):
            if weights[b]:
                v += weights[b] * C.payoff(c, me, opp, a, b)
        if best_v is None or v > best_v:
            best_a, best_v = a, v
    return best_a


def choose(pid, me, opp, h, c, s):
    if pid == 0:
        return C.ATTACK
    if pid == 1:
        return C.GUARD if me["hp"] * 100 < 60 * me["maxhp"] else C.ATTACK
    if pid == 2:
        return C.POWER
    if pid == 3:
        if me["hp"] * 100 <= 40 * me["maxhp"] and me["potions"] > 0:
            return C.HEAL
        return C.ATTACK
    if pid == 4:
        return R.rand(s, 4)
    if pid == 5:
        w = [h["counts"][i] + 1 for i in range(4)]
        return _best(c, me, opp, w)
    if pid == 7:
        return C.GUARD
    # counter: best response to the opponent's previous action
    last = h["last"] if h["last"] >= 0 else C.ATTACK
    w = [0, 0, 0, 0]
    w[last] = 1
    return _best(c, me, opp, w)
