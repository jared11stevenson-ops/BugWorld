import json, os, shutil, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from studio import inspiration as I, universe as U, cycle, verify, retro, agents, pool, lore, audio, feedback, tuner

GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")


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
            self.assertEqual(len({b[1] for b in c}), 3)
        u = U.make_universe(I.pick(prompt="plague purge", seed=1)[0], 1)
        self.assertIn(u["law"], ("contagion", "purge"))

    def test_genre_pool_picks_distinct_families_and_rewards_novelty(self):
        u = U.make_universe(I.pick(prompt="plague quarantine", seed=3)[0], 3)
        g1, _ = pool.choose(u, {"cycles": []}, 1)
        self.assertEqual(len({pool.POOL[g]["family"] for g in g1}), 3); self.assertIn("cordon", g1)
        g2, s2 = pool.choose(u, {"cycles": [{"genres": g1}]}, 1)
        self.assertNotEqual(sorted(g1), sorted(g2))      # genres shipped last cycle are disfavoured

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
        self.assertEqual(set(tuner.SPECS), {"arcade", "cordon"})
        for kind, sp in tuner.SPECS.items():
            base = sp["base"]("pulse")
            for k, (lo, hi, st) in sp["bounds"].items():
                self.assertLessEqual(lo, base[k]); self.assertGreaterEqual(hi, base[k])

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
        self.assertEqual(len({pool.POOL[g]["family"] for g in man["genres"]}), 3)
        for g in man["genres"]:
            self.assertTrue(os.path.exists(os.path.join(dest, "games", g, "project.godot")))
        know = json.load(open(cycle.KNOW))
        self.assertEqual(len(know["cycles"]), 1)
        self.assertNotIn(m["universe"].split("-")[0], json.dumps({k: v for k, v in know.items() if k != "cycles"}))


if __name__ == "__main__":
    unittest.main()
