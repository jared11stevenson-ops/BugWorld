"""Persistent headless RPG world. State is a single JSON-able dict `s`; every function is
(s, ...) -> mutate. Integer math + fixed iteration order => deterministic and portable to GDScript."""
from . import rng as R, combat as C, policies as P
from .rules import clone

(EV_TRAVEL, EV_FIGHT, EV_KILL, EV_BUY, EV_SELL, EV_WAR, EV_PEACE,
 EV_SPAWN, EV_INTERVENE, EV_POTION) = range(10)
EV_NAMES = ["travel", "fight", "kill", "buy", "sell", "war", "peace", "spawn", "intervene", "potion"]
# fight event c = rounds*10 + outcome
OUT_TIMEOUT, OUT_A_KILLED_B, OUT_B_KILLED_A, OUT_BOTH_DIED, OUT_A_FLED, OUT_B_FLED = range(6)

TOWN_NAMES = ["Oakhaven", "Stonebridge", "Mirefall", "Highmark", "Saltreach", "Emberdell", "Greywatch", "Thornwick"]
FACTION_NAMES = ["Crown", "Guild", "Wilds", "Order"]
FIRST = ["Ash", "Bram", "Cora", "Dov", "Elda", "Fenn", "Gale", "Hob"]
LAST = ["Vale", "Thorn", "Reed", "Marsh", "Crow", "Stone", "Wick", "Ford"]


def npc_name(n):
    return FIRST[n["na"]] + " " + LAST[n["nb"]]


