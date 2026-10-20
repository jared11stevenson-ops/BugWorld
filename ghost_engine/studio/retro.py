"""Retrospective: analyze the cycle (bottlenecks, failures, search gains) and update the studio's persistent knowledge.
Only universe-independent numbers are stored: the universe itself is archived, then forgotten."""
import statistics


def retrospective(know, cname, uni, games, reports, timings, genres):
    stages = {k: v for k, v in timings.items() if k != "total"}
    bottleneck = max(stages, key=stages.get)
    fails = [(gid, name) for gid, r in reports.items() for name, ok in r["checks"].items() if not ok]
    search = uni["search"]
    entry = {"cycle": cname, "released": [gid for gid, r in reports.items() if r["released"]], "failed_checks": [f"{g}:{n}" for g, n in fails],
             "timings_s": timings, "bottleneck": bottleneck, "universe_search": {"start": search["start_fitness"], "final": search["final_fitness"], "evaluations": search["evaluations"]},
             "history_branches_explored": uni["canon"]["explored"], "canon_richness": uni["canon"]["richness"], "median_branch_richness": uni["canon"]["median_richness"],
             "law": uni["law"]}
    entry["genres"] = genres
    entry["tuning"] = {}
    for g in games:
        tn = g.get("tuning")
        if tn:
            hb = tn["holdout_best"]
            entry["tuning"][g["id"]] = {"start": tn["start_fitness"], "final": tn["final_fitness"], "holdout_skilled": hb["skilled"], "holdout_novice": hb["novice"],
                                        "holdout_average": hb.get("average"), "in_band": tn.get("in_band"), "retuned": tn.get("retuned", False)}
    entry["perf_step_us"] = {gid: r["details"]["selftest"].get("perf_step_us") for gid, r in reports.items() if r["details"].get("selftest", {}).get("perf_step_us") is not None}
    know["cycles"].append(entry)
    actions = []
    if search["final_fitness"] >= search["start_fitness"]:
        pri = {}
        for sec in ("world", "economy"):
            for k, v in uni["rules"][sec].items():
                if (sec, k) in __import__("studio.universe", fromlist=["BOUNDS"]).BOUNDS:
                    old = know["universe_priors"].get(k)
                    pri[k] = v if old is None else round((old + v) / 2)
        know["universe_priors"] = pri
        actions.append("stored evolved world-rule priors (search improved fitness)")
    for g in games:
        tn = g.get("tuning")
        if tn and tn.get("in_band"):
            kind = {"arcade3d": "arcade"}.get(g["id"], g["id"])
            key = "cordon" if kind == "cordon" else f"{kind}:{uni['law']}"
            know["tuning_priors"][key] = tn["params"]
            actions.append(f"stored validated tuning parameters '{key}' (held-out skill gap confirmed)")
    # 2b) persist widened tuner bounds when a search saturated (the studio's tuning space itself evolves)
    for g in games:
        tn = g.get("tuning")
        if tn and tn.get("at_bounds"):
            kind = {"arcade3d": "arcade"}.get(g["id"], g["id"])
            from studio import tuner as _t
            wide = _t.widen(kind, {k: tuple(v) for k, v in tn["bounds_used"].items()}, tn["at_bounds"])
            know.setdefault("tuner_bounds", {})[kind] = {k: list(v) for k, v in wide.items()}
            actions.append(f"tuner for '{kind}' saturated at {tn['at_bounds']} -> bounds widened for future cycles")
        if tn and tn.get("retuned"):
            actions.append(f"'{g['id']}': first tuning missed the target band; retune with widened bounds {'succeeded' if tn['in_band'] else 'still missed'}")
    # 3) budget adaptation from measured search behaviour
    b = know["budget"]
    gain = search["final_fitness"] - search["start_fitness"]
    last_gain = search["curve"][-1]["best"] - search["curve"][-3]["best"] if len(search["curve"]) >= 3 else 0
    if last_gain > 0.01 and b["universe_gens"] < 24:
        b["universe_gens"] += 4
        actions.append("universe search still improving at the end -> +4 generations next cycle")
    elif gain < 0.005 and b["universe_gens"] > 6:
        b["universe_gens"] -= 2
        actions.append("universe search flat -> -2 generations next cycle (saves compute)")
    # 4) lessons from failures
    for g, n in fails:
        know["lessons"].append({"cycle": cname, "game": g, "check": n, "note": "fix before next release; gate failed"})
    if not fails:
        know["lessons"].append({"cycle": cname, "note": f"all checks passed; slowest stage was {bottleneck} ({stages[bottleneck]}s)"})
    know["improvements"].append({"cycle": cname, "actions": actions})
    know["capabilities"] = __import__("studio.agents", fromlist=["ROLES"]).ROLES
    return entry
