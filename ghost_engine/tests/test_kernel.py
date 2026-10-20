import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ghost.kernel import rng as R, rules as RU, world as W, combat as C
from ghost.kernel.timeline import Timeline


def mk(seed=7, **kw):
    return W.new_world(seed, RU.BASELINE, **kw)


class Kernel(unittest.TestCase):
    def test_rng_golden(self):
        st = {"rng": R.seed_state(12345)}
        self.assertEqual([R.rand(st, 1000) for _ in range(5)], [25, 267, 808, 684, 134])

    def test_determinism(self):
        a, b = mk(11), mk(11)
        W.run(a, 300); W.run(b, 300)
        self.assertEqual(W.digest(a), W.digest(b))
        c = mk(12); W.run(c, 300)
        self.assertNotEqual(W.digest(a), W.digest(c))

    def test_gold_conservation(self):
        for seed in range(1, 15):
            s = mk(seed); W.run(s, 400)
            self.assertEqual(W.conservation_error(s), 0, f"seed {seed}")

    def test_world_is_alive(self):
        s = mk(3); W.run(s, 500)
        kinds = {e[2] for e in s["events"]}
        for k in (W.EV_FIGHT, W.EV_KILL, W.EV_BUY, W.EV_TRAVEL):
            self.assertIn(k, kinds)

    def test_causal_chain_links_exist(self):
        found = False
        for seed in range(1, 30):
            s = mk(seed); W.run(s, 600)
            for ev in s["events"]:
                if ev[2] == W.EV_KILL and W.consequences(s, ev[0]):
                    found = True
        self.assertTrue(found)

    def test_rewind_replay_identical(self):
        tl = Timeline(mk(5)); tl.step(200)
        d200 = W.digest(tl.s)
        tl.step(100)
        d300 = W.digest(tl.s)
        tl.rewind(120)
        self.assertEqual(tl.tick, 120)
        tl.step(80)
        self.assertEqual(W.digest(tl.s), d200)
        tl.step(100)
        self.assertEqual(W.digest(tl.s), d300)

    def test_rewind_with_interventions_replays(self):
        tl = Timeline(mk(5)); tl.step(60)
        tl.intervene("kill", [2]); tl.step(100)
        d = W.digest(tl.s)
        tl.rewind(30); tl.step(130)
        self.assertEqual(W.digest(tl.s), d)

    def test_branching(self):
        main = Timeline(mk(9)); main.step(100)
        same = main.fork(); alt = main.fork()
        alt.intervene("kill", [1])
        main.step(150); same.step(150); alt.step(150)
        self.assertEqual(W.digest(main.s), W.digest(same.s))   # un-intervened branch == mainline
        self.assertNotEqual(W.digest(main.s), W.digest(alt.s))  # alternate reality diverged
        self.assertEqual(main.tick, 250)

    def test_set_rule_intervention(self):
        a = Timeline(mk(4)); a.step(50)
        b = a.fork(); b.intervene("set_rule", [90], path="world.aggro_pct")
        a.step(200); b.step(200)
        self.assertNotEqual(W.digest(a.s), W.digest(b.s))
        self.assertEqual(b.s["rules"]["world"]["aggro_pct"], 90)
        self.assertEqual(a.s["rules"]["world"]["aggro_pct"], 4)

    def test_combat_round_math(self):
        c = RU.BASELINE["combat"]
        a = {"hp": 100, "maxhp": 100, "atk": 20, "def": 5, "potions": 3, "last": -1, "streak": 0}
        b = dict(a)
        # expected-crit: 15*(10000+10*50)//10000 = 15; guard 20% => 12
        da, db, _, _ = C.round_outcome(c, a, b, C.ATTACK, C.GUARD, None, C.CRIT_EXPECTED)
        self.assertEqual((da, db), (0, 12))
        # power = 15*150//100 = 22; expected crit => 23; baseline has no interrupt, b's attack hits a for 15
        da, db, _, _ = C.round_outcome(c, a, b, C.POWER, C.ATTACK, None, C.CRIT_EXPECTED)
        self.assertEqual((da, db), (15, 23))

    def test_history_and_json_roundtrip(self):
        s = mk(2); W.run(s, 200)
        s2 = json.loads(json.dumps(s))
        self.assertEqual(W.digest(s), W.digest(s2))
        self.assertTrue(len(W.history(s, 0)) > 0)


if __name__ == "__main__":
    unittest.main()