# ---------------------------------------------------------------- construction
def new_world(seed, rules, n_npcs=24, n_towns=6, n_fac=3):
    s = {"seed": seed & 0x7FFFFFFF, "tick": 0, "rng": R.seed_state(seed), "rules": clone(rules),
         "n_fac": n_fac, "towns": [], "adj": [], "rel": [], "war": [], "npcs": [], "pending": [],
         "events": [], "ev_hash": R.FNV_OFFSET, "minted": 0, "burned": 0, "gold0": 0}
    cap = rules["economy"]["stock_cap"]
    for i in range(n_towns):
        s["towns"].append({"id": i, "treasury": 100, "stock": cap // 2})
        s["adj"].append([])
    for i in range(n_towns):
        _link(s, i, (i + 1) % n_towns)
    for i in range(0, n_towns, 3):
        _link(s, i, (i + n_towns // 2) % n_towns)
    for i in range(n_fac):
        s["rel"].append([0] * n_fac)
        s["war"].append([0] * n_fac)
    for i in range(n_fac):
        s["rel"][i][i] = 100
    for i in range(n_fac):
        for j in range(i + 1, n_fac):
            v = R.rand(s, 61) - 30
            s["rel"][i][j] = v
            s["rel"][j][i] = v
    for i in range(n_npcs):
        f = i % n_fac
        loc = (_home(s, f) + R.rand(s, 2)) % n_towns
        gold = 20 + R.rand(s, 31)
        _make_npc(s, f, loc, gold)
    s["gold0"] = total_gold(s)
    return s


def _link(s, a, b):
    if a != b and b not in s["adj"][a]:
        s["adj"][a].append(b)
        s["adj"][b].append(a)


def _home(s, f):
    nt = len(s["towns"])
    return (f * (nt // s["n_fac"])) % nt


def _make_npc(s, faction, loc, gold):
    nid = len(s["npcs"])
    n = {"id": nid, "faction": faction, "loc": loc, "gold": gold}
    n["maxhp"] = 80 + R.rand(s, 41)
    n["atk"] = 12 + R.rand(s, 13)
    n["def"] = 2 + R.rand(s, 6)
    n["potions"] = R.rand(s, 4)
    n["policy"] = R.rand(s, P.NUM)
    n["na"] = R.rand(s, 8)
    n["nb"] = R.rand(s, 8)
    n["hp"] = n["maxhp"]
    n["alive"] = 1
    n["trader"] = 1 if nid % 4 == 3 else 0
    n["kills"] = 0
    n["basis"] = 0
    n["born"] = s["tick"]
    n["aff"] = []
    C.reset(n)
    s["npcs"].append(n)
    return n


# ---------------------------------------------------------------- helpers
def emit(s, etype, a=-1, b=-1, c=0, cause=-1):
    eid = len(s["events"])
    ev = [eid, s["tick"], etype, a, b, c, cause]
    s["events"].append(ev)
    s["ev_hash"] = R.fnv32_ints(s["ev_hash"], ev)
    return eid


def total_gold(s):
    t = 0
    for n in s["npcs"]:
        t += n["gold"]
    for tw in s["towns"]:
        t += tw["treasury"]
    for p in s["pending"]:
        t += p[2]
    return t


def conservation_error(s):
    """Gold ledger: supply must equal initial + minted - burned. Non-zero => an exploit/bug."""
    return total_gold(s) - (s["gold0"] + s["minted"] - s["burned"])


def price(s, town):
    e = s["rules"]["economy"]
    pct = max(20, 100 + e["swing_pct"] * (e["stock_cap"] // 2 - town["stock"]))
    return max(1, e["base_price"] * pct // 100)


def get_aff(n, other):
    for e in n["aff"]:
        if e[0] == other:
            return e[1]
    return 0


def add_aff(n, other, delta, cause):
    for e in n["aff"]:
        if e[0] == other:
            e[1] = max(-100, min(100, e[1] + delta))
            if delta < 0:
                e[2] = cause
            return
    n["aff"].append([other, max(-100, min(100, delta)), cause if delta < 0 else -1])


def change_rel(s, f, g, delta, cause):
    v = max(-100, min(100, s["rel"][f][g] + delta))
    s["rel"][f][g] = v
    s["rel"][g][f] = v
    thr = s["rules"]["world"]["war_threshold"]
    if v < thr and s["war"][f][g] == 0:
        s["war"][f][g] = 1
        s["war"][g][f] = 1
        emit(s, EV_WAR, f, g, v, cause)
    elif v > thr + 25 and s["war"][f][g] == 1:
        s["war"][f][g] = 0
        s["war"][g][f] = 0
        emit(s, EV_PEACE, f, g, v, cause)


# ---------------------------------------------------------------- death / combat
def die(s, vid, killer, cause):
    w = s["rules"]["world"]
    v = s["npcs"][vid]
    v["alive"] = 0
    v["hp"] = 0
    if killer >= 0:
        k = s["npcs"][killer]
        loot = v["gold"] * w["loot_pct"] // 100
        v["gold"] -= loot
        k["gold"] += loot
        k["kills"] += 1
    rem = v["gold"]
    v["gold"] = 0
    kid = emit(s, EV_KILL, killer, vid, v["loc"], cause)
    s["pending"].append([s["tick"] + w["respawn_delay"], v["faction"], rem, vid, kid])
    if killer >= 0:
        k = s["npcs"][killer]
        add_aff(v, killer, -50, kid)
        for o in s["npcs"]:
            if o["alive"] and o["id"] != killer and o["id"] != vid and o["loc"] == v["loc"] and o["faction"] == v["faction"]:
                add_aff(o, killer, -15, kid)
        if k["faction"] != v["faction"]:
            change_rel(s, k["faction"], v["faction"], -w["kill_rel_penalty"], kid)
    return kid


def fight(s, i, t, cause):
    c = s["rules"]["combat"]
    w = s["rules"]["world"]
    a = s["npcs"][i]
    b = s["npcs"][t]
    C.reset(a)
    C.reset(b)
    ha = P.new_hist()
    hb = P.new_hist()
    rounds = 0
    fled = 0
    while a["hp"] > 0 and b["hp"] > 0 and rounds < c["round_cap"]:
        xa = P.choose(a["policy"], a, b, ha, c, s)
        xb = P.choose(b["policy"], b, a, hb, c, s)
        xa, xb = C.fight_round(c, a, b, xa, xb, s)
        rounds += 1
        P.observe(ha, xb)
        P.observe(hb, xa)
        if a["hp"] > 0 and b["hp"] > 0:
            if a["hp"] * 100 < 20 * a["maxhp"] and R.rand(s, 100) < w["flee_pct"]:
                fled = 1
            elif b["hp"] * 100 < 20 * b["maxhp"] and R.rand(s, 100) < w["flee_pct"]:
                fled = 2
            if fled:
                break
    if a["hp"] <= 0 and b["hp"] <= 0:
        out = OUT_BOTH_DIED
    elif b["hp"] <= 0:
        out = OUT_A_KILLED_B
    elif a["hp"] <= 0:
        out = OUT_B_KILLED_A
    elif fled == 1:
        out = OUT_A_FLED
    elif fled == 2:
        out = OUT_B_FLED
    else:
        out = OUT_TIMEOUT
    fid = emit(s, EV_FIGHT, i, t, rounds * 10 + out, cause)
    if out == OUT_A_KILLED_B:
        die(s, t, i, fid)
    elif out == OUT_B_KILLED_A:
        die(s, i, t, fid)
    elif out == OUT_BOTH_DIED:
        die(s, i, -1, fid)
        die(s, t, -1, fid)
    else:
        add_aff(a, t, -10, fid)
        add_aff(b, i, -10, fid)


# ---------------------------------------------------------------- npc behaviour
def _work(s, n):
    e = s["rules"]["economy"]
    tax = e["wage"] * e["tax_pct"] // 100
    n["gold"] += e["wage"] - tax
    s["towns"][n["loc"]]["treasury"] += tax
    s["minted"] += e["wage"]


def _buy(s, n, town):
    p = price(s, town)
    n["gold"] -= p
    town["treasury"] += p
    town["stock"] -= 1
    n["potions"] += 1
    n["basis"] += p
    emit(s, EV_BUY, n["id"], n["loc"], p)


def npc_turn(s, n):
    r = s["rules"]
    c = r["combat"]
    e = r["economy"]
    w = r["world"]
    town = s["towns"][n["loc"]]
    n["hp"] = min(n["maxhp"], n["hp"] + max(1, n["maxhp"] // w["regen_div"]))
    if s["tick"] % e["upkeep_every"] == 0 and n["gold"] >= e["upkeep"]:
        n["gold"] -= e["upkeep"]
        town["treasury"] += e["upkeep"]
    if n["hp"] * 100 < 40 * n["maxhp"] and n["potions"] > 0:
        n["hp"] = min(n["maxhp"], n["hp"] + c["potion_heal"])
        n["potions"] -= 1
        if n["potions"] == 0:
            n["basis"] = 0
        emit(s, EV_POTION, n["id"])
        return
    p = price(s, town)
    if n["trader"]:
        if n["potions"] > 0:
            sp = p * e["sell_pct"] // 100
            avg = n["basis"] // n["potions"]
            if sp > avg and town["treasury"] >= sp:
                town["treasury"] -= sp
                n["gold"] += sp
                town["stock"] = min(e["stock_cap"], town["stock"] + 1)
                n["basis"] -= avg
                n["potions"] -= 1
                emit(s, EV_SELL, n["id"], n["loc"], sp)
                return
        if town["stock"] > 0 and n["potions"] < 6 and n["gold"] >= p and p <= e["base_price"]:
            _buy(s, n, town)
            return
    elif n["hp"] * 100 < 60 * n["maxhp"] and n["potions"] < 3 and town["stock"] > 0 and n["gold"] >= p:
        _buy(s, n, town)
        return
    roll = R.rand(s, 100)
    if roll < 35:
        nb = s["adj"][n["loc"]]
        dest = nb[R.rand(s, len(nb))]
        n["loc"] = dest
        emit(s, EV_TRAVEL, n["id"], dest)
    elif roll < 60:
        others = []
        for o in s["npcs"]:
            if o["alive"] and o["id"] != n["id"] and o["loc"] == n["loc"]:
                others.append(o["id"])
        if len(others) == 0:
            _work(s, n)
            return
        t = others[R.rand(s, len(others))]
        o = s["npcs"][t]
        aggro = 0
        cause = -1
        if n["faction"] != o["faction"]:
            rel = s["rel"][n["faction"]][o["faction"]]
            aggro = w["aggro_pct"]
            if rel < 0:
                aggro += -rel // 4
            if s["war"][n["faction"]][o["faction"]]:
                aggro += 10
        else:
            for ent in n["aff"]:
                if ent[0] == t and ent[1] <= -40:
                    aggro = 30
                    cause = ent[2]
        aggro = min(95, aggro)
        if R.rand(s, 100) < aggro:
            fight(s, n["id"], t, cause)
        else:
            add_aff(n, t, 1, -1)
            add_aff(o, n["id"], 1, -1)
    else:
        _work(s, n)


def tick(s):
    s["tick"] += 1
    e = s["rules"]["economy"]
    if s["tick"] % e["restock_ticks"] == 0:
        for tw in s["towns"]:
            tw["stock"] = min(e["stock_cap"], tw["stock"] + 1)
    if s["tick"] % 10 == 0:
        for f in range(s["n_fac"]):
            for g in range(f + 1, s["n_fac"]):
                if s["rel"][f][g] < 0:
                    change_rel(s, f, g, 1, -1)
    keep = []
    for p in s["pending"]:
        if p[0] <= s["tick"]:
            loc = (_home(s, p[1]) + R.rand(s, 2)) % len(s["towns"])
            n = _make_npc(s, p[1], loc, p[2])
            emit(s, EV_SPAWN, n["id"], p[1], p[3], p[4])
        else:
            keep.append(p)
    s["pending"] = keep
    count = len(s["npcs"])
    for i in range(count):
        n = s["npcs"][i]
        if n["alive"]:
            npc_turn(s, n)
    for tw in s["towns"]:
        b = min(e["burn"], tw["treasury"])
        tw["treasury"] -= b
        s["burned"] += b


def run(s, ticks):
    for _ in range(ticks):
        tick(s)


# ---------------------------------------------------------------- interventions (experimental rule/world changes)
def apply_intervention(s, iv):
    kind = iv["kind"]
    a = iv.get("args", [])
    if kind == "kill":
        eid = emit(s, EV_INTERVENE, 0, a[0], 0)
        if s["npcs"][a[0]]["alive"]:
            die(s, a[0], -1, eid)
    elif kind == "give_gold":
        emit(s, EV_INTERVENE, 1, a[0], a[1])
        s["npcs"][a[0]]["gold"] += a[1]
        s["minted"] += a[1]
    elif kind == "set_rel":
        eid = emit(s, EV_INTERVENE, 2, a[0], a[2])
        change_rel(s, a[0], a[1], a[2] - s["rel"][a[0]][a[1]], eid)
    elif kind == "set_rule":
        sec, key = iv["path"].split(".")
        s["rules"][sec][key] = a[0]
        emit(s, EV_INTERVENE, 3, a[0], 0)
    else:
        raise ValueError("unknown intervention " + kind)


# ---------------------------------------------------------------- queries: history & consequences
def history(s, nid):
    out = []
    for ev in s["events"]:
        t = ev[2]
        if t in (EV_TRAVEL, EV_BUY, EV_SELL, EV_POTION, EV_SPAWN) and ev[3] == nid:
            out.append(ev)
        elif t in (EV_FIGHT, EV_KILL) and (ev[3] == nid or ev[4] == nid):
            out.append(ev)
    return out


def consequences(s, event_id):
    """All events transitively caused by event_id (kill -> war -> grudge fights -> kills ...)."""
    seen = {event_id}
    out = []
    for ev in s["events"]:
        if ev[6] in seen:
            seen.add(ev[0])
            out.append(ev)
    return out


def describe(s, ev):
    t = ev[2]
    nm = lambda i: npc_name(s["npcs"][i]) + f"#{i}" if 0 <= i < len(s["npcs"]) else "(nature)"
    if t == EV_TRAVEL:
        return f"[{ev[1]}] {nm(ev[3])} travels to {TOWN_NAMES[ev[4]]}"
    if t == EV_FIGHT:
        return f"[{ev[1]}] {nm(ev[3])} fights {nm(ev[4])} ({ev[5] // 10} rounds)"
    if t == EV_KILL:
        return f"[{ev[1]}] {nm(ev[4])} is killed by {nm(ev[3])} in {TOWN_NAMES[ev[5]]}"
    if t == EV_BUY:
        return f"[{ev[1]}] {nm(ev[3])} buys a potion for {ev[5]}g"
    if t == EV_SELL:
        return f"[{ev[1]}] {nm(ev[3])} sells a potion for {ev[5]}g"
    if t == EV_WAR:
        return f"[{ev[1]}] WAR: {FACTION_NAMES[ev[3]]} vs {FACTION_NAMES[ev[4]]}"
    if t == EV_PEACE:
        return f"[{ev[1]}] PEACE: {FACTION_NAMES[ev[3]]} and {FACTION_NAMES[ev[4]]}"
    if t == EV_SPAWN:
        return f"[{ev[1]}] {nm(ev[3])} arrives as heir of #{ev[5]}"
    if t == EV_POTION:
        return f"[{ev[1]}] {nm(ev[3])} drinks a potion"
    kinds = ["killed", "gave gold to", "forced relations of", "changed a rule:"]
    return f"[{ev[1]}] GOD-MODE: {kinds[ev[3]]} {'#' + str(ev[4]) if ev[3] < 2 else ev[4]} ({ev[5]})"


# ---------------------------------------------------------------- digest (cross-engine parity)
def digest(s):
    parts = [s["tick"], s["rng"], s["minted"], s["burned"], len(s["events"]), s["ev_hash"]]
    for sec in ("combat", "economy", "world"):
        d = s["rules"][sec]
        for k in sorted(d.keys()):
            parts.append(d[k])
    for tw in s["towns"]:
        parts += [tw["treasury"], tw["stock"]]
    for row in s["rel"]:
        parts += row
    for row in s["war"]:
        parts += row
    for n in s["npcs"]:
        parts += [n["id"], n["faction"], n["loc"], n["hp"], n["maxhp"], n["atk"], n["def"], n["gold"],
                  n["potions"], n["alive"], n["policy"], n["kills"], n["basis"], len(n["aff"])]
        for e in n["aff"]:
            parts += e
    for p in s["pending"]:
        parts += p
    return R.fnv32_str(",".join(str(x) for x in parts))


def digest_hex(s):
    return "%08x" % digest(s)
