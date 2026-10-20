"""Game builders. Each returns the data/evidence for one game inside the universe and writes a self-contained Godot project."""
import json, os, random, shutil
from ghost.foundry import dsl, loop as L, grammar as G, seeds as S
from . import universe as U, audio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "studio", "templates")
GODOT_LIB = os.path.join(ROOT, "godot", "ghost")
VERBS = ["surge", "weave", "anchor", "ripple", "kindle", "fracture", "tether", "glide", "siphon", "bloom", "erode", "pulse", "ward", "sever"]


def gd_const(name, obj):
    txt = json.dumps(obj, sort_keys=True)
    assert "true" not in txt and "false" not in txt and "null" not in txt, "gd const must avoid json literals"
    return f"extends RefCounted\n\nconst {name} := {txt}\n"


def assemble(project_dir, game_id, title, universe, extra_files, libs, template_game, extra_templates=()):
    """Create a standalone Godot project: libs + template script + data + audio."""
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
    for d in ("ghost", "data", "audio", "tests"):
        os.makedirs(os.path.join(project_dir, d))
    for f in libs:
        src = os.path.join(TPL, "lib", f) if os.path.exists(os.path.join(TPL, "lib", f)) else os.path.join(GODOT_LIB, f)
        shutil.copy(src, os.path.join(project_dir, "ghost", f))
    for f in ("selftest.gd", "shot.gd"):
        shutil.copy(os.path.join(TPL, "lib", f), os.path.join(project_dir, "tests", f))
    shutil.copy(os.path.join(TPL, template_game), os.path.join(project_dir, "game.gd"))
    for t in extra_templates:
        shutil.copy(os.path.join(TPL, t), os.path.join(project_dir, "ghost", os.path.basename(t)))
    with open(os.path.join(project_dir, "main.tscn"), "w") as f:
        f.write('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://game.gd" id="1"]\n\n'
                '[node name="Main" type="Control"]\nlayout_mode = 3\nanchors_preset = 15\nanchor_right = 1.0\nanchor_bottom = 1.0\nscript = ExtResource("1")\n')
    with open(os.path.join(project_dir, "project.godot"), "w") as f:
        f.write(f'config_version=5\n\n[application]\n\nconfig/name="{title}"\nrun/main_scene="res://main.tscn"\nconfig/features=PackedStringArray("4.4")\n\n'
                '[rendering]\n\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n\n[debug]\n\ngdscript/warnings/integer_division=0\ngdscript/warnings/unused_parameter=0\ngdscript/warnings/shadowed_variable=0\n\n'
                '[display]\n\nwindow/size/viewport_width=1100\nwindow/size/viewport_height=680\nwindow/stretch/mode="canvas_items"\n')
    uj = {k: universe[k] for k in ("id", "seed", "name", "inspirations", "facts", "law", "law_text", "palette", "lexicon", "mood", "elements", "laws", "physics", "siblings") if k in universe}
    uj["lore"] = universe.get("lore", {})
    uj["game_title"] = title
    json.dump(uj, open(os.path.join(project_dir, "data", "universe.json"), "w"), indent=1)
    for rel, content in extra_files.items():
        with open(os.path.join(project_dir, rel), "w" if isinstance(content, str) else "wb") as f:
            f.write(content)
    audio.sfx(os.path.join(project_dir, "audio"), universe["seed"] * 3 + len(game_id))
    audio.music(os.path.join(project_dir, "audio", "music.wav"), universe["seed"] * 5 + len(game_id) * 7, mood=universe.get("mood", "calm"))
    audio.ambient(os.path.join(project_dir, "audio", "ambient.wav"), universe["seed"] + len(game_id), universe.get("mood", "calm"))


