import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ghost.foundry import dsl, agents as A, seeds as S, metrics as M, grammar as G, loop as L, compile_godot as CG, replay
import random

ROOT = os.path.join(os.path.dirname(__file__), "..")
GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")


class DSL(unittest.TestCase):
    def test_seeds_valid_and_deterministic(self):
        for sp in S.all_seeds():
            self.assertEqual(dsl.validate(sp), [])
            a = A.play(sp, 8, 7, 5); b = A.play(sp, 8, 7, 5)
            self.assertEqual(dsl.match_digest(sp, a), dsl.match_digest(sp, b))

    def test_validation_rejects_bad_specs(self):
        sp = S.slugfest(); sp["actions"][0]["cond"] = [">=", ["v", "me", "energy"], 1]
        self.assertTrue(dsl.validate(sp))
        sp = S.slugfest(); sp["actions"][1]["fx"].append(["+=", "me", "nonexistent", 1])
        self.assertTrue(dsl.validate(sp))
        sp = S.slugfest(); sp["end"] = []
        self.assertTrue(dsl.validate(sp))

    def test_truncating_division(self):
        self.assertEqual((dsl.tdiv(-7, 2), dsl.tdiv(7, -2), dsl.tdiv(7, 2), dsl.tdiv(5, 0)), (-3, -3, 3, 0))

    def test_simultaneous_resolution(self):
        sp = S.slugfest(); m = dsl.new_match(sp, 1)
        dsl.step(sp, m, 0, 0)   # both strike: both lose 6 hp, both gain energy
        self.assertEqual((m["p"][0]["hp"], m["p"][1]["hp"]), (34, 34))

    def test_illegal_action_falls_back(self):
        sp = S.slugfest(); m = dsl.new_match(sp, 1); m["p"][0]["energy"] = 0
        self.assertEqual(dsl.sanitize(sp, m, 0, 2), 0)

    def test_branching_matches_alternate_history(self):
        sp = S.slugfest(); m = dsl.new_match(sp, 3)
        dsl.step(sp, m, 0, 1)
        b = dsl.clone_match(m)
        dsl.step(sp, m, 1, 0); dsl.step(sp, b, 1, 0)
        self.assertEqual(dsl.match_digest(sp, m), dsl.match_digest(sp, b))
        c = dsl.clone_match(m); dsl.step(sp, m, 0, 0); dsl.step(sp, c, 3, 0)
        self.assertNotEqual(dsl.match_digest(sp, m), dsl.match_digest(sp, c))


class RedTeamRegressions(unittest.TestCase):
    """Each case is a defect reported by the red-team agent (foundry_agents/redteam_report.md), now fixed."""
    def load(self, name):
        return json.load(open(os.path.join(ROOT, "foundry_agents", name)))

    def test_set_effect_removed_so_resolution_cannot_favour_a_seat(self):
        self.assertTrue(dsl.validate(self.load("redteam_seat.json")))

    def test_rnd_in_end_rules_and_act_in_conds_rejected(self):
        self.assertTrue(dsl.validate(self.load("redteam_inert_rnd.json")))
        sp = S.slugfest(); sp["actions"][2]["cond"] = ["==", ["act", "opp"], 1]
        self.assertTrue(any("cond" in e for e in dsl.validate(sp)))

    def test_validate_never_raises_on_malformed_input(self):
        for bad in ("x", [], {"vars": 5}, dict(S.slugfest(), actions=["str", "str"]), dict(S.slugfest(), max_rounds=3.5),
                    dict(S.slugfest(), name=["list"])):
            self.assertTrue(dsl.validate(bad))

    def test_expression_budget_and_int_saturation(self):
        sp = S.slugfest(); e = 1
        for _ in range(30):
            e = ["+", e, 1]
        sp["actions"][0]["fx"] = [["+=", "me", "energy", e]]
        self.assertTrue(any("nodes" in x for x in dsl.validate(sp)))
        self.assertEqual(dsl.sat(10**12), 10**6)

    def test_decoy_and_luck_games_are_flagged(self):
        self.assertIn("misleading_value", M.evaluate(self.load("redteam_decoy.json"), 1, 6)["flags"])
        self.assertIn("luck_dominated", M.evaluate(self.load("redteam_dice.json"), 1, 6)["flags"])

    def test_always_action_baseline_is_order_invariant_for_sprint(self):
        import itertools
        base = S.sprint(); verdicts = set()
        for perm in [(0, 1, 2, 3), (2, 1, 0, 3), (3, 2, 1, 0)]:
            sp = json.loads(json.dumps(base)); acts = [base["actions"][i] for i in perm]
            inv = {old: new for new, old in enumerate(perm)}
            def fix(e):
                if isinstance(e, list) and e:
                    if e[0] == "==" and isinstance(e[1], list) and e[1][0] == "act" and isinstance(e[2], int):
                        e[2] = inv[e[2]]
                    for x in e[1:]: fix(x)
            sp["actions"] = json.loads(json.dumps(acts))
            for a in sp["actions"]:
                for f in a["fx"]: fix(f[3])
            sp["actions"][0]["cond"] = 0 if sp["actions"][0]["cond"] == 0 else sp["actions"][0]["cond"]
            if dsl.validate(sp):
                continue
            verdicts.add(tuple(M.evaluate(sp, 1, 6)["flags"]))
        self.assertEqual(len(verdicts), 1, verdicts)


