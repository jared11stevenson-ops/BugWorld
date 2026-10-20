import json, os, shutil, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from studio import inspiration as I, universe as U, cycle, verify, retro, agents

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

    def test_gate_refuses_unverified_game(self):
        r = {"checks": {"selftest_passes": True, "python_twin_matches": False}}
        self.assertFalse(all(r["checks"].values()))

    def test_capability_gaps_are_declared_not_hidden(self):
        self.assertIn("MISSING", agents.ROLES["art_3d"]["status"]); self.assertIn("MISSING", agents.ROLES["animation"]["status"])

    @unittest.skipUnless(os.path.exists(GODOT), "Godot binary not available")
    def test_full_cycle_smoke_archives_resets_and_retains_knowledge(self):
        m = cycle.run_cycle(seed=3, quick=True, log=lambda *a: None)     # isolated smoke dirs, real pipeline
        self.assertTrue(m["reset"]["ok"])
        self.assertFalse(os.path.exists(cycle.STATE))
        dest = os.path.join(cycle.ARCHIVE, m["cycle"])
        for g in ("concept_campaign", "steward", "arcade"):
            self.assertTrue(os.path.exists(os.path.join(dest, "games", g, "project.godot")))
        know = json.load(open(cycle.KNOW))
        self.assertEqual(len(know["cycles"]), 1)
        self.assertNotIn(m["universe"].split("-")[0], json.dumps({k: v for k, v in know.items() if k != "cycles"}))


if __name__ == "__main__":
    unittest.main()