# ---------------------------------------------------------------- G1: concept campaign
def rename_spec(spec, names):
    s = json.loads(json.dumps(spec))
    def ex(e):
        if isinstance(e, list) and e:
            if e[0] == "v":
                e[2] = names.get(e[2], e[2])
            for x in e[1:]:
                ex(x)
    for a in s["actions"]:
        ex(a["cond"])
        for f in a["fx"]:
            f[2] = names.get(f[2], f[2]); ex(f[3])
    for f in s["passive"]:
        f[2] = names.get(f[2], f[2]); ex(f[3])
    for e, _o in s["end"]:
        ex(e)
    s["vars"] = [[names.get(v[0], v[0])] + v[1:] for v in s["vars"]]
    s["tiebreak"] = names.get(s["tiebreak"], s["tiebreak"])
    s["value"] = [[names.get(v, v), w] for v, w in s["value"]]
    return s


def theme_spec(spec, uni, idx, rnd):
    motifs = [m.replace("-", "") for m in uni["lexicon"]["motifs"]]
    pool = motifs[:]
    rnd.shuffle(pool)
    names = {}
    for v in spec["vars"]:
        names[v[0]] = pool.pop() if pool else v[0]
    s = rename_spec(spec, names)
    verbs = VERBS[:]
    rnd.shuffle(verbs)
    for a in s["actions"]:
        a["name"] = verbs.pop()
    s["name"] = f"{uni['name']} Trial {idx + 1}"
    s["id"] = f"{uni['id']}-c{idx + 1}"
    assert not dsl.validate(s), dsl.validate(s)
    return s


def build_concept_campaign(uni, out_dir, workdir, knowledge, gens=8, per_gen=40, log=print):
    prior = {}
    for t, n in uni["tags"].items():
        for a in U.TAG_ATOMS.get(t, []):
            prior[a] = prior.get(a, 1.0) * (1 + 0.6 * n)
    F = L.Foundry(os.path.join(workdir, "g1_discovery"), seed=uni["seed"], workers=4, use_inbox=False)
    F.prior = prior
    F.run(generations=gens, per_gen=per_gen, quiet=True)
    disc = F.discoveries(top=3, min_novelty=0.1)
    picked = [d["rec"] for d in disc]
    if len(picked) < 3:     # fall back to best archive elites that are not seeds
        rest = sorted((F.cands[i] for i in F.archive.values() if F.cands[i]["proposer"] != "seed" and F.cands[i]["id"] not in {p["id"] for p in picked}),
                      key=lambda r: -r["fitness"])
        picked += rest[:3 - len(picked)]
    rnd = random.Random(uni["seed"] + 99)
    chapters, evidence = [], []
    for i, rec in enumerate(sorted(picked[:3], key=lambda r: r["fitness"])):   # ascending fitness: build toward the best
        spec = theme_spec(rec["spec"], uni, i, rnd)
        mt = rec["metrics"]
        chapters.append({"title": spec["name"], "blurb": f"{uni['law_text']} Rule set discovered by the foundry (cycle search, generation {rec['gen']}, proposer {rec['proposer']}).",
                         "spec": spec, "text": dsl.spec_text(spec), "ladder": [7, 9, 8]})
        evidence.append({"chapter": i + 1, "source_id": rec["id"], "proposer": rec["proposer"], "fitness": rec["fitness"],
                         "novelty_vs_seeds": rec.get("novelty_vs_seeds"), "live_actions": mt["live_actions"], "n_actions": mt["n_actions"],
                         "interaction": mt["interaction"], "leverage": mt["leverage"], "length": mt["length"], "flags": rec["flags"]})
    camp = {"chapters": chapters, "tagline": f"Three trials of the {uni['name']}. Learn each law, then outplay the adaptive rival."}
    files = {"data/campaign.gd": gd_const("CAMPAIGN", camp), "data/campaign.json": json.dumps(camp)}
    assemble(out_dir, "concept_campaign", f"{uni['name']}: Trials", uni, files,
             ["kernel.gd", "concept.gd", "shell.gd"], "game_concept.gd")
    return {"id": "concept_campaign", "title": f"{uni['name']}: Trials", "genre": "strategy duel campaign", "evidence": evidence,
            "discovery": {"evaluations": len(F.cands), "viable": sum(1 for c in F.cands.values() if c["valid"] and not c["flags"]), "cells": len(F.archive)}}