class Foundry(unittest.TestCase):
    def test_grammar_specs_always_valid_incl_mutants(self):
        rnd = random.Random(4)
        for i in range(80):
            sp, me = G.random_spec(rnd, f"t{i}")
            self.assertEqual(dsl.validate(sp), [], sp)
            for _ in range(3):
                sp, me = G.mutate(sp, me, rnd, f"m{i}")
                self.assertEqual(dsl.validate(sp), [])

    def test_metrics_flag_degenerate_concept(self):
        sp = S.slugfest()
        sp["actions"][0]["fx"] = [["+=", "opp", "hp", -40]]     # strike kills instantly: degenerate one-round game
        r = M.evaluate(sp, 1, 6)
        self.assertIn("no_interaction", r["flags"])

    def test_loop_reproducible_and_learns(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = L.Foundry(d1, seed=3, workers=1, use_inbox=False).run(2, 16, quiet=True)
            b = L.Foundry(d2, seed=3, workers=1, use_inbox=False).run(2, 16, quiet=True)
            self.assertEqual(sorted(c["hash"] for c in a.cands.values()), sorted(c["hash"] for c in b.cands.values()))
            self.assertTrue(a.failures and a.archive)
            self.assertTrue(a.memory["atoms"])
            self.assertTrue(os.path.exists(os.path.join(d1, "failures.json")))

    def test_inbox_ingests_external_specs(self):
        with tempfile.TemporaryDirectory() as inbox, tempfile.TemporaryDirectory() as d:
            sp = S.sprint(); sp["id"] = "ext1"; sp["name"] = "External"
            sp["actions"][0]["fx"][0][3] = 2
            json.dump([sp], open(os.path.join(inbox, "tester.json"), "w"))
            old = L.INBOX; L.INBOX = inbox
            try:
                f = L.Foundry(d, seed=1, workers=1).run(0, 4, quiet=True)
            finally:
                L.INBOX = old
            self.assertTrue(any(c["proposer"] == "agent:tester" for c in f.cands.values()))

    def test_loop_beats_random_control_small(self):
        from ghost.foundry import run_discovery as RD
        with tempfile.TemporaryDirectory() as d:
            f = L.Foundry(d, seed=1, workers=2, use_inbox=False).run(5, 32, quiet=True)
        viable = sum(1 for c in f.cands.values() if c["valid"] and not c["flags"]) / len(f.cands)
        ctl = RD.control_random(len(f.cands), 1, 6)
        self.assertGreater(viable, ctl["viable"] / ctl["evals"])


@unittest.skipUnless(os.path.exists(GODOT), "Godot binary not available")
class ConceptTwin(unittest.TestCase):
    def run_godot(self, *args):
        return subprocess.run([GODOT, "--headless", "--path", os.path.join(ROOT, "godot"), *args], capture_output=True, text=True, timeout=600)

    def test_concept_parity(self):
        r = self.run_godot("--script", "res://tests/concept_parity.gd")
        line = [l for l in r.stdout.splitlines() if l.startswith("CONCEPT_PARITY")]
        self.assertTrue(line, r.stdout[-1000:])
        res = json.loads(line[0].split(" ", 1)[1])
        self.assertEqual(res["fails"], 0); self.assertGreater(res["checks"], 200)

    def test_arena_sessions_replay_in_python(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "s.json")
            r = self.run_godot("--script", "res://tests/concept_ui_smoke.gd", "--", out)
            self.assertIn("CONCEPT_UI", r.stdout, r.stdout[-800:])
            res = replay.verify(out)
            self.assertEqual(res["mismatches"], 0, res); self.assertGreaterEqual(res["sessions"], 9)


if __name__ == "__main__":
    unittest.main()
