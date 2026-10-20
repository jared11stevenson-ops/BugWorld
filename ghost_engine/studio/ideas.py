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
    "arcade3d": ["wells", "pulse", "drift"],
    "concept": ["signal", "selection", "feedback"],
    "steward": ["network", "symbiosis", "scarcity"],
}
GENRE_ID = {"concept": "concept_campaign"}
SIM = {"volley": ("volley", G.build_volley), "splash": ("splash", G.build_splash)}
W = {"fun": 0.28, "depth": 0.14, "novelty": 0.24, "fit": 0.34}


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
        sets = []
        for c in cs:
            p = tuner.SPECS[kind]["base"](uni["law"], uni["physics"], c["mods"])
            sets.append({"p": p, "seed_base": 3000})
        res = tuner.run_batch(lab, sets, tuner.SPECS[kind]["script"])
        for c, r in zip(cs, res):
            c["sim"] = r
            mono = r["skilled"] >= r["average"] >= r["novice"]
            c["depth"] = round(min(1.0, max(0.0, (r["skilled"] - r["novice"]) / 0.7)) * (1.0 if mono else 0.6), 3)
            c["fun"] = round(tuner.fitness(r), 3)
            c["simulated"] = True


def explore(uni, know, workdir, quick=False, log=print):
    cands = candidates(uni)
    os.makedirs(workdir, exist_ok=True)
    _simulate(cands, uni, workdir, quick)
    archive = seed_archive(know)
    insp = inspiration_elements(uni)
    for c in cands:
        if not c.get("simulated"):
            c["fun"], c["depth"], c["simulated"] = 0.45, 0.45, False     # neutral prior: no per-idea bot simulation exists for this family
        c["fit"], c["coverage"] = coverage(c, insp)
        c["novelty"] = round(novelty(c, archive), 3)
        c["fit"] = round(c["fit"], 3)
        c["score"] = round(sum(W[k] * c[k] for k in W), 4)
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
    bits = {"volley": "a net-and-rally sport", "splash": "a top-down water-balloon skirmish", "cordon": "a containment campaign", "arcade3d": "a 3D expedition",
            "concept": "a duel of discovered rules", "steward": "a stewardship of the living world"}[c["family"]]
    return f"In {uni['name']}, {fac} play {bits}: {c['label']}. Laws honoured: " + "; ".join(EL.ELEMENTS[e]["law"] for e in c["elements"][:2])


def remember(know, cname, chosen):
    know.setdefault("idea_archive", seed_archive(know) if not know.get("idea_archive") else know["idea_archive"])
    for c in chosen:
        know["idea_archive"].append({"cycle": cname, "family": c["family"], "mods": c["mods"], "label": c["label"], "score": c["score"], "novelty": c["novelty"]})


def mods_key(mods):
    return ",".join(f"{k}{v}" for k, v in sorted(mods.items()))
