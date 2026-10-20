"""Universe generation: combine inspirations into ONE fictional universe, then explore its possible worlds and histories
(evolutionary search over world rules + branching alternate histories) and pick a canon history with measured causal richness."""
import colorsys, copy, json, os, random, statistics
from concurrent.futures import ProcessPoolExecutor
from ghost.kernel import rules as RU, world as W
from ghost.kernel.timeline import Timeline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TAG_LAW = {"gust": {"rally", "projectile"}, "slick": {"splash"}, "contagion": {"contagion", "quarantine"}, "purge": {"purge"}, "pulse": {"oscillation", "resonance", "signal"}, "wells": {"predation", "network", "symbiosis", "tipping"},
           "drift": {"diffusion", "migration", "erosion", "entropy", "scarcity", "feedback", "selection"}}
LAW_TEXT = {"gust": "The air here is never still. Gusts rise without warning and carry everything that flies; the clever play the wind rather than fight it.",
            "slick": "Everything is wet, and wet things slide. Footing is a rumor here; momentum is the only honest thing you own.",
            "contagion": "A sickness walks this land. It blooms where people gather, swells while it is ignored, and only a remedy, never courage, makes it recede.",
            "purge": "A cleansing line sweeps the world on a fixed cadence. Fire does not ask who is guilty; there is a narrow gap, and the wise learn where it opens.",
            "pulse": "Everything in this universe beats with a rhythm; periodic waves sweep across the land and punish those who ignore the beat.",
            "wells": "Mass bends the world here; heavy places pull wanderers toward them whether they wish it or not.",
            "drift": "A restless current runs through all things; nothing stays where it was put, and standing still is a choice with a price."}
# tag -> shift of world-rule priors used to seed the search (genome centre)
TAG_PRIOR = {"projectile": {"aggro_pct": +1}, "splash": {"loot_pct": -10, "flee_pct": +10}, "rally": {"aggro_pct": +1, "flee_pct": -10}, "team": {"kill_rel_penalty": +1},
             "contagion": {"aggro_pct": -1, "flee_pct": +10, "regen_div": +5}, "purge": {"aggro_pct": +2, "loot_pct": +10, "respawn_delay": +5},
             "quarantine": {"flee_pct": -10, "respawn_delay": +5},"predation": {"aggro_pct": +3, "loot_pct": +20}, "symbiosis": {"aggro_pct": -2, "kill_rel_penalty": +2},
             "scarcity": {"wage": -1, "burn": +1, "restock_ticks": +3}, "entropy": {"burn": +1, "regen_div": +10},
             "feedback": {"kill_rel_penalty": +3}, "migration": {"respawn_delay": -6}, "erosion": {"regen_div": +8},
             "network": {"flee_pct": +10}, "selection": {"aggro_pct": +1}, "tipping": {"kill_rel_penalty": +2}}
TAG_ATOMS = {"projectile": ["hurt", "counter"], "splash": ["hurt", "break"], "rally": ["counter", "negate"], "team": ["shield_up", "gain"], "contagion": ["sabotage", "charge", "risk"], "purge": ["hurt", "break", "cool"], "quarantine": ["shield_up", "cool", "negate"], "predation": ["hurt", "steal", "break"], "symbiosis": ["gain", "negate", "shield_up"], "scarcity": ["spend", "charge", "cool"],
             "feedback": ["counter", "negate", "break"], "entropy": ["cool", "sabotage"], "resonance": ["counter", "negate"],
             "oscillation": ["counter", "break"], "network": ["sabotage", "steal"], "selection": ["risk"], "tipping": ["risk", "spend"],
             "diffusion": ["charge", "gain"], "signal": ["counter", "negate"], "erosion": ["break", "sabotage"], "migration": ["gain", "charge"]}
SUFFIX_F = ["Concord", "Host", "Choir", "Covenant", "Syndicate", "Assembly", "Lineage", "Compact"]
SUFFIX_T = ["reach", "hollow", "mark", "fall", "gate", "ward", "ford", "spire"]
CURRENCY = ["marks", "shards", "tallies", "beads", "chits", "scrip"]
POTION = ["draught", "tonic", "philter", "salve", "elixir"]


def cap(w):
    return w[:1].upper() + w[1:]


def _lum(hexc):
    c = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _shift(hexc, f):
    """f>0 lightens toward white, f<0 darkens toward black."""
    c = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    c = [int(x + (255 - x) * f) if f > 0 else int(x * (1 + f)) for x in c]
    return "#%02x%02x%02x" % tuple(max(0, min(255, x)) for x in c)


