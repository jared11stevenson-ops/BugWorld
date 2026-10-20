"""Idea exploration: the universe is searched for game ideas BEFORE any game is built.

An idea = (family, module configuration). The universe's fused elements decide which families and modules exist at all (elements.py).
Every candidate that has a headless bot simulation (volley, splash) is actually played by tiered bots (novice / average / expert) in a lab project;
the others are scored from priors and flagged as unsimulated. Scores (all proxies, never claimed as fun):
  playability = tuner.fitness of the untuned idea, depth = monotonic skill gradient, novelty = distance from every idea the studio has shipped,
  fit = how much of EACH fused inspiration the idea expresses (rewards true fusion), revolution = novelty x fit x depth.
Three ideas are selected from three different families (genres)."""
import json, os
from . import elements as EL, tuner, games as G

CORE = {   # elements a family expresses by itself
    "volley": ["net", "rally", "touch_limit", "serve", "bounce", "team"],
    "splash": ["projectile_arc", "burst", "soak", "refill", "friendly_fire", "team"],
    "cordon": ["contagion", "quarantine", "network", "fog"],
    "artillery": ["projectile_arc", "siege", "wind", "bounce"],
    "bastion": ["siege", "logistics", "team"],
    "arcade3d": ["wells", "pulse", "drift"],
    "concept": ["signal", "selection", "feedback"],
    "steward": ["network", "symbiosis", "scarcity"],
}
GENRE_ID = {"concept": "concept_campaign"}
SIM = {"volley": ("volley", G.build_volley), "splash": ("splash", G.build_splash), "artillery": ("artillery", G.build_artillery), "bastion": ("bastion", G.build_bastion), "arcade3d": ("arcade", G.build_arcade3d)}
# Inspirations shape the WORLD, not the game. A game is chosen for quality, novelty and how fully it lives inside the universe's physics; being a literal copy of an inspiration earns nothing.
W = {"fun": 0.25, "depth": 0.12, "novelty": 0.24, "fit": 0.17, "surprise": 0.08, "richness": 0.14}
HONOURS = {   # which shared physics constants each engine actually honours
    "volley": {"gravity_scale", "wind", "slick", "restitution_scale", "burst_radius"}, "splash": {"wind", "slick", "burst_radius"},
    "artillery": {"gravity_scale", "wind", "armor_factor"}, "bastion": {"gravity_scale", "armor_factor"}, "cordon": set(), "arcade3d": set(), "concept": set(), "steward": set(),
}
PHYS_DEFAULT = {"gravity_scale": 1.0, "wind": 0.0, "slick": 0, "burst_radius": 1.0, "restitution_scale": 1.0, "armor_factor": 1.0, "soak_weight": 0.0}


def _combos(mods):
    out = [{}]
    for m, vals in mods.items():
        out = [dict(o, **{m: v}) for o in out for v in vals]
    return out


def core(fam, uni):
    """Families whose content is generated from the universe express whatever the universe's own tags/dynamics contain."""
    if fam == "concept":      # the rule-discovery loop is primed by every tag of the universe
        return sorted(set(CORE[fam]) | {e for t in uni["tags"] for e in EL.TAG_ELEMENTS.get(t, [])})
    if fam == "steward":      # the world simulation expresses the diffusive/periodic elements of the evolved world rules
        return sorted(set(CORE[fam]) | {e for e in ("tide", "soak", "drift", "pulse", "diffusion", "wind", "erosion") if e in uni["elements"]})
    return CORE[fam]


def candidates(uni):
    els = uni["elements"]
    out = []
    for fam, spec in EL.FAMILIES.items():
        if not EL.family_available(fam, els):
            continue
        mods = {m: [v for v in vals if EL.module_available(fam, m, v, els)] for m, vals in spec["modules"].items()}
        for c in _combos(mods):
            used = set(core(fam, uni)) | {e for m, v in c.items() for e in EL.FAMILIES[fam]["modules"][m][v][1]}
            out.append({"family": fam, "genre": GENRE_ID.get(fam, fam), "mods": c, "elements": sorted(e for e in used if e in els),
                        "label": " + ".join([EL.FAMILIES[fam]["modules"][m][v][0] for m, v in c.items()] or [EL.FAMILIES[fam]["genre"]])})
    return out


