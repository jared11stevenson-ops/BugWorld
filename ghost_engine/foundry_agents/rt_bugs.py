"""Reproducible DSL bug probes. python3 foundry_agents/rt_bugs.py"""
import json, time, copy, signal
from rt_lib import *
from ghost.kernel import rng as R

def base(**kw):
    s = {"id": "b", "name": "b", "vars": [["x", 5, 0, 10], ["y", 0, 0, 10]],
         "actions": [{"name": "a", "cond": 0, "fx": []}, {"name": "b", "cond": 0, "fx": []}],
         "passive": [], "end": [[[">=", ["v", "me", "y"], 10], 1]], "tiebreak": "x", "max_rounds": 10, "value": [["x", 1]]}
    s.update(kw); return s

print("B1 '=' vs '+=' ordering: mirrored play is NOT symmetric (seat 1's effects apply last)")
s = base(actions=[{"name": "noop", "cond": 0, "fx": []},
                  {"name": "raid", "cond": 0, "fx": [["+=", "me", "x", 2], ["=", "opp", "x", ["-", ["v", "opp", "x"], 1]]]}])
m = dsl.new_match(s, 1); dsl.step(s, m, 1, 1)
print("  both play raid from x=5/5: seat0.x=%d seat1.x=%d  (symmetric would be equal)" % (m["p"][0]["x"], m["p"][1]["x"]))
s2 = base(actions=[{"name": "noop", "cond": 0, "fx": []}, {"name": "set", "cond": 0, "fx": [["=", "opp", "x", 0], ["=", "me", "x", 9]]}])
m = dsl.new_match(s2, 1); dsl.step(s2, m, 1, 1)
print("  both play set(opp.x=0, me.x=9): seat0.x=%d seat1.x=%d  -> last writer (seat 1) always wins the collision" % (m["p"][0]["x"], m["p"][1]["x"]))

print("B2 'cond' is evaluated with acts=[0,0] -> any ['act',..] in cond is silently constant")
s = base(actions=[{"name": "a", "cond": 0, "fx": []}, {"name": "needs_opp_act", "cond": [">", ["act", "opp"], 0], "fx": [["+=", "me", "y", 10]]}])
m = dsl.new_match(s, 1)
print("  spec text:", dsl.spec_text(s).splitlines()[2])
print("  legal(action1) =", dsl.legal(s, m, 0, 1), "(always False: can never be played)")

print("B3 'rnd' in end/cond is evaluated in expected mode (n//2): rule text says d100 but value is constant 50")
s = base(end=[[["<", ["rnd", 100], 10], 1]], max_rounds=5)
print("  rule:", dsl.spec_text(s).splitlines()[-1])
fired = 0
for k in range(200):
    fired += A.play(s, 0, 0, k)["timeout"] == 0
print("  games ended by the 10%% chance rule: %d / 200 (expected ~ 1-(0.9^5) = 41%%)" % fired)
s = base(end=[[[">=", ["rnd", 100], 50], 1]])
r = [A.play(s, 0, 0, k)["round"] for k in range(3)]
print("  rule 'd100 >= 50' ends every game at round", r, "(true intent: ~50%/round)")

print("B4 no int64 guard: Python bignum vs GDScript int64 wraparound (cross-engine divergence)")
big = ["*", 3037000500, 3037000500]
s = base(vars=[["x", 0, -(2**62), 2**62]], actions=[{"name": "a", "cond": 0, "fx": []}, {"name": "b", "cond": 0, "fx": [["=", "me", "x", big]]}],
         end=[[[">", ["v", "me", "x"], 0], 1]], tiebreak="x", value=[["x", 1]])
print("  validate():", dsl.validate(s))
m = dsl.new_match(s, 1); dsl.step(s, m, 1, 1)
wrap = lambda v: (v + 2**63) % 2**64 - 2**63
print("  python x=%d (clamped); true product=%d; int64-wrapped product=%d (sign differs => GDScript would pick different branch)" % (m["p"][0]["x"], 3037000500*3037000500, wrap(3037000500*3037000500)))

print("B5 clamp happens only after ALL effects: overheal at cap absorbs damage; no per-effect clamping")
s = base(vars=[["hp", 10, 0, 10]], actions=[{"name": "idle", "cond": 0, "fx": []}, {"name": "heal", "cond": 0, "fx": [["+=", "me", "hp", 4]]}],
         passive=[], end=[[["<=", ["v", "me", "hp"], 0], -1]], tiebreak="hp", value=[["hp", 1]])