# ---------------------------------------------------------------- G2: steward
def build_steward(uni, out_dir, target_pct=104):
    data = {"rules": uni["rules"], "seed": uni["canon"]["seed"], "start_tick": 100, "player_faction": 0, "epochs": 10, "epoch_ticks": 25,
            "ip_start": 6, "ip_gain": 4, "target_pct": target_pct, "evaluations": uni["search"]["evaluations"]}
    files = {"data/steward.gd": gd_const("DATA", {"DATA": data}).replace("const DATA := {\"DATA\": ", "const DATA := ")[:-2] + "\n"}
    assemble(out_dir, "steward", f"{uni['lexicon']['factions'][0]}: Steward", uni, files, ["kernel.gd", "timeline.gd", "shell.gd"], "game_steward.gd")
    return {"id": "steward", "title": f"{uni['lexicon']['factions'][0]}: Steward", "genre": "world-sim stewardship", "data": data}


# ---------------------------------------------------------------- G3: arcade
def build_arcade(uni, out_dir, params, tuning=None):
    data = {"params": params}
    uni2 = dict(uni)
    files = {"data/arcade.gd": gd_const("DATA", data).replace("const DATA := ", "const DATA := ")}
    assemble(out_dir, "arcade", f"{uni['name']}: Expedition", uni2, files, ["kernel.gd", "shell.gd"], "game_arcade.gd", ["arcade_core.gd", "tune.gd"])
    u = json.load(open(os.path.join(out_dir, "data", "universe.json")))
    u["fact_lines"] = [f"{k}: {v}" for k, v in uni["facts"].items()]
    json.dump(u, open(os.path.join(out_dir, "data", "universe.json"), "w"), indent=1)
    return {"id": "arcade", "title": f"{uni['name']}: Expedition", "genre": "real-time arcade", "params": params, "tuning": tuning}


# ---------------------------------------------------------------- G: cordon (epidemic containment)
def build_cordon(uni, out_dir, params, tuning=None):
    files = {"data/contain.gd": gd_const("DATA", {"params": params})}
    title = f"{uni['name']}: Cordon"
    assemble(out_dir, "cordon", title, uni, files, ["kernel.gd", "shell.gd"], "game_contain.gd", ["contain_core.gd", "tune_contain.gd"])
    return {"id": "cordon", "title": title, "genre": "network containment strategy", "params": params, "tuning": tuning}


# ---------------------------------------------------------------- G: expedition 3D
def build_arcade3d(uni, out_dir, params, tuning=None):
    files = {"data/arcade.gd": gd_const("DATA", {"params": params})}
    title = f"{uni['name']}: Expedition 3D"
    assemble(out_dir, "arcade3d", title, uni, files, ["kernel.gd", "shell.gd"], "game_arcade3d.gd", ["arcade_core.gd", "tune.gd"])
    return {"id": "arcade3d", "title": title, "genre": "real-time 3D action", "params": params, "tuning": tuning}


# ---------------------------------------------------------------- G: volley (3D beach volleyball tournament)
def build_volley(uni, out_dir, params, tuning=None):
    files = {"data/volley.gd": gd_const("DATA", {"params": params})}
    title = f"{uni['name']}: Beach Volley"
    assemble(out_dir, "volley", title, uni, files, ["kernel.gd", "shell.gd"], "game_volley.gd", ["volley_core.gd", "tune_volley.gd"])
    return {"id": "volley", "title": title, "genre": "3D sports tournament", "params": params, "tuning": tuning}


# ---------------------------------------------------------------- G: splash (top-down water-balloon fight)
def build_splash(uni, out_dir, params, tuning=None):
    files = {"data/splash.gd": gd_const("DATA", {"params": params})}
    title = f"{uni['name']}: Splash"
    assemble(out_dir, "splash", title, uni, files, ["kernel.gd", "shell.gd"], "game_splash.gd", ["splash_core.gd", "tune_splash.gd"])
    return {"id": "splash", "title": title, "genre": "top-down water-balloon battle", "params": params, "tuning": tuning}