def inspiration_elements(uni):
    from . import inspiration
    bank = {b[0]: b for b in inspiration.BANK}
    return {n: set(EL.entry_elements(bank[n])) & set(uni["elements"]) for n in uni["inspirations"] if n in bank}


def coverage(cand, insp_els):
    cov = {n: (len(set(cand["elements"]) & es) / len(es) if es else 1.0) for n, es in insp_els.items()}
    vals = list(cov.values())
    return (0.5 * sum(vals) / len(vals) + 0.5 * min(vals)) if vals else 0.5, cov


def integration(family, physics):
    """How much of the universe's active physics the engine honours (0.25 baseline: every game carries the codex, lore and factions)."""
    active = {k for k, v in physics.items() if v != PHYS_DEFAULT.get(k, v)}
    if not active:
        return 1.0
    return 0.25 + 0.75 * len(active & HONOURS.get(family, set())) / len(active)


def novelty(cand, archive):
    """1.0 = nothing like it was ever shipped. Same family: module-configuration distance to the closest shipped idea; new family: 1.0."""
    same = [a for a in archive if a["family"] == cand["family"]]
    if not same:
        return 1.0
    keys = list(cand["mods"]) or [None]
    if keys == [None]:
        return 0.15
    d = min(sum(1 for k in keys if cand["mods"][k] != a["mods"].get(k, 0)) / len(keys) for a in same)
    return 0.15 + 0.85 * d


def seed_archive(know):
    """Ideas shipped before the idea model existed are reconstructed from the genre history (default modules)."""
    arch = list(know.get("idea_archive", []))
    if not arch:
        for c in know.get("cycles", []):
            for g in c.get("genres", []):
                arch.append({"cycle": c.get("cycle"), "family": {"concept_campaign": "concept"}.get(g, g), "mods": {}, "label": "baseline"})
    return arch


def _simulate(cands, uni, workdir, quick):
    """Play every simulatable candidate with tiered bots in one lab project per family; one batched Godot run each."""
    for fam in SIM:
        cs = [c for c in cands if c["family"] == fam]
        if not cs:
            continue
        kind, builder = SIM[fam]
        lab = os.path.join(workdir, "idea_lab_" + fam)
        base = tuner.SPECS[kind]["base"](uni["law"], uni["physics"], None)
        builder(uni, lab, base)
        probes = tuner.SPECS[kind].get("probes", [{}])        # difficulty probes: an idea is judged at its best-calibrated difficulty, not at an arbitrary default
        sets = []
        for c in cs:
            for pr in probes:
                p = tuner.SPECS[kind]["base"](uni["law"], uni["physics"], c["mods"])
                p.update(pr)
                sets.append({"p": p, "seed_base": 3000})
        res = tuner.run_batch(lab, sets, tuner.SPECS[kind]["script"])
        for ci, c in enumerate(cs):
            rs = res[ci * len(probes):(ci + 1) * len(probes)]
            r = max(rs, key=tuner.fitness)
            c["sim"] = r
            mono = r["skilled"] >= r.get("average", r["skilled"]) >= r["novice"]
            c["depth"] = round(min(1.0, max(0.0, (r["skilled"] - r["novice"]) / 0.7)) * (1.0 if mono else 0.6), 3)
            c["fun"] = round(tuner.fitness(r), 3)
            c["simulated"] = True
            c["probes"] = len(probes)


