"""Golden traces from the Python kernel. The Godot parity test must reproduce every value exactly."""
from ..kernel import rng as R, world as W, combat as C, policies as P
from ..kernel.timeline import Timeline
from ..lab import tournament as T


def golden(rulesets):
    """rulesets: {name: full ruleset dict}. Returns a JSON-able dict of ints/strings/lists only."""
    g = {"rng": {"seed": 12345, "vals": []}, "payoff": {}, "duels": {}, "worlds": [], "timeline": {}}
    st = {"rng": R.seed_state(12345)}
    g["rng"]["vals"] = [R.rand(st, 1000) for _ in range(8)]
    for name, rules in rulesets.items():
        c = rules["combat"]
        a = {"hp": 100, "maxhp": 100, "atk": 20, "def": 5, "potions": c["start_potions"], "last": -1, "streak": 0}
        g["payoff"][name] = [[C.payoff(c, a, dict(a), x, y) for y in range(4)] for x in range(4)]
        duels = []
        for pa in range(P.NUM):
            for pb in range(pa, P.NUM):
                sc, rounds, stale = T.duel(c, pa, pb, 31337 + pa * 8 + pb)
                duels.append([pa, pb, 31337 + pa * 8 + pb, int(sc * 2), rounds, 1 if stale else 0])
        g["duels"][name] = duels
        for seed in (1, 2, 3, 7):
            s = W.new_world(seed, rules)
            cps = []
            for _ in range(4):
                W.run(s, 100)
                cps.append([s["tick"], W.digest_hex(s)])
            g["worlds"].append({"rules": name, "seed": seed, "checkpoints": cps, "events": len(s["events"]),
                                "ev_hash": s["ev_hash"], "alive": sum(n["alive"] for n in s["npcs"]),
                                "conservation_error": W.conservation_error(s)})
    # timeline semantics: rewind/replay, branching, interventions (uses the last ruleset given)
    name, rules = list(rulesets.items())[-1]
    tl = Timeline(W.new_world(5, rules))
    tl.step(200)
    d200 = W.digest_hex(tl.s)
    tl.step(100)
    d300 = W.digest_hex(tl.s)
    tl.rewind(120)
    tl.step(80)
    replay200 = W.digest_hex(tl.s)
    main = Timeline(W.new_world(9, rules))
    main.step(100)
    same, alt = main.fork(), main.fork()
    alt.intervene("kill", [1])
    alt.intervene("set_rule", [90], path="world.aggro_pct")
    for t in (main, same, alt):
        t.step(150)
    g["timeline"] = {"rules": name, "d200": d200, "d300": d300, "replay200": replay200,
                     "main250": W.digest_hex(main.s), "same250": W.digest_hex(same.s), "alt250": W.digest_hex(alt.s)}
    return g
