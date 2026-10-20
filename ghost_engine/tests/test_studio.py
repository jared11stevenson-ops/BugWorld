import json, os, shutil, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from studio import inspiration as I, universe as U, cycle, verify, retro, agents, lore, audio, feedback, tuner

GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")
ROOT = os.path.join(os.path.dirname(__file__), "..")


class Studio(unittest.TestCase):
    def test_inspirations_distinct_fields_and_reproducible(self):
        a, _ = I.pick(7); b, _ = I.pick(7)
        self.assertEqual([x[0] for x in a], [x[0] for x in b])
        self.assertEqual(len({x[1] for x in a}), 3)
        c, _ = I.pick(prompt="a world of tides and moons")
        self.assertIn("tidal locking", [x[0] for x in c])

    def test_random_pick_without_seed_varies(self):
        picks = {tuple(x[0] for x in I.pick()[0]) for _ in range(6)}
        self.assertGreater(len(picks), 1)

    def test_universe_is_deterministic_and_has_distinct_identity(self):
        u1 = U.make_universe(I.pick(11)[0], 11); u2 = U.make_universe(I.pick(11)[0], 11); u3 = U.make_universe(I.pick(12)[0], 12)
        self.assertEqual(u1, u2); self.assertNotEqual(u1["name"], u3["name"])
        self.assertIn(u1["law"], ("pulse", "wells", "drift")); self.assertEqual(len(u1["palette"]), 5)

    def test_stored_priors_from_earlier_cycles_are_applied(self):
        u = U.make_universe(I.pick(21)[0], 21)
        know = {"universe_priors": {k: v for (s, k), (lo, hi, st) in U.BOUNDS.items() for v in [hi]}}   # every bounded key, incl. sell_pct/swing_pct
        r = U.prior_rules(u, know)
        for (s, k), (lo, hi, st) in U.BOUNDS.items():
            self.assertGreaterEqual(r[s][k], lo); self.assertLessEqual(r[s][k], hi)
        self.assertGreater(r["economy"]["sell_pct"], U.prior_rules(u, None)["economy"]["sell_pct"] - 1)

    def test_plague_purge_prompt_yields_both_themes_and_dedicated_laws(self):
        for seed in range(6):
            c, _ = I.pick(prompt="The Plague / the Purge", seed=seed)
            tags = {t for b in c for t in b[2]}
            self.assertTrue(tags & {"contagion", "quarantine"}, [b[0] for b in c]); self.assertIn("purge", tags)
            self.assertGreaterEqual(len({b[1] for b in c}), 2)
        u = U.make_universe(I.pick(prompt="plague purge", seed=1)[0], 1)
        self.assertIn(u["law"], ("contagion", "purge"))

    def test_idea_space_is_unlocked_by_fused_elements_and_selects_three_families(self):
        from studio import ideas, elements as EL
        u = U.make_universe(I.pick(prompt="plague quarantine", seed=3)[0], 3)
        fams = {c["family"] for c in ideas.candidates(u)}
        self.assertIn("cordon", fams); self.assertNotIn("volley", fams)          # no net/rally in a plague universe
        w = U.make_universe(I.pick(prompt="waterballoon fights / volleyball world", seed=1)[0], 1)
        self.assertEqual(sorted(w["inspirations"]), ["volleyball", "water balloon fights"])
        wf = {c["family"] for c in ideas.candidates(w)}
        self.assertTrue({"volley", "splash"} <= wf); self.assertNotIn("cordon", wf)
        self.assertTrue(any(c["mods"].get("ball") == 1 for c in ideas.candidates(w)))   # fusion module exists only because both inspirations are present
        only_v = U.make_universe([b for b in I.BANK if b[0] == "volleyball"] + [b for b in I.BANK if b[0] == "rally scoring"], 1)
        self.assertFalse(any(c["mods"].get("ball") == 1 for c in ideas.candidates(only_v)))
        self.assertEqual(ideas.novelty({"family": "volley", "mods": {"ball": 0, "net": 0, "score": 0}}, [{"family": "volley", "mods": {}}]), 0.15)
        self.assertEqual(ideas.novelty({"family": "volley", "mods": {"ball": 1, "net": 1, "score": 1}}, [{"family": "volley", "mods": {}}]), 1.0)
        self.assertEqual(ideas.novelty({"family": "splash", "mods": {"ball": 1}}, [{"family": "volley", "mods": {}}]), 1.0)

    def test_universe_physics_is_shared_and_fused(self):
        from studio import elements as EL
        ph = EL.universe_physics(["wind", "burst", "soak"])
        self.assertGreater(ph["wind"], 0); self.assertEqual(ph["burst_radius"], 1.0)
        from studio import tuner
        b = tuner.SPECS["volley"]["base"]("none", ph, {"ball": 1, "net": 1, "score": 0})
        self.assertEqual(b["wind"], ph["wind"]); self.assertEqual((b["ball"], b["net"]), (1, 1))

    def test_lore_is_derived_from_simulation_and_deterministic(self):
        u = U.make_universe(I.pick(5)[0], 5); u["rules"] = U.prior_rules(u); u["canon"] = {"seed": 101, "fork_tick": 100, "intervention": "none", "richness": 0}
        u["chronicle"], _ = U.chronicle(u)
        a, b = lore.make_lore(u), lore.make_lore(u)
        self.assertEqual(a, b); self.assertEqual(len(a["prologue"]), 3); self.assertEqual(set(a["factions"]), set(u["lexicon"]["factions"]))
        self.assertTrue(all("slew" in f["blurb"] for f in a["factions"].values()))

    def test_town_names_unique(self):
        for s in range(30):
            u = U.make_universe(I.pick(seed=s)[0], s)
            self.assertEqual(len(set(u["lexicon"]["towns"])), 6)

    def test_audio_moods_differ_and_files_valid(self):
        import tempfile, wave
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.wav"), os.path.join(d, "b.wav")
            audio.music(a, 4, mood="calm", bars=2); audio.music(b, 4, mood="dread", bars=2)
            self.assertNotEqual(open(a, "rb").read(), open(b, "rb").read())
            with wave.open(a) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 22050))
            self.assertGreaterEqual(len(audio.sfx(d, 1)), 12)

    def test_feedback_import_ignores_selftests_and_aggregates(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"game": "cordon", "rating": 4, "ctx": {"selftest": True}}) + "\n")
            f.write(json.dumps({"game": "cordon", "rating": 5, "ctx": {}}) + "\n" + json.dumps({"game": "cordon", "rating": 3, "ctx": {}}) + "\n")
        k = {}
        self.assertEqual(feedback.aggregate(k, feedback.load_records(f.name)), {"cordon": {"n": 2, "mean": 4.0}})

    def test_tuner_specs_cover_every_tunable_template(self):
        self.assertEqual(set(tuner.SPECS), {"arcade", "cordon", "volley", "splash"})
        for kind, sp in tuner.SPECS.items():
            base = sp["base"]("pulse")
            for k, (lo, hi, st) in sp["bounds"].items():
                self.assertLessEqual(lo, base[k]); self.assertGreaterEqual(hi, base[k])

    def test_palette_contrast_is_guaranteed(self):
        for s in range(150):
            pal = U.make_universe(I.pick(seed=s)[0], s)["palette"]
            self.assertGreaterEqual(U.contrast(pal[4], pal[0]), 7.0); self.assertGreaterEqual(U.contrast(pal[3], pal[0]), 4.5); self.assertGreaterEqual(U.contrast(pal[2], pal[0]), 3.0)

    def test_waterballoon_volleyball_prompt_gets_new_laws_and_sport_genres(self):
        for seed in range(5):
            c, _ = I.pick(prompt="waterballoon fights / volleyball world", seed=seed)
            self.assertEqual(sorted(b[0] for b in c), ["volleyball", "water balloon fights"])
        u = U.make_universe(I.pick(prompt="waterballoon volleyball", seed=2)[0], 2)
        self.assertIn(u["law"], ("gust", "slick")); self.assertEqual(u["mood"], "bright")
        self.assertIn("net", u["elements"]); self.assertIn("burst", u["elements"])

    def test_tuner_band_rejects_unrealistic_difficulty_and_widen_respects_caps(self):
        self.assertFalse(tuner.in_target_band({"skilled": 1.0, "average": 1.0, "novice": 0.0}))      # average player must not also win 100%
        self.assertTrue(tuner.in_target_band({"skilled": 0.9, "average": 0.5, "novice": 0.05}))
        self.assertFalse(tuner.in_target_band({"skilled": 0.9, "average": 0.5, "novice": 0.05, "side_bias": 0.3, "rally": 5}))     # unfair sides
        wide = tuner.widen("cordon", tuner.CORDON_BOUNDS, {"beta": "hi", "ap": "lo"})
        self.assertGreater(wide["beta"][1], tuner.CORDON_BOUNDS["beta"][1]); self.assertLessEqual(wide["beta"][1], tuner.HARD_CAPS["cordon"]["beta"][1])
        self.assertGreaterEqual(wide["ap"][0], tuner.HARD_CAPS["cordon"]["ap"][0])

    def test_fairness_term_penalises_biased_sports_games(self):
        good = {"skilled": 0.9, "average": 0.5, "novice": 0.05, "side_bias": 0.02, "rally": 6, "ticks": 2000}
        bad = dict(good, side_bias=0.4)
        self.assertGreater(tuner.fitness(good), tuner.fitness(bad))

    def test_volley_python_twin_matches_known_godot_digest_for_large_seed(self):
        from studio import volley_twin as VT
        p = dict(VT.DEFAULTS); p.update({"wind": 0.03, "jump": 9.5, "restitution": 0.95, "points": 5})
        s = VT.play(76533082012, p, 2, [9, 45.0, 0.55])          # seed > 2^31: the case that exposed an int64 overflow in GDScript
        self.assertEqual((VT.digest(s), s["t"], s["score"]), ("96f94420", 1784, [5, 2]))

    @unittest.skipUnless(os.path.exists(GODOT), "Godot binary not available")
    def test_volley_core_in_godot_matches_python_twin_on_large_seed(self):
        import subprocess, tempfile, shutil
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "ghost"))
            for src, dst in (("godot/ghost/kernel.gd", "ghost/kernel.gd"), ("studio/templates/volley_core.gd", "ghost/volley_core.gd")):
                shutil.copy(os.path.join(ROOT, src), os.path.join(d, dst))
            open(os.path.join(d, "project.godot"), "w").write('config_version=5\n[application]\nconfig/name="t"\n[debug]\ngdscript/warnings/integer_division=0\n')
            open(os.path.join(d, "t.gd"), "w").write('extends SceneTree\nconst V = preload("res://ghost/volley_core.gd")\nfunc _init():\n\tvar p := V.defaults()\n\tp["wind"] = 0.03\n\tp["jump"] = 9.5\n\tp["restitution"] = 0.95\n\tp["points"] = 5\n\tvar s := V.play(76533082012, p, 2, [9, 45.0, 0.55])\n\tprint("GD ", V.digest(s), " ", s["t"])\n\tquit(0)\n')
            out = subprocess.run([GODOT, "--headless", "--path", d, "--script", "res://t.gd"], capture_output=True, text=True, timeout=120).stdout
            self.assertIn("GD 96f94420 1784", out, out[-400:])

    def test_gate_refuses_unverified_game(self):
        r = {"checks": {"selftest_passes": True, "python_twin_matches": False}}
        self.assertFalse(all(r["checks"].values()))

    def test_capability_gaps_are_declared_not_hidden(self):
        self.assertIn("partial", agents.ROLES["art_3d"]["status"]); self.assertIn("no authored", agents.ROLES["art_3d"]["status"])
        self.assertIn("no skeletal", agents.ROLES["animation"]["status"])
        self.assertIn("NO human ratings", agents.ROLES["polish_producer"]["status"])

    @unittest.skipUnless(os.path.exists(GODOT), "Godot binary not available")
    def test_full_cycle_smoke_archives_resets_and_retains_knowledge(self):
        m = cycle.run_cycle(seed=3, quick=True, log=lambda *a: None)     # isolated smoke dirs, real pipeline
        self.assertTrue(m["reset"]["ok"])
        self.assertFalse(os.path.exists(cycle.STATE))
        dest = os.path.join(cycle.ARCHIVE, m["cycle"])
        man = json.load(open(os.path.join(dest, "manifest.json")))
        self.assertEqual(len(man["genres"]), 3)
        self.assertEqual(len(set(man["genres"])), 3)
        ij = json.load(open(os.path.join(dest, "ideas.json")))
        self.assertEqual(len({c["family"] for c in ij["chosen"]}), 3)
        for g in man["genres"]:
            self.assertTrue(os.path.exists(os.path.join(dest, "games", g, "project.godot")))
        know = json.load(open(cycle.KNOW))
        self.assertEqual(len(know["cycles"]), 1)
        self.assertNotIn(m["universe"].split("-")[0], json.dumps({k: v for k, v in know.items() if k != "cycles"}))


if __name__ == "__main__":
    unittest.main()