def explore(uni, know, workdir, quick=False, log=print):
    cands = candidates(uni)
    os.makedirs(workdir, exist_ok=True)
    _simulate(cands, uni, workdir, quick)
    archive = seed_archive(know)
    insp = inspiration_elements(uni)
    for c in cands:
        if not c.get("simulated"):
            c["fun"], c["depth"], c["simulated"] = 0.45, 0.45, False     # neutral prior: no per-idea bot simulation exists for this family
        lit, c["coverage"] = coverage(c, insp)          # how literally the idea restates an inspiration (reported, and penalised via surprise)
        c["literalness"] = round(max(c["coverage"].values()) if c["coverage"] else 0.0, 3)
        c["surprise"] = round(1.0 - c["literalness"], 3)
        c["novelty"] = round(novelty(c, archive), 3)
        c["richness"] = round(sum(1 for v in c["mods"].values() if v) / len(c["mods"]), 3) if c["mods"] else 0.3     # interacting rule modules: more systems to play with (only counts if the idea also scores on fun)
        c["fit"] = round(integration(c["family"], uni["physics"]), 3)
        c["score"] = round(sum(W[k] * c[k] for k in W) * (1.0 if c["fun"] >= 0.8 or not c["simulated"] else 0.85), 4)
        c["revolution"] = round(c["novelty"] * c["fit"] * (0.5 + c["depth"]), 3)
        c["coverage"] = {k: round(v, 2) for k, v in c["coverage"].items()}
    ranked = sorted(cands, key=lambda c: -c["score"])
    chosen, fams = [], set()
    for c in ranked:
        if c["family"] not in fams and len(chosen) < 3:
            chosen.append(c); fams.add(c["family"])
    for c in chosen:
        c["premise"] = premise(c, uni)
    log(f"  idea space: {len(cands)} candidates over {len({c['family'] for c in cands})} families; simulated {sum(1 for c in cands if c['simulated'])}")
    for c in chosen:
        log(f"  idea -> {c['family']}: {c['label']} (score {c['score']}, fun {c['fun']}, depth {c['depth']}, novelty {c['novelty']}, fit {c['fit']})")
    return {"chosen": chosen, "ranked": ranked, "weights": W, "archive_size": len(archive)}


def premise(c, uni):
    fac = uni["lexicon"]["factions"][0]
    bits = {"volley": "a net-and-rally sport", "splash": "a top-down lobbed-munition skirmish", "artillery": "a duel of arcing shells over wind and broken ground", "bastion": "a siege defence along a winding road", "cordon": "a containment campaign", "arcade3d": "a 3D expedition",
            "concept": "a duel of discovered rules", "steward": "a stewardship of the living world"}[c["family"]]
    return f"In {uni['name']}, {fac} play {bits}: {c['label']}. Laws honoured: " + "; ".join(EL.ELEMENTS[e]["law"] for e in c["elements"][:2])


def remember(know, cname, chosen):
    know.setdefault("idea_archive", seed_archive(know) if not know.get("idea_archive") else know["idea_archive"])
    for c in chosen:
        know["idea_archive"].append({"cycle": cname, "family": c["family"], "mods": c["mods"], "label": c["label"], "score": c["score"], "novelty": c["novelty"]})


def mods_key(mods):
    return ",".join(f"{k}{v}" for k, v in sorted(mods.items()))


LIBRARY_ADDED = {"concept": "cycle_001", "steward": "cycle_001", "arcade3d": "cycle_003", "cordon": "cycle_003", "volley": "cycle_004", "splash": "cycle_004", "artillery": "cycle_006", "bastion": "cycle_006"}


def sync_library(know, cname):
    """The studio's own game library: which engines exist, since when, and whether they are theme-neutral (playable in any universe)."""
    lib = know.setdefault("library", {})
    for fam, spec in EL.FAMILIES.items():
        e = lib.setdefault(fam, {"added": LIBRARY_ADDED.get(fam, cname), "uses": 0})
        e["neutral"] = bool(spec.get("neutral", not spec["unlock"]))
        e["modules"] = {m: len(v) for m, v in spec["modules"].items()}
    return lib


def next_capability(exp, uni):
    """Self-evolution: name the single most valuable capability the studio should build before the next cycle (kept in knowledge['roadmap'])."""
    chosen = exp["chosen"]
    unsim = [c["family"] for c in chosen if not c["simulated"]]
    if unsim:
        return f"per-idea bot simulation for '{unsim[0]}' (it won a slot on a neutral prior, not on evidence)"
    weakest = min(chosen, key=lambda c: c["fun"] + c["depth"])
    themed = [f for f, sp in EL.FAMILIES.items() if sp["unlock"] and not sp.get("neutral")]
    if themed:
        return f"re-skin the theme-bound engine '{themed[0]}' so it can serve any universe, and deepen '{weakest['family']}' (weakest fun+depth {weakest['fun']}+{weakest['depth']})"
    return f"add a new engine/genre; weakest chosen idea is '{weakest['family']}'"