def ensure_contrast(pal):
    """Accessibility/polish guarantee: text (pal[4]) >= 7:1 and accent (pal[3]) >= 4.5:1 against the background (pal[0]); pal[2] >= 3:1."""
    pal = list(pal)
    for idx, need in ((4, 7.0), (3, 4.5), (2, 3.0)):
        n = 0
        while contrast(pal[idx], pal[0]) < need and n < 40:
            pal[idx] = _shift(pal[idx], 0.08); n += 1
        if contrast(pal[idx], pal[0]) < need:      # still short (very light bg): darken the background instead
            m = 0
            while contrast(pal[idx], pal[0]) < need and m < 40:
                pal[0] = _shift(pal[0], -0.1); m += 1
    return pal


def make_universe(inspirations, seed):
    rnd = random.Random(seed * 7 + 1)
    tags = {}
    for b in inspirations:
        for t in b[2]:
            tags[t] = tags.get(t, 0) + 1
    motifs = [w for b in inspirations for w in b[3]]
    rnd.shuffle(motifs)
    uname = cap(motifs[0].replace("-", "")) + motifs[1].replace("-", "")
    law = max(TAG_LAW, key=lambda l: (sum(tags.get(t, 0) for t in TAG_LAW[l]) * (2 if l in ("contagion", "purge", "gust", "slick") else 1), l))   # theme-defining laws weigh double
    hue = (sum(ord(c) for c in uname) % 360) / 360.0
    pal = []
    for i, (s, v) in enumerate([(0.55, 0.16), (0.5, 0.30), (0.6, 0.85), (0.75, 0.95), (0.35, 0.95)]):
        r, g, b_ = colorsys.hsv_to_rgb((hue + (0.0, 0.04, 0.5, 0.08, 0.12)[i]) % 1.0, s, v)
        pal.append("#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b_ * 255)))
    pal = ensure_contrast(pal)
    fac = [f"The {cap(motifs[i + 2].replace('-', ''))} {rnd.choice(SUFFIX_F)}" for i in range(3)]
    towns = []
    for m in motifs[:6]:
        for _ in range(20):                                   # unique town names
            nm = cap(m.replace("-", "")) + rnd.choice(SUFFIX_T)
            if nm not in towns:
                break
        towns.append(nm)
    from . import elements as EL
    elements, sources = [], {}
    for b in inspirations:
        for e in EL.entry_elements(b):
            sources.setdefault(e, []).append(b[0])
            if e not in elements:
                elements.append(e)
    law_element = {"gust": "wind", "slick": "slick", "contagion": "contagion", "purge": "purge", "pulse": "pulse", "wells": "wells", "drift": "drift"}.get(law)
    if law_element and law_element not in elements:
        elements.append(law_element); sources[law_element] = ["the law of the universe"]
    uni = {"id": f"{uname.lower()}-{seed}", "elements": elements, "element_sources": sources, "physics": EL.universe_physics(elements),
           "laws": [{"element": e, "text": EL.ELEMENTS[e]["law"]} for e in elements], "seed": seed, "name": uname, "inspirations": [b[0] for b in inspirations],
           "facts": {b[0]: b[4] for b in inspirations}, "fields": [b[1] for b in inspirations], "tags": tags, "law": law,
           "law_text": LAW_TEXT[law], "palette": pal,
           "mood": {"gust": "bright", "slick": "bright", "contagion": "dread", "purge": "tense", "wells": "tense", "pulse": "calm", "drift": "calm"}[law],
           "lexicon": {"factions": fac, "towns": towns, "currency": rnd.choice(CURRENCY), "potion": rnd.choice(POTION), "motifs": motifs}}
    return uni


def prior_rules(uni, knowledge=None):
    r = RU.clone(json.load(open(os.path.join(ROOT, "rulesets", "v1_evolved.json"))))
    r["name"] = uni["id"]
    for t, n in uni["tags"].items():
        for k, d in TAG_PRIOR.get(t, {}).items():
            sec = next(s for (s, k2) in BOUNDS if k2 == k)
            r[sec][k] = r[sec][k] + d * n
    if knowledge and knowledge.get("universe_priors"):       # validated improvement from earlier cycles
        for k, v in knowledge["universe_priors"].items():
            sec = next((s for (s, k2) in BOUNDS if k2 == k), None)
            if sec:
                r[sec][k] = int(round((r[sec][k] + v) / 2))
    return clamp(r)


BOUNDS = {("world", "aggro_pct"): (1, 10, 1), ("world", "kill_rel_penalty"): (2, 12, 1), ("world", "loot_pct"): (0, 100, 10),
          ("world", "flee_pct"): (10, 90, 10), ("world", "respawn_delay"): (5, 40, 5), ("world", "regen_div"): (10, 50, 5),
          ("economy", "wage"): (1, 4, 1), ("economy", "burn"): (1, 5, 1), ("economy", "sell_pct"): (50, 85, 5),
          ("economy", "swing_pct"): (5, 30, 5), ("economy", "restock_ticks"): (3, 12, 1)}


def clamp(r):
    for (sec, k), (lo, hi, _s) in BOUNDS.items():
        r[sec][k] = max(lo, min(hi, int(r[sec][k])))
    return r


# ---------------------------------------------------------------- history richness (measured, not narrated)
def chain_depth(s):
    depth = {}
    best = 0
    for ev in s["events"]:
        d = depth.get(ev[6], 0) + 1 if ev[6] >= 0 else 0
        depth[ev[0]] = d
        best = max(best, d)
    return best


def richness(s):
    ev = s["events"]
    kills = sum(1 for e in ev if e[2] == W.EV_KILL)
    wars = sum(1 for e in ev if e[2] == W.EV_WAR)
    peaces = sum(1 for e in ev if e[2] == W.EV_PEACE)
    alive = sum(n["alive"] for n in s["npcs"])
    kinds = len({e[2] for e in ev})
    depth = chain_depth(s)
    gold = [n["gold"] for n in s["npcs"] if n["alive"]]
    tot = sum(gold) or 1
    gini = sum((2 * (i + 1) - len(gold) - 1) * x for i, x in enumerate(sorted(gold))) / (len(gold) * tot) if gold else 1
    deaths = [0] * s["n_fac"]
    for e in ev:
        if e[2] == W.EV_KILL:
            deaths[s["npcs"][e[4]]["faction"]] += 1
    mean = sum(deaths) / len(deaths)
    balance = 1 - min(1.0, (statistics.pstdev(deaths) / mean) if mean else 1.0)
    parts = {"kills": 1.0 if 25 <= kills <= 110 else max(0.0, 1 - min(abs(kills - 25), abs(kills - 110)) / 60),
             "war_and_peace": (0.5 if wars else 0) + (0.5 if peaces else 0), "alive": min(1.0, alive / 18),
             "diversity": min(1.0, kinds / 9), "chain": min(1.0, depth / 6),
             "equality": 1.0 if 0.25 <= gini <= 0.6 else max(0.0, 1 - min(abs(gini - 0.25), abs(gini - 0.6)) / 0.3), "balance": balance}
    w = {"kills": 1, "war_and_peace": 1.5, "alive": 1, "diversity": 0.5, "chain": 1.5, "equality": 0.5, "balance": 1}
    return sum(w[k] * parts[k] for k in w) / sum(w.values()), parts


def _eval(args):
    rules, seeds, ticks = args
    fs = []
    for sd in seeds:
        s = W.new_world(sd, rules)
        W.run(s, ticks)
        fs.append(richness(s)[0])
    return statistics.mean(fs)


def mutate(r, rnd, rate=0.35):
    r = copy.deepcopy(r)
    for (sec, k), (lo, hi, st) in BOUNDS.items():
        if rnd.random() < rate:
            r[sec][k] = r[sec][k] + st * rnd.choice((-2, -1, 1, 2))
    return clamp(r)


def explore(uni, knowledge=None, pop=16, gens=12, seeds=(1, 2, 3), ticks=600, workers=4, log=print):
    """Evolutionary search over world rules, then branching histories. Returns the universe with rules, canon history, chronicle."""
    rnd = random.Random(uni["seed"] * 13 + 5)
    center = prior_rules(uni, knowledge)
    popn = [center] + [mutate(center, rnd, 0.6) for _ in range(pop - 1)]
    curve = []
    cache = {}
    with ProcessPoolExecutor(workers) as ex:
        for g in range(gens + 1):
            keys = [json.dumps(p, sort_keys=True) for p in popn]
            todo = [(k, p) for k, p in zip(keys, popn) if k not in cache]
            for (k, _), f in zip(todo, ex.map(_eval, [(p, seeds, ticks) for _, p in todo])):
                cache[k] = f
            ranked = sorted(zip(keys, popn), key=lambda kp: -cache[kp[0]])
            curve.append({"gen": g, "best": cache[ranked[0][0]], "mean": statistics.mean(cache[k] for k, _ in ranked)})
            log(f"  search gen {g:2d} best {curve[-1]['best']:.3f} mean {curve[-1]['mean']:.3f}")
            if g == gens:
                break
            elite = [p for _, p in ranked[:4]]
            popn = list(elite)
            while len(popn) < pop:
                a, b = rnd.sample(elite, 2)
                c = copy.deepcopy(a)
                for (sec, k) in BOUNDS:
                    if rnd.random() < 0.5:
                        c[sec][k] = b[sec][k]
                popn.append(mutate(c, rnd))
    best = ranked[0][1]
    uni["rules"] = best
    uni["search"] = {"generations": gens, "population": pop, "seeds": list(seeds), "ticks": ticks, "curve": curve,
                     "start_fitness": curve[0]["best"], "final_fitness": curve[-1]["best"], "evaluations": len(cache)}
    uni["canon"] = choose_canon(best, uni, rnd, log)
    uni["chronicle"], uni["pivotal"] = chronicle(uni)
    return uni


def choose_canon(rules, uni, rnd, log):
    """Branching histories: from several seeds, fork at ticks and apply random interventions; keep the richest timeline as canon."""
    options = []
    for sd in range(101, 107):
        base = Timeline(W.new_world(sd, rules))
        base.step(100)
        for t0 in (100, 200, 300):
            if base.tick < t0:
                base.step(t0 - base.tick)
            branches = [("none", None)] + [(k, k) for k in ("kill_deadliest", "windfall", "force_war")]
            for name, kind in branches:
                b = base.fork()
                if kind == "kill_deadliest":
                    d = max(b.s["npcs"], key=lambda n: (n["kills"], -n["id"]))
                    b.intervene("kill", [d["id"]])
                elif kind == "windfall":
                    p = min((n for n in b.s["npcs"] if n["alive"]), key=lambda n: n["gold"])
                    b.intervene("give_gold", [p["id"], 500])
                elif kind == "force_war":
                    b.intervene("set_rel", [0, 1, -90])
                b.step(600 - b.tick)
                f, _ = richness(b.s)
                options.append({"seed": sd, "fork_tick": t0, "intervention": name, "richness": f})
    options.sort(key=lambda o: -o["richness"])
    canon = options[0]
    log(f"  branching: {len(options)} alternate histories explored; canon = seed {canon['seed']} fork@{canon['fork_tick']} '{canon['intervention']}' richness {canon['richness']:.3f}"
        f" (median {statistics.median(o['richness'] for o in options):.3f})")
    canon["explored"] = len(options)
    canon["median_richness"] = statistics.median(o["richness"] for o in options)
    return canon


def canon_world(uni):
    c = uni["canon"]
    base = Timeline(W.new_world(c["seed"], uni["rules"]))
    base.step(c["fork_tick"])
    if c["intervention"] != "none":
        b = base
        if c["intervention"] == "kill_deadliest":
            d = max(b.s["npcs"], key=lambda n: (n["kills"], -n["id"]))
            b.intervene("kill", [d["id"]])
        elif c["intervention"] == "windfall":
            p = min((n for n in b.s["npcs"] if n["alive"]), key=lambda n: n["gold"])
            b.intervene("give_gold", [p["id"], 500])
        else:
            b.intervene("set_rel", [0, 1, -90])
    base.step(600 - base.tick)
    return base


def chronicle(uni):
    tl = canon_world(uni)
    s = tl.s
    lex = uni["lexicon"]
    nm = lambda i: f"{W.npc_name(s['npcs'][i])} of {lex['factions'][s['npcs'][i]['faction']]}" if i >= 0 else "an unseen hand"
    scored = []
    for ev in s["events"]:
        if ev[2] in (W.EV_KILL, W.EV_WAR):
            scored.append((len(W.consequences(s, ev[0])), ev))
    scored.sort(key=lambda x: -x[0])
    lines, piv = [], []
    for n, ev in sorted(scored[:6], key=lambda x: x[1][1]):
        if ev[2] == W.EV_KILL:
            txt = f"Day {ev[1]}: {nm(ev[4])} fell at {lex['towns'][ev[5]]} to {nm(ev[3])}."
        else:
            txt = f"Day {ev[1]}: war broke out between {lex['factions'][ev[3]]} and {lex['factions'][ev[4]]}."
        lines.append(txt + f" It set off {n} later events.")
        piv.append({"event": ev[0], "tick": ev[1], "cascade": n})
    return lines, piv
