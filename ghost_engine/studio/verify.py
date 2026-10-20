"""Quality verification. A game is 'released' only if every check passes. Checks run the real Godot project headless:
self-test through the game's own code paths, no script errors, assets present, screenshots non-blank, and Python twins of the sim."""
import json, os, subprocess
from ghost.kernel import world as W
from ghost.kernel.timeline import Timeline
from ghost.foundry import dsl, replay as R
from ghost.kernel import rng as RNG

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
    try:
        out = godot(project, ["--script", "res://tests/selftest.gd"], timeout=420)      # hard cap: a hung game must fail, not stall the studio
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "selftest timed out"}, ["selftest timed out"]
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


def twin_cordon(game, res):
    """Python port of contain_core.gd; replays the bot's winning action script and compares the final state digest."""
    p = dict({"nodes": 12, "days": 30, "beta": 45, "flow": 6, "mort": 8, "rec": 12, "ap": 3, "meds": 8, "treat": 150, "q_days": 4,
              "seeds": 2, "win_pct": 55, "purge_cap": 15, "purge_ap": 2, "leak": 25, "jump": 4}, **{k: int(v) for k, v in game["params"].items()})
    s = {"rng": RNG.seed_state(res["seed"])}
    n = p["nodes"]
    X, Y, POP, S_, I_, R_, D_, Q, B = ([] for _ in range(9))
    for i in range(n):
        X.append(RNG.rand(s, 1000)); Y.append(RNG.rand(s, 1000))
        pop = 300 + RNG.rand(s, 900)
        POP.append(pop); S_.append(pop); I_.append(0); R_.append(0); D_.append(0); Q.append(0); B.append(0)
    total = sum(POP)
    d2 = lambda i, j: (X[i] - X[j]) ** 2 + (Y[i] - Y[j]) ** 2
    edges = []
    def add(a, b):
        if [a, b] not in edges:
            edges.append([a, b])
    for i in range(n):
        best = sorted((d2(i, j), j) for j in range(n) if j != i)
        for k in range(2):
            j = best[k][1]; add(min(i, j), max(i, j))
    def comps():
        comp = [-1] * n; c = 0
        for i in range(n):
            if comp[i] != -1:
                continue
            comp[i] = c; stack = [i]
            while stack:
                u = stack.pop()
                for a, b in edges:
                    v = b if a == u else (a if b == u else -1)
                    if v >= 0 and comp[v] == -1:
                        comp[v] = c; stack.append(v)
            c += 1
        return comp
    while True:
        comp = comps()
        if max(comp) + 1 <= 1:
            break
        bd, bi, bj = 1 << 60, 0, 0
        for i in range(n):
            for j in range(i + 1, n):
                if comp[i] != comp[j] and d2(i, j) < bd:
                    bd, bi, bj = d2(i, j), i, j
        add(bi, bj)
    placed = 0
    while placed < p["seeds"]:
        i = RNG.rand(s, n)
        if I_[i] == 0:
            I_[i] = 20; S_[i] -= 20; placed += 1
    st = {"day": 0, "ap": p["ap"], "meds": p["meds"], "purged": 0, "over": 0, "won": 0, "why": ""}
    def alive_inf():
        return sum(S_[i] + I_[i] + R_[i] for i in range(n)), sum(I_)
    for kind, i in res["script"]:
        if kind == "q":
            if st["over"] == 0 and st["ap"] >= 1 and B[i] == 0:
                st["ap"] -= 1; Q[i] = p["q_days"]
        elif kind == "t":
            if st["over"] == 0 and st["ap"] >= 1 and st["meds"] >= 1 and B[i] == 0 and I_[i] > 0:
                m = min(I_[i], p["treat"]); I_[i] -= m; R_[i] += m; st["meds"] -= 1; st["ap"] -= 1
        elif kind == "p":
            if st["over"] == 0 and st["ap"] >= p["purge_ap"] and B[i] == 0:
                k = S_[i] + I_[i]; st["ap"] -= p["purge_ap"]; D_[i] += k; st["purged"] += k; S_[i] = I_[i] = 0; B[i] = 1
                if st["purged"] * 100 > total * p["purge_cap"]:
                    st["over"] = 1; st["why"] = "conscience"
        else:   # end day
            if st["over"]:
                continue
            new = [0] * n
            for i2 in range(n):
                if B[i2] or I_[i2] == 0:
                    continue
                beta = p["beta"] // 2 if Q[i2] > 0 else p["beta"]
                new[i2] += I_[i2] * S_[i2] * beta // (max(1, POP[i2]) * 100)
            for u, v in edges:
                if B[u] == 0 and B[v] == 0:
                    f = p["flow"] * p["leak"] // 100 if (Q[u] > 0 or Q[v] > 0) else p["flow"]
                    new[v] += I_[u] * f // 100; new[u] += I_[v] * f // 100
            for i2 in range(n):
                if B[i2] == 0 and I_[i2] >= 30:
                    if RNG.rand(s, 100) < p["jump"]:
                        tgt = RNG.rand(s, n)
                        if B[tgt] == 0:
                            new[tgt] += 3
            for i2 in range(n):
                if B[i2]:
                    continue
                inf = min(S_[i2], new[i2]); S_[i2] -= inf
                deaths = rec = 0
                if I_[i2] > 0:
                    deaths = (I_[i2] * p["mort"] + 99) // 100; rec = (I_[i2] * p["rec"] + 99) // 100
                    if deaths + rec > I_[i2]:
                        rec = max(0, I_[i2] - deaths)
                I_[i2] = I_[i2] + inf - deaths - rec; D_[i2] += deaths; R_[i2] += rec
                if Q[i2] > 0:
                    Q[i2] -= 1
            st["day"] += 1; st["ap"] = p["ap"]
            a, inf_t = alive_inf()
            if a * 100 < total * 30:
                st["over"] = 1; st["why"] = "collapse"
            elif inf_t == 0 and st["day"] >= 3:
                st["over"] = 1; st["why"] = "extinguished"
            elif st["day"] >= p["days"]:
                st["over"] = 1; st["why"] = "survived"
            if st["over"] and st["why"] not in ("collapse", "conscience"):
                st["won"] = 1 if a * 100 >= total * p["win_pct"] else 0
                if not st["won"]:
                    st["why"] = "too_many_dead"
    parts = [st["day"], st["ap"], st["meds"], st["purged"], st["over"], st["won"], s["rng"]]
    for i in range(n):
        parts += [S_[i], I_[i], R_[i], D_[i], Q[i], B[i]]
    dg = "%08x" % RNG.fnv32_str(",".join(str(x) for x in parts))
    return {"digest_match": dg == res["final_digest"], "day_match": st["day"] == res["final_day"], "alive_match": alive_inf()[0] == res["final_alive"], "won": st["won"]}


