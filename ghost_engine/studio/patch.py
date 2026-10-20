"""Post-release patch of archived games: copy the current template into the archived project, re-run the verification gate for those games,
update screenshots and the manifest, and record the patch honestly. Usage: python -m studio.patch cycle_004 splash volley"""
import json, os, shutil, sys
from . import verify, games as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = {"splash": "game_splash.gd", "volley": "game_volley.gd", "steward": "game_steward.gd", "concept_campaign": "game_concept.gd",
             "arcade": "game_arcade.gd", "arcade3d": "game_arcade3d.gd", "cordon": "game_contain.gd", "artillery": "game_artillery.gd", "bastion": "game_bastion.gd"}


def patch(cycle, ids, note):
    base = os.path.join(ROOT, "archive", cycle)
    man = json.load(open(os.path.join(base, "manifest.json")))
    for gid in ids:
        proj = os.path.join(base, "games", gid)
        shutil.copy(os.path.join(G.TPL, TEMPLATES[gid]), os.path.join(proj, "game.gd"))
        game = [g for g in man["games"] if g["id"] == gid][0]
        if gid == "steward":
            game["data"] = json.load(open(os.path.join(ROOT, "evidence", "steward_data.json"))) if False else game.get("data")
        shots_dir = os.path.join(base, "evidence", gid)
        rep = verify.verify_game(game, proj, shots_dir)
        man["verification"][gid] = rep
        man.setdefault("patches", []).append({"game": gid, "note": note, "checks_after": rep["checks"]})
        print(gid, {k: ("PASS" if v else "FAIL") for k, v in rep["checks"].items()})
    man["released"] = [g["id"] for g in man["games"] if man["verification"][g["id"]]["released"]]
    json.dump(man, open(os.path.join(base, "manifest.json"), "w"), indent=1)
    for d, _s, files in os.walk(os.path.join(base, "games")):
        if ".godot" in d:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    patch(sys.argv[1], sys.argv[2:], "visual polish: neutral bumpers / sand colour (found in screenshot review after release)")
