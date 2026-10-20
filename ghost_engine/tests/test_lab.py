import json, os, subprocess, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ghost.kernel import rules as RU, world as W
from ghost.lab import tournament as T, evolve as E, causal as CA
from ghost.compiler import compile as CC

ROOT = os.path.join(os.path.dirname(__file__), "..")
GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")


class Lab(unittest.TestCase):
    def test_tournament_is_reproducible(self):
        a = T.metrics(RU.BASELINE["combat"], 3, 6)
        b = T.metrics(RU.BASELINE["combat"], 3, 6)
        self.assertEqual(a["matrix"], b["matrix"])
        self.assertEqual(a["action_shares"], b["action_shares"])

    def test_baseline_has_measurable_dominant_strategy(self):
        m = T.metrics(RU.BASELINE["combat"], 1, 12)
        self.assertGreaterEqual(m["dominance"], 0.9)
        self.assertEqual(m["top_policy"], "bruiser")
        self.assertLess(m["live_actions"], 4)

    def test_evolution_is_elitist_and_reproducible(self):
        _, h1, _ = E.evolve(seed=5, generations=3, pop=8, fights=4)
        _, h2, _ = E.evolve(seed=5, generations=3, pop=8, fights=4)
        self.assertEqual([r["best"] for r in h1], [r["best"] for r in h2])
        bests = [r["best"] for r in h1]
        self.assertEqual(bests, sorted(bests))

    def test_ledger_detector_fires_on_planted_mint_bug(self):
        orig = W._work
        def leaky(s, n):          # plants an exploit: free gold that bypasses the ledger
            orig(s, n); n["gold"] += 5
        W._work = leaky
        try:
            s = W.new_world(3, RU.BASELINE); W.run(s, 100)
            self.assertNotEqual(W.conservation_error(s), 0)
            self.assertTrue(CA.FLAGS["ledger_violation"]({}, CA.world_metrics(s)))
        finally:
            W._work = orig

    def test_stalemate_detector_fires_on_degenerate_rules(self):
        c = dict(RU.BASELINE["combat"]); c.update(guard_reduce_pct=90, guard_counter_pct=0, fatigue_pct=0)
        m = T.metrics(c, 1, 8)
        self.assertGreater(m["stalemate"], 0.0)

    def test_counterfactual_branch_is_paired_and_diverges(self):
        r = CA.counterfactual(RU.BASELINE, range(1, 4), 50, 60, "kill_deadliest")
        self.assertEqual(r["n"], 3)
        self.assertGreater(r["diverged_fraction"], 0)

    def test_compile_gate_rejects_unvalidated_mechanic(self):
        bad = {"baseline_v0": {"metrics": {"dominance": .9, "stalemate": 0, "live_actions": 2}},
               "cand": {"paired_gain_mean": -0.1, "seeds_improved": 2, "metrics": {"dominance": .95, "stalemate": .3, "live_actions": 2}}}
        self.assertFalse(all(ok for _, ok in CC.gate("cand", bad)))


@unittest.skipUnless(os.path.exists(GODOT), "Godot binary not available (set GODOT_BIN)")
class Godot(unittest.TestCase):
    def run_godot(self, script):
        return subprocess.run([GODOT, "--headless", "--path", os.path.join(ROOT, "godot"), "--script", script],
                              capture_output=True, text=True, timeout=600)

    def test_parity_with_golden_traces(self):
        r = self.run_godot("res://tests/parity_test.gd")
        line = [l for l in r.stdout.splitlines() if l.startswith("PARITY_RESULT")]
        self.assertTrue(line, r.stdout[-1500:])
        res = json.loads(line[0].split(" ", 1)[1])
        self.assertEqual(res["fails"], 0, r.stdout[-1500:])
        self.assertGreater(res["checks"], 100)

    def test_fuzz_parity_python_vs_godot(self):
        from ghost import twin
        res = twin.parity(8, 250)
        self.assertEqual(res["mismatches"], 0, res)

    def test_ui_smoke(self):
        r = self.run_godot("res://tests/ui_smoke.gd")
        self.assertIn("UI_SMOKE", r.stdout, r.stdout[-1500:])
        self.assertEqual(json.loads(r.stdout.split("UI_SMOKE ", 1)[1].splitlines()[0])["fails"], 0, r.stdout[-1500:])


if __name__ == "__main__":
    unittest.main()