def twin_volley(game, res):
    from . import volley_twin as VT
    p = dict(VT.DEFAULTS)
    for k, v in game["params"].items():
        p[k] = int(v) if k in ("slick", "points", "ai_lag", "serve_pause", "max_ticks") else float(v)
    tw = res["twin"]
    s = VT.play(tw["seed"], p, tw["left_level"], tw["right"])
    return {"digest_match": VT.digest(s) == tw["digest"], "ticks_match": s["t"] == tw["ticks"], "score_match": s["score"] == tw["score"]}


def tuner_band(hb):
    from . import tuner
    return tuner.in_target_band(hb)


def verify_game(game, project, out_dir):
    """Returns {"checks": {name: bool}, "details": {...}, "released": bool}"""
    os.makedirs(out_dir, exist_ok=True)
    st, errs = selftest(project)
    checks = {"selftest_passes": bool(st.get("ok")), "no_script_errors": not errs}
    details = {"selftest": {k: v for k, v in st.items() if k not in ("records", "script")}, "script_errors": errs[:5]}
    files = ["project.godot", "main.tscn", "game.gd", "data/universe.json"] + [f"audio/{n}.wav" for n in ("click", "hit", "pickup", "win", "lose", "pulse", "alarm", "burn", "cure", "infect", "step", "ui_open", "music", "ambient")]
    if st.get("perf_step_us") is not None:
        checks["performance_budget"] = st["perf_step_us"] < 3000.0          # simulation step must stay far below a 16 ms frame
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
    elif game["id"] == "cordon" and "script" in st:
        t = twin_cordon(game, st)
        checks["python_twin_matches"] = t["digest_match"] and t["day_match"] and t["alive_match"] and t["won"] == 1
        details["twin"] = t
        hb = (game.get("tuning") or {}).get("holdout_best", {})
        checks["difficulty_in_target_band"] = bool(hb) and tuner_band(hb)
        details["tuning_holdout"] = hb
    elif game["id"] == "volley" and st.get("twin"):
        t = twin_volley(game, st)
        checks["python_twin_matches"] = all(t.values())
        details["twin"] = t
        hb = (game.get("tuning") or {}).get("holdout_best", {})
        checks["difficulty_in_target_band"] = bool(hb) and tuner_band(hb)
        details["tuning_holdout"] = hb
    elif game["id"] == "splash":
        st2, _e2 = selftest(project)          # determinism across processes: a second run must reproduce the digest
        checks["deterministic_across_runs"] = bool(st.get("deterministic")) and st.get("det_digest") == st2.get("det_digest") and st.get("det_digest") is not None
        details["det_digest"] = [st.get("det_digest"), st2.get("det_digest")]
        hb = (game.get("tuning") or {}).get("holdout_best", {})
        checks["difficulty_in_target_band"] = bool(hb) and tuner_band(hb)
        details["tuning_holdout"] = hb
    elif game["id"] in ("arcade", "arcade3d"):
        tn = game.get("tuning") or {}
        hb = tn.get("holdout_best", {})
        checks["difficulty_in_target_band"] = bool(hb) and tuner_band(hb)
        details["tuning_holdout"] = hb
    return {"checks": checks, "details": details, "released": all(checks.values())}
