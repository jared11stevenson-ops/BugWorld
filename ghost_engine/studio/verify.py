"""Quality verification. A game is 'released' only if every check passes. Checks run the real Godot project headless:
self-test through the game's own code paths, no script errors, assets present, screenshots non-blank, and Python twins of the sim."""
import json, os, subprocess
from ghost.kernel import world as W
from ghost.kernel.timeline import Timeline
from ghost.foundry import dsl, replay as R

GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")
NOISE = ("ALSA", "audio_driver", "audio drivers", "dummy driver", "Godot Engine v", "init_output_device")


def godot(project, args, timeout=900, display=False):
    cmd = [GODOT, "--headless", "--path", project] + args
    if display:
        cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", GODOT, "--rendering-driver", "opengl3", "--path", project] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout + "\n" + r.stderr


def script_errors(out):
    return [l for l in out.splitlines() if ("SCRIPT ERROR" in l or "Parse Error" in l or l.startswith("ERROR:")) and not any(n in l for n in NOISE)]


def selftest(project):
    out = godot(project, ["--script", "res://tests/selftest.gd"])
    line = [l for l in out.splitlines() if l.startswith("GAME_SELFTEST ")]
    res = json.loads(line[0].split(" ", 1)[1]) if line else {"ok": False, "reason": "no GAME_SELFTEST output", "tail": out[-600:]}
    return res, script_errors(out)


def shots(project, out_dir):
    out = godot(project, ["--script", "res://tests/shot.gd", "--", out_dir], display=True, timeout=300)
    p = os.path.join(out_dir, "shots.json")
    if not os.path.exists(p):
        return {"ok": False, "reason": "no screenshots", "tail": out[-400:]}
    d = json.load(open(p))
    d["ok"] = d["title_colors"] >= 6 and d["play_colors"] >= 6 and os.path.getsize(os.path.join(out_dir, "title.png")) > 4000 and os.path.getsize(os.path.join(out_dir, "play.png")) > 4000
    return d


def twin_concept(project, records):
    camp = json.load(open(os.path.join(project, "data", "campaign.json")))
    specs = {c["spec"]["id"]: c["spec"] for c in camp["chapters"]}
    bad = []
    for r in records:
        got = R.replay(r, specs[r["concept"]])
        if not got or got["digest"] != r["digest"] or got["winner"] != r["winner"]:
            bad.append(r["seed"])
    return {"sessions": len(records), "mismatches": len(bad)}


def twin_steward(data, res):
    f = data["player_faction"]
    tl = Timeline(W.new_world(data["seed"], data["rules"]))
    tl.step(data["start_tick"])
    def poorest():
        best = None
        for n in tl.s["npcs"]:
            if n["alive"] and n["faction"] == f and (best is None or n["gold"] < tl.s["npcs"][best]["gold"]):
                best = n["id"]
        return best
    def enemy():
        best = None
        for g in range(tl.s["n_fac"]):
            if g != f and tl.s["rel"][f][g] < 0 and (best is None or tl.s["rel"][f][g] < tl.s["rel"][f][best]):
                best = g
        return best
    score = 0
    for act in res["script"]:
        a = act[0]
        if a == "bless":
            tl.intervene("give_gold", [poorest(), 300])
        elif a == "peace":
            tl.intervene("set_rel", [f, enemy(), 0])
        elif a == "calm":
            tl.intervene("set_rule", [max(1, tl.s["rules"]["world"]["aggro_pct"] - 2)], path="world.aggro_pct")
        elif a == "end":
            tl.step(data["epoch_ticks"])
            alive = [n for n in tl.s["npcs"] if n["alive"] and n["faction"] == f]
            score += len(alive) * 10 + sum(n["gold"] for n in alive) // 50
    return {"digest_match": W.digest_hex(tl.s) == res["final_digest"], "tick_match": tl.tick == res["final_tick"], "score_match": score == res["bot_score"],
            "python_score": score, "godot_score": res["bot_score"]}


def verify_game(game, project, out_dir):
    """Returns {"checks": {name: bool}, "details": {...}, "released": bool}"""
    os.makedirs(out_dir, exist_ok=True)
    st, errs = selftest(project)
    checks = {"selftest_passes": bool(st.get("ok")), "no_script_errors": not errs}
    details = {"selftest": {k: v for k, v in st.items() if k not in ("records", "script")}, "script_errors": errs[:5]}
    files = ["project.godot", "main.tscn", "game.gd", "data/universe.json"] + [f"audio/{n}.wav" for n in ("click", "hit", "pickup", "win", "lose", "pulse", "music")]
    checks["assets_present"] = all(os.path.exists(os.path.join(project, f)) for f in files)
    sh = shots(project, os.path.join(out_dir, "screens"))
    checks["screenshots_nonblank"] = bool(sh.get("ok"))
    details["screenshots"] = {k: v for k, v in sh.items() if k != "tail"}
    if game["id"] == "concept_campaign" and "records" in st:
        t = twin_concept(project, st["records"])
        checks["python_twin_matches"] = t["mismatches"] == 0 and t["sessions"] > 0
        details["twin"] = t
    elif game["id"] == "steward" and "script" in st:
        t = twin_steward(game["data"], st)
        checks["python_twin_matches"] = t["digest_match"] and t["tick_match"] and t["score_match"]
        details["twin"] = t
    elif game["id"] == "arcade":
        tn = game.get("tuning") or {}
        hb = tn.get("holdout_best", {})
        checks["difficulty_tuned_on_holdout"] = bool(hb) and hb.get("skilled", 0) >= 0.3 and hb.get("skilled", 0) - hb.get("novice", 1) >= 0.2
        details["tuning_holdout"] = hb
    return {"checks": checks, "details": details, "released": all(checks.values())}
