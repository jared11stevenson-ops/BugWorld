"""One production cycle: inspiration -> universe -> 3 games -> verify -> archive -> retrospective -> RESET."""
import hashlib, json, os, shutil, time
from . import inspiration, universe as U, games as G, tuner, verify, retro, agents, lore, ideas
from ghost.foundry import grammar as FG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "studio", "state")
KNOW = os.path.join(ROOT, "studio", "knowledge", "knowledge.json")
ARCHIVE = os.path.join(ROOT, "archive")


def load_knowledge():
    if os.path.exists(KNOW):
        k = json.load(open(KNOW))
        k.setdefault("tuning_priors", {f"arcade:{law}": p for law, p in k.get("arcade_priors", {}).items()})
        k.setdefault("human_feedback", {})
        for c in k["cycles"]:
            c.setdefault("genres", ["concept_campaign", "steward", "arcade"])
        return k
    seed_lessons = os.path.join(ROOT, "studio", "knowledge", "seed_lessons.json")
    return {"version": 1, "cycles": [], "budget": {"universe_pop": 16, "universe_gens": 12, "tune_pop": 12, "tune_gens": 8, "g1_gens": 8},
            "universe_priors": {}, "tuning_priors": {}, "human_feedback": {}, "lessons": json.load(open(seed_lessons)) if os.path.exists(seed_lessons) else [], "improvements": [], "capabilities": agents.ROLES}


def next_cycle_id():
    os.makedirs(ARCHIVE, exist_ok=True)
    n = len([d for d in os.listdir(ARCHIVE) if d.startswith("cycle_")])
    return n + 1


