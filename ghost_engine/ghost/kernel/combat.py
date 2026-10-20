"""Simultaneous-action combat. One round primitive shared by duels (lab) and the world.
Fighters are dicts with hp,maxhp,atk,def,potions,last,streak. All math is integer."""
from . import rng as R

ATTACK, GUARD, POWER, HEAL = 0, 1, 2, 3
CRIT_ROLL, CRIT_EXPECTED = 0, 1


def reset(f):
    f["last"] = -1
    f["streak"] = 0


def base_damage(x, y):
    return max(1, x["atk"] - y["def"])


def sanitize(act, f):
    if act == HEAL and f["potions"] <= 0:
        return ATTACK
    return act


def _dealt(c, x, y, act_x, act_y, rep, s, mode):
    if act_x == ATTACK:
        d = base_damage(x, y)
    elif act_x == POWER:
        d = base_damage(x, y) * c["power_mult_pct"] // 100
        if act_y == ATTACK:
            d = d * c["power_interrupt_pct"] // 100
    else:
        return 0
    if c["fatigue_pct"] > 0 and rep > 0:
        d = d * max(20, 100 - c["fatigue_pct"] * rep) // 100
    if d > 0:
        if mode == CRIT_ROLL:
            if R.rand(s, 100) < c["crit_pct"]:
                d = d * c["crit_mult_pct"] // 100
        else:
            d = d * (10000 + c["crit_pct"] * (c["crit_mult_pct"] - 100)) // 10000
    return d


def _taken(c, raw, act_y, act_x):
    if raw <= 0:
        return 0
    if act_y == GUARD:
        red = c["guard_reduce_pct"]
        if act_x == POWER:
            red = red * c["guard_pierce_pct"] // 100
        raw = raw * (100 - red) // 100
    elif act_y == HEAL:
        raw = raw * (100 + c["heal_vuln_pct"]) // 100
    return raw


def _rep(f, act):
    return f["streak"] if act == f["last"] else 0


def round_outcome(c, a, b, act_a, act_b, s, mode):
    """Returns (damage_to_a, damage_to_b, heal_a, heal_b). Rolls RNG only in CRIT_ROLL mode (a's crit first)."""
    raw_b = _dealt(c, a, b, act_a, act_b, _rep(a, act_a), s, mode)   # a's attack aimed at b
    raw_a = _dealt(c, b, a, act_b, act_a, _rep(b, act_b), s, mode)   # b's attack aimed at a
    dmg_b = _taken(c, raw_b, act_b, act_a)
    dmg_a = _taken(c, raw_a, act_a, act_b)
    if act_b == GUARD and act_a == ATTACK and c["guard_counter_pct"] > 0:
        dmg_a += base_damage(b, a) * c["guard_counter_pct"] // 100
    if act_a == GUARD and act_b == ATTACK and c["guard_counter_pct"] > 0:
        dmg_b += base_damage(a, b) * c["guard_counter_pct"] // 100
    heal_a = min(c["potion_heal"], a["maxhp"] - a["hp"]) if act_a == HEAL else 0
    heal_b = min(c["potion_heal"], b["maxhp"] - b["hp"]) if act_b == HEAL else 0
    return dmg_a, dmg_b, heal_a, heal_b


def payoff(c, a, b, act_a, act_b):
    """Expected one-round hp swing for a (no RNG). Used by the adaptive policies."""
    act_a = sanitize(act_a, a)
    act_b = sanitize(act_b, b)
    da, db, ha, hb = round_outcome(c, a, b, act_a, act_b, None, CRIT_EXPECTED)
    return db - da + ha - hb


def fight_round(c, a, b, act_a, act_b, s):
    act_a = sanitize(act_a, a)
    act_b = sanitize(act_b, b)
    da, db, ha, hb = round_outcome(c, a, b, act_a, act_b, s, CRIT_ROLL)
    if act_a == HEAL:
        a["potions"] -= 1
    if act_b == HEAL:
        b["potions"] -= 1
    a["hp"] = a["hp"] + ha - da
    b["hp"] = b["hp"] + hb - db
    for f, act in ((a, act_a), (b, act_b)):
        f["streak"] = f["streak"] + 1 if act == f["last"] else 0
        f["last"] = act
    return act_a, act_b
