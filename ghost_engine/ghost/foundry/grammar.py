"""Proposal engine (non-LLM): composes whole game concepts from mechanic atoms and mutates their STRUCTURE
(actions, variables, win conditions, reactive rules), not just constants. Lab-side (uses python random)."""
import copy, random
from . import dsl

# driver vars decide how you win; support vars create trade-offs
DRIVERS = {
    "hp":    {"init": (24, 50), "kind": "hp"},
    "pos":   {"init": (0, 0), "kind": "pos"},
    "score": {"init": (0, 0), "kind": "score"},
    "cash":  {"init": (5, 5), "kind": "score"},
}
SUPPORTS = {"energy": (2, 0, 6), "shield": (0, 0, 6), "heat": (0, 0, 10), "focus": (0, 0, 5), "fuel": (3, 0, 6)}
KIND_W = None   # set by the discovery loop from failure/success memory: {kind: weight}
ATOM_KINDS = ["hurt", "gain", "charge", "spend", "counter", "negate", "steal", "risk", "cool", "sabotage", "shield_up", "break"]


def V(w, n): return ["v", w, n]
def inc(w, n, e): return ["+=", w, n, e]
def when_opp(a, yes, no=0): return ["?", ["==", ["act", "opp"], a], yes, no]


def pick_kind(rnd):
    if KIND_W:
        return rnd.choices(ATOM_KINDS, weights=[KIND_W.get(k, 1.0) for k in ATOM_KINDS])[0]
    return rnd.choice(ATOM_KINDS)