def run_cycle(prompt=None, seed=None, quick=False, log=print):
    global ARCHIVE, KNOW
    if quick:       # smoke runs never touch the real archive or the studio's accumulated knowledge
        ARCHIVE = os.path.join("/tmp", "ghost_smoke_archive")
        KNOW = os.path.join("/tmp", "ghost_smoke_knowledge.json")
        shutil.rmtree(ARCHIVE, ignore_errors=True)
        if os.path.exists(KNOW):
            os.remove(KNOW)
    know = load_knowledge()
    cid = next_cycle_id()
    cname = f"cycle_{cid:03d}"
    timings = {}
    t_all = time.time()
    def stage(name):
        class T:
            def __enter__(s): s.t = time.time(); log(f"[{cname}] {name} ..."); return s
            def __exit__(s, *a): timings[name] = round(time.time() - s.t, 1)
        return T()
    if os.path.exists(STATE):
        shutil.rmtree(STATE)
    os.makedirs(STATE)
    bud = dict(know["budget"])
    if quick:
        bud.update(universe_pop=8, universe_gens=3, tune_pop=6, tune_gens=1, g1_gens=4)
    with stage("1_inspiration"):
        ins, seed = inspiration.pick(seed, prompt)
        log("  inspirations: " + "; ".join(f"{b[0]} ({b[1]})" for b in ins))
    with stage("2_universe"):
        uni = U.make_universe(ins, seed)
        U.explore(uni, know, pop=bud["universe_pop"], gens=bud["universe_gens"], seeds=(1, 2, 3) if not quick else (1, 2), ticks=600 if not quick else 300, log=log)
        json.dump(uni, open(os.path.join(STATE, "universe.json"), "w"), indent=1)
    with stage("2b_lore"):
        uni["lore"] = lore.make_lore(uni)
        json.dump(uni, open(os.path.join(STATE, "universe.json"), "w"), indent=1)
    with stage("2c_idea_exploration"):
        exp = ideas.explore(uni, know, os.path.join(STATE, "lab"), quick=quick, log=log)
    chosen = exp["chosen"]
    ideas.sync_library(know, cname)
    nxt = ideas.next_capability(exp, uni)
    know.setdefault("roadmap", []).append({"cycle": cname, "next_capability": nxt})
    log(f"  studio roadmap: {nxt}")
    genres = [c["genre"] for c in chosen]
    genre_scores = {c["genre"]: c["score"] for c in chosen}
    uni["siblings"] = [{"genre": c["genre"], "label": c["label"], "premise": c["premise"]} for c in chosen]
    games = []
    gdir = os.path.join(STATE, "games")
    for idea in chosen:
        gid = idea["genre"]
        with stage(f"3_build_{gid}"):
            proj = os.path.join(gdir, gid)
            if gid == "concept_campaign":
                games.append(G.build_concept_campaign(uni, proj, STATE, know, gens=bud["g1_gens"], per_gen=24 if quick else 40, log=log))
                games[-1]["idea"] = {k: idea[k] for k in ("family", "label", "mods", "premise", "score", "fun", "depth", "novelty", "fit", "coverage", "revolution", "simulated", "surprise", "literalness", "richness")}
            elif gid == "steward":
                games.append(G.build_steward(uni, proj, target_pct=135))
                games[-1]["idea"] = {k: idea[k] for k in ("family", "label", "mods", "premise", "score", "fun", "depth", "novelty", "fit", "coverage", "revolution", "simulated", "surprise", "literalness", "richness")}
            else:
                kind, builder = {"arcade": ("arcade", G.build_arcade), "arcade3d": ("arcade", G.build_arcade3d), "cordon": ("cordon", G.build_cordon),
                                 "volley": ("volley", G.build_volley), "splash": ("splash", G.build_splash), "artillery": ("artillery", G.build_artillery), "bastion": ("bastion", G.build_bastion)}[gid]
                mods = idea["mods"]
                base = tuner.SPECS[kind]["base"](uni["law"], uni["physics"], mods)
                builder(uni, proj, base)
                key = ("cordon" if kind == "cordon" else f"{kind}:{uni['law']}") + (":" + ideas.mods_key(mods) if mods else "")
                init = know["tuning_priors"].get(key)
                override = know.get("tuner_bounds", {}).get(kind)
                tuning = tuner.tune(proj, kind, uni["law"], seed, pop=bud["tune_pop"], gens=bud["tune_gens"], init=init, bounds_override=override, log=log, physics=uni["physics"], mods=mods)
                tuning["retuned"] = False
                if not quick and not tuning["in_band"] and tuning["at_bounds"]:
                    # evolved behaviour: the search saturated at its bounds and missed the target band -> widen those bounds (within hard caps) and retune once
                    wide = tuner.widen(kind, {k: tuple(v) for k, v in tuning["bounds_used"].items()}, tuning["at_bounds"])
                    log(f"  tune[{kind}] saturated at {tuning['at_bounds']} and outside target band -> widening bounds and retuning")
                    t2 = tuner.tune(proj, kind, uni["law"], seed + 1, pop=bud["tune_pop"], gens=bud["tune_gens"], init=tuning["params"], bounds_override=wide, log=log, physics=uni["physics"], mods=mods)
                    t2["retuned"] = True
                    t2["first_attempt"] = {"holdout_best": tuning["holdout_best"], "at_bounds": tuning["at_bounds"], "in_band": False}
                    if t2["in_band"] or tuner.fitness(t2["holdout_best"]) > tuner.fitness(tuning["holdout_best"]):
                        tuning = t2
                g = builder(uni, proj, tuning["params"], tuning)
                g["idea"] = {k: idea[k] for k in ("family", "label", "mods", "premise", "score", "fun", "depth", "novelty", "fit", "coverage", "revolution", "simulated", "surprise", "literalness", "richness")}
                games.append(g)
    reports = {}
    with stage("6_verification"):
        for g in games:
            reports[g["id"]] = verify.verify_game(g, os.path.join(gdir, g["id"]), os.path.join(STATE, "evidence", g["id"]))
            log(f"  {g['id']}: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in reports[g["id"]]["checks"].items()))
    with stage("7_archive"):
        dest = os.path.join(ARCHIVE, cname)
        os.makedirs(dest)
        for g in games:
            shutil.copytree(os.path.join(gdir, g["id"]), os.path.join(dest, "games", g["id"]), ignore=shutil.ignore_patterns(".godot", "*.uid", "__pycache__"))
            shutil.copytree(os.path.join(STATE, "evidence", g["id"], "screens"), os.path.join(dest, "evidence", g["id"], "screens"))
        udoc = {k: v for k, v in uni.items()}
        json.dump(udoc, open(os.path.join(dest, "universe.json"), "w"), indent=1)
        with open(os.path.join(dest, "CHRONICLE.md"), "w") as f:
            f.write(f"# {uni['name']}\n\n{uni['law_text']}\n\n## Inspirations (real world)\n" + "\n".join(f"- **{k}** — {v}" for k, v in uni["facts"].items())
                    + "\n\n## Factions\n" + "\n".join(f"- {x}" for x in uni["lexicon"]["factions"]) + "\n\n## Canon history (from the evolved, branch-selected simulation)\n" + "\n".join(f"- {l}" for l in uni["chronicle"]) + "\n")
        slim = [{k: v for k, v in g.items() if k not in ("data",)} for g in games]
        manifest = {"cycle": cname, "universe": uni["id"], "seed": seed, "prompt": prompt, "genres": genres, "genre_scores": genre_scores, "games": slim, "verification": reports,
                    "released": [g["id"] for g in games if reports[g["id"]]["released"]], "timings_s": timings}
        json.dump(manifest, open(os.path.join(dest, "manifest.json"), "w"), indent=1)
        json.dump({"universe": uni["name"], "elements": uni["elements"], "physics": uni["physics"], "weights": exp["weights"], "chosen": exp["chosen"], "ranked": exp["ranked"]},
                  open(os.path.join(dest, "ideas.json"), "w"), indent=1)
        idx_p = os.path.join(ARCHIVE, "index.json")
        idx = json.load(open(idx_p)) if os.path.exists(idx_p) else []
        idx.append({"cycle": cname, "universe": uni["name"], "released": manifest["released"], "inspirations": uni["inspirations"], "genres": genres})
        json.dump(idx, open(idx_p, "w"), indent=1)
    timings["total"] = round(time.time() - t_all, 1)
    with stage("8_retrospective_and_reset"):
        know_hash_before = hashlib.sha256(json.dumps(know, sort_keys=True).encode()).hexdigest()
        ideas.remember(know, cname, exp["chosen"])
        for c in exp["chosen"]:
            know["library"][c["family"]]["uses"] += 1
        retro.retrospective(know, cname, uni, games, reports, timings, genres)
        json.dump(know, open(KNOW, "w"), indent=1, sort_keys=True)
        reset_report = reset_state(uni)
    manifest["timings_s"] = timings
    manifest["reset"] = reset_report
    json.dump(manifest, open(os.path.join(dest, "manifest.json"), "w"), indent=1)
    return manifest


def reset_state(uni):
    """Controlled reset: universe, creative assumptions and temporary simulation state are destroyed; studio knowledge is retained."""
    shutil.rmtree(STATE, ignore_errors=True)
    FG.KIND_W = None
    for root, dirs, _f in os.walk(os.path.join(ROOT, "studio")):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
    know = json.load(open(KNOW))
    ok = (not os.path.exists(STATE)) and FG.KIND_W is None and uni["name"] not in json.dumps({k: v for k, v in know.items() if k != "cycles"}) \
        and bool(know["cycles"]) and "universe" not in know
    return {"state_dir_removed": not os.path.exists(STATE), "grammar_priors_cleared": FG.KIND_W is None,
            "knowledge_retained": bool(know["cycles"]), "no_universe_leak_in_knowledge": uni["name"] not in json.dumps({k: v for k, v in know.items() if k != "cycles"}),
            "ok": ok}