s["actions"].append({"name": "hit", "cond": 0, "fx": [["+=", "opp", "hp", -4]]})
m = dsl.new_match(s, 1); dsl.step(s, m, 1, 2)   # seat0 heals while seat1 hits seat0 at full hp 10
print("  seat0 at cap 10 plays heal(+4) while hit(-4) lands: hp=%d (sequential clamp would give 10-4=6 then +4=10, or 10 then -4=6)" % m["p"][0]["hp"])
m = dsl.new_match(s, 1); dsl.step(s, m, 1, 2); 
s["actions"][1]["fx"] = [["+=", "me", "hp", 9]]
m = dsl.new_match(s, 1); dsl.step(s, m, 1, 2)
print("  heal(+9) vs hit(-4) at cap: hp=%d -> the hit is fully absorbed by wasted overheal (net +5 clamps to 10)" % m["p"][0]["hp"])

print("B6 validate() crashes (uncaught AttributeError) on malformed-but-parseable specs")
for label, mut in [("action is a string", lambda s: s["actions"].append("oops")),
                   ("fx entry is a dict", lambda s: s["actions"][0].__setitem__("fx", [{"a": 1}])),
                   ("end rule is an int", lambda s: s.__setitem__("end", [3])),
                   ("vars is an int", lambda s: s.__setitem__("vars", 3)),
                   ("passive None", lambda s: s.__setitem__("passive", None)),
                   ("value entry int", lambda s: s.__setitem__("value", [3])),
                   ("name is a list", lambda s: s["actions"][0].__setitem__("name", ["x"])),
                   ("unhashable var name", lambda s: s["vars"].append([["z"], 0, 0, 1])),
                   ("max_rounds NaN", lambda s: s.__setitem__("max_rounds", float("nan"))),
                   ("tiebreak list", lambda s: s.__setitem__("tiebreak", ["x"])),
                   ("spec is a list", None)]:
    s = base()
    try:
        if mut is None: out = dsl.validate([s])
        else:
            mut(s); out = dsl.validate(s)
        print("  %-22s -> returned %s" % (label, str(out)[:60]))
    except Exception as ex:
        print("  %-22s -> CRASH %s: %s" % (label, type(ex).__name__, ex))

print("B7 validate accepts specs that crash/misbehave at play time")
s = base(actions=[{"name": "a", "cond": 0, "fx": []}, {"name": "b", "cond": 0, "fx": []}], max_rounds=True)
print("  max_rounds=True ->", dsl.validate(s))
s = base(); s["vars"][0][1] = True
print("  var init True accepted ->", dsl.validate(s))
s = base(); s["actions"][1]["cond"] = ["?", 1, 1, 1]; s["actions"][1]["fx"] = [["+=", "me", "y", 10]]
print("  float max_rounds 3.5:", dsl.validate(base(max_rounds=3.5)))
s = base(); s["actions"][0]["fx"] = [["+=", "me", "x", ["/", 7, 0]]]

print("B8 expression SIZE is bounded only by depth (12): 2^11 leaf evals per effect; a 'valid' spec can make evaluate() take minutes")
def tree(d):
    return ["v", "me", "x"] if d == 0 else ["+", tree(d - 1), tree(d - 1)]
for d in (4, 8, 10):
    s = base(); s["actions"][1]["fx"] = [["+=", "me", "y", ["min", 1, tree(d)]]]
    errs = dsl.validate(s); m = dsl.new_match(s, 1)
    t = time.time(); [dsl.payoff(s, m, 0, 1, 1) for _ in range(20)]
    print("  tree depth %2d: validate=%s  20 payoff() calls %.3fs" % (d, errs, time.time() - t))
s = base(); s["actions"][1]["fx"] = [["+=", "me", "y", ["min", 1, tree(10)]]] * 4
s["actions"] += [copy.deepcopy(s["actions"][1]) for _ in range(3)]
t = time.time(); M.evaluate(s, 1, 1); print("  evaluate(fights=1), 4 actions x 4 depth-10 effects: %.1fs (normal spec ~0.1s); validate=%s" % (time.time() - t, dsl.validate(s)))

print("B9 xorshift seed_state(seed): seeds 0 and 2^31 alias (seed masked to 31 bits)")
print("  seed_state(5)==seed_state(5+2**31):", R.seed_state(5) == R.seed_state(5 + 2**31))