def make_atom(rnd, kind, d, sups, n_actions):
    """Returns (cond, fx). d = driver var name, sups = support var names present."""
    S = rnd.choice(sups) if sups else None
    big = {"hp": (4, 12), "pos": (1, 4), "score": (2, 6), "cash": (2, 6)}.get(d, (1, 5))
    k = rnd.randint(*big)
    j = rnd.randrange(n_actions)
    if kind == "hurt":
        return 0, [inc("opp", d, -k)]
    if kind == "gain":
        return 0, [inc("me", d, max(1, k // 2))]
    if kind == "charge" and S:
        return 0, [inc("me", S, rnd.randint(1, 3))]
    if kind == "spend" and S:
        c = rnd.randint(1, 3)
        return [">=", V("me", S), c], [inc("me", S, -c), inc("me", d, k + c) if rnd.random() < .5 else inc("opp", d, -(k + c))]
    if kind == "counter":
        return 0, [inc("opp", d, when_opp(j, -k)), inc("me", d, when_opp(j, max(1, k // 2)))]
    if kind == "negate":
        return 0, [inc("me", d, when_opp(j, k)), inc("me", d, 1)]
    if kind == "steal":
        return 0, [inc("opp", d, -max(1, k // 2)), inc("me", d, max(1, k // 2))]
    if kind == "risk" and S:
        return 0, [inc("me", d, k + 1), inc("me", S, rnd.randint(1, 3))]
    if kind == "cool" and S:
        return 0, [inc("me", S, -rnd.randint(2, 3))]
    if kind == "sabotage" and S:
        return 0, [inc("opp", S, rnd.randint(1, 3))]
    if kind == "shield_up" and S:
        return 0, [inc("me", S, 2), inc("me", d, when_opp(j, k))]
    if kind == "break":
        return 0, [inc("opp", d, when_opp(j, -(k + 2), -1))]
    return 0, [inc("opp", d, -k)]


def end_rules(rnd, d, sups, goal):
    if d == "hp":
        e = [[["<=", V("opp", "hp"), 0], 1], [["<=", V("me", "hp"), 0], -1]]
    elif d == "pos":
        e = [[[">=", V("me", "pos"), goal], 1]]
    else:
        e = [[[">=", V("me", d), goal], 1]]
    if "heat" in sups and d != "hp" and rnd.random() < .8:
        e.insert(0, [[">=", V("me", "heat"), 10], -1])
    return e


def random_spec(rnd, uid):
    d = rnd.choice(list(DRIVERS))
    sups = rnd.sample(list(SUPPORTS), rnd.randint(1, 2))
    if d == "pos" and "fuel" not in sups and rnd.random() < .5:
        sups[0] = "fuel"
    vars_ = []
    if d == "hp":
        hp = rnd.randint(*DRIVERS["hp"]["init"]); vars_.append(["hp", hp, 0, hp])
        goal = 0
    else:
        goal = {"pos": rnd.randint(8, 16), "score": rnd.randint(12, 24), "cash": rnd.randint(14, 26)}[d]
        init = DRIVERS[d]["init"][0]
        vars_.append([d, init, 0, goal + 6])
    for s in sups:
        i, lo, hi = SUPPORTS[s]
        vars_.append([s, i, lo, hi])
    n = rnd.randint(3, 5)
    acts, kinds = [], []
    for ai in range(n):
        kind = pick_kind(rnd)
        cond, fx = make_atom(rnd, kind, d, sups, n)
        if rnd.random() < .35:
            k2 = pick_kind(rnd)
            c2, fx2 = make_atom(rnd, k2, d, sups, n)
            if c2 == 0 or cond == 0:
                fx = fx + fx2; cond = cond or c2; kind = kind + "+" + k2
        if ai == 0 and cond != 0:
            cond = 0
        acts.append({"name": f"{kind}{ai}", "cond": cond, "fx": fx}); kinds.append(kind)
    passive = []
    r = rnd.random()
    if r < .25 and "shield" in sups:
        passive.append(inc("me", "shield", -1))
    elif r < .45 and "heat" in sups:
        passive.append(inc("me", "heat", -1))
    elif r < .6:
        passive.append(inc("me", d, 1))
    elif r < .7 and d == "hp":
        passive.append(inc("me", "hp", -1)); passive.append(inc("opp", "hp", -1))
    value = [[d, 1]] + ([["heat", -1]] if "heat" in sups else [])
    spec = {"id": uid, "name": uid, "vars": vars_, "actions": acts, "passive": passive,
            "end": end_rules(rnd, d, sups, goal), "tiebreak": d, "max_rounds": rnd.randint(14, 30), "value": value}
    return spec, {"atoms": kinds, "driver": d}


# ------------------------------------------------------------------ structural signature (for novelty)
def signature(spec):
    tags = set()
    def walk(e):
        if isinstance(e, list) and e:
            if e[0] == "act":
                tags.add("reactive")
            if e[0] == "rnd":
                tags.add("random")
            if e[0] == "v":
                tags.add(f"reads:{e[1]}.{e[2]}")
            for x in e[1:]:
                walk(x)
    for a in spec["actions"]:
        if a["cond"] != 0:
            tags.add("gated_action"); walk(a["cond"])
        for f in a["fx"]:
            sign = "-" if (isinstance(f[3], int) and f[3] < 0) or (isinstance(f[3], list) and f[3][0] == "?" and isinstance(f[3][2], int) and f[3][2] < 0) else "+"
            tags.add(f"fx:{f[1]}.{f[2]}{sign}")
            walk(f[3])
    for f in spec["passive"]:
        tags.add(f"passive:{f[1]}.{f[2]}"); walk(f[3])
    for e, o in spec["end"]:
        tags.add(f"end:{o}:{e[0]}:{e[1][1] if e[1][0] == 'v' else ''}.{e[1][2] if e[1][0] == 'v' else ''}")
    for v in spec["vars"]:
        tags.add(f"var:{v[0]}")
    tags.add(f"n_actions:{len(spec['actions'])}")
    return tags


def distance(sa, sb):
    u = len(sa | sb)
    return 1 - len(sa & sb) / u if u else 0.0


# ------------------------------------------------------------------ mutation / crossover
def _literals(spec):
    """References to mutable int literals inside effects: (container, index)."""
    out = []
    def walk(e, parent, idx):
        if isinstance(e, int) and parent is not None:
            out.append((parent, idx))
        elif isinstance(e, list) and e and e[0] not in ("v", "act", "round", "rnd"):
            for i in range(1, len(e)):
                walk(e[i], e, i)
    for a in spec["actions"]:
        for f in a["fx"]:
            walk(f[3], f, 3)
    return out


def mutate(spec, meta, rnd, uid):
    s = copy.deepcopy(spec)
    m = copy.deepcopy(meta)
    names = [v[0] for v in s["vars"]]
    d = m.get("driver") or s["vars"][0][0]
    sups = [x for x in names if x != d]
    ops = ["tweak", "tweak", "swap_atom", "add_action", "drop_action", "goal", "passive", "add_var", "reactive_target"]
    op = rnd.choice(ops)
    n = len(s["actions"])
    if op == "tweak":
        lits = _literals(s)
        if lits:
            c, i = rnd.choice(lits)
            c[i] = c[i] + rnd.choice((-3, -2, -1, 1, 2, 3)) if c[i] != 0 else rnd.choice((-1, 1))
    elif op == "swap_atom" and n:
        ai = rnd.randrange(n)
        kind = pick_kind(rnd)
        cond, fx = make_atom(rnd, kind, d, sups, n)
        if ai == 0:
            cond = 0
        s["actions"][ai] = {"name": f"{kind}{ai}", "cond": cond, "fx": fx}
        if ai < len(m.get("atoms", [])):
            m["atoms"][ai] = kind
    elif op == "add_action" and n < dsl.MAX_ACTIONS:
        kind = pick_kind(rnd)
        cond, fx = make_atom(rnd, kind, d, sups, n + 1)
        s["actions"].append({"name": f"{kind}{n}", "cond": cond, "fx": fx})
        m.setdefault("atoms", []).append(kind)
    elif op == "drop_action" and n > 3:
        ai = rnd.randrange(1, n)
        del s["actions"][ai]
        if ai < len(m.get("atoms", [])):
            del m["atoms"][ai]
        _fix_act_refs(s)
    elif op == "goal":
        for e, o in s["end"]:
            if e[0] == ">=" and isinstance(e[2], int):
                e[2] = max(3, e[2] + rnd.choice((-3, -2, 2, 3)))
        s["max_rounds"] = max(8, min(40, s["max_rounds"] + rnd.choice((-4, 4))))
    elif op == "passive":
        if s["passive"]:
            s["passive"] = []
        else:
            tgt = rnd.choice(names)
            s["passive"] = [inc(rnd.choice(("me", "opp")), tgt, rnd.choice((-1, 1)))]
    elif op == "add_var":
        cands = [x for x in SUPPORTS if x not in names]
        if cands:
            x = rnd.choice(cands)
            i, lo, hi = SUPPORTS[x]
            s["vars"].append([x, i, lo, hi])
            sups.append(x)
            ai = rnd.randrange(1, n)
            cond, fx = make_atom(rnd, rnd.choice(("charge", "spend", "risk", "sabotage")), d, [x], n)
            s["actions"][ai] = {"name": f"{x}_play{ai}", "cond": cond, "fx": fx}
    elif op == "reactive_target":
        def retarget(e):
            if isinstance(e, list) and e:
                if e[0] == "==" and isinstance(e[1], list) and e[1][0] == "act" and isinstance(e[2], int):
                    e[2] = rnd.randrange(len(s["actions"]))
                for x in e[1:]:
                    retarget(x)
        for a in s["actions"]:
            for f in a["fx"]:
                retarget(f[3])
    s["id"] = uid; s["name"] = uid
    m["op"] = op
    return s, m


def _fix_act_refs(s):
    n = len(s["actions"])
    def fix(e):
        if isinstance(e, list) and e:
            if e[0] == "==" and isinstance(e[1], list) and e[1][0] == "act" and isinstance(e[2], int) and e[2] >= n:
                e[2] = n - 1
            for x in e[1:]:
                fix(x)
    for a in s["actions"]:
        for f in a["fx"]:
            fix(f[3])


def crossover(sa, ma, sb, mb, rnd, uid):
    """Child = A's vars/goal with a random subset of B's actions grafted in; B's vars added where needed."""
    s = copy.deepcopy(sa)
    m = copy.deepcopy(ma)
    have = {v[0] for v in s["vars"]}
    k = rnd.randint(1, max(1, len(sb["actions"]) - 1))
    graft = rnd.sample(range(1, len(sb["actions"])), min(k, len(sb["actions"]) - 1)) if len(sb["actions"]) > 1 else []
    for gi in graft:
        a = copy.deepcopy(sb["actions"][gi])
        used = set()
        def refs(e):
            if isinstance(e, list) and e:
                if e[0] == "v":
                    used.add(e[2])
                for x in e[1:]:
                    refs(x)
        refs(a["cond"])
        for f in a["fx"]:
            used.add(f[2]); refs(f[3])
        if not used <= have:
            # only graft if every variable it needs exists in the child (adding B's support vars when it can)
            for u in used - have:
                vd = [v for v in sb["vars"] if v[0] == u]
                if vd and u in SUPPORTS:
                    s["vars"].append(copy.deepcopy(vd[0])); have.add(u)
            if not used <= have:
                continue
        if len(s["actions"]) < dsl.MAX_ACTIONS:
            s["actions"].append(a)
            m.setdefault("atoms", []).append(mb.get("atoms", ["?"] * 9)[gi] if gi < len(mb.get("atoms", [])) else "?")
    _fix_act_refs(s)
    s["id"] = uid; s["name"] = uid
    m["op"] = "crossover"
    return s, m
