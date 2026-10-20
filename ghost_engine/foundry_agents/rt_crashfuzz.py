"""Random valid-by-validate() specs through evaluate(); report any exception or slow case."""
import random, sys, time, traceback, json
from rt_lib import *
rnd = random.Random(int(sys.argv[1]))
OPS = ["+","-","*","/","min","max",">","<",">=","<=","==","!=","&&","||"]
def expr(names, d=0):
    r = rnd.random()
    if d > 3 or r < .25: return rnd.choice([0, 1, -1, 2, 3, 7, -5, 100, 10**6])
    if r < .45: return ["v", rnd.choice(["me","opp"]), rnd.choice(names)]
    if r < .52: return ["act", rnd.choice(["me","opp"])]
    if r < .56: return ["round"]
    if r < .62: return ["rnd", rnd.choice([1,2,3,100])]
    if r < .66: return ["!", expr(names, d+1)]
    if r < .72: return ["?", expr(names,d+1), expr(names,d+1), expr(names,d+1)]
    return [rnd.choice(OPS), expr(names,d+1), expr(names,d+1)]
bad = 0
for t in range(int(sys.argv[2])):
    k = rnd.randint(1, 3); names = ["a","b","c"][:k]
    vars_ = []
    for nm in names:
        lo = rnd.choice([-5, 0, 0, -100]); hi = rnd.choice([3, 10, 40, 1000]); vars_.append([nm, rnd.randint(lo, min(hi, lo+5)), lo, hi])
    n = rnd.randint(2, 6)
    acts = [{"name": "x%d" % i, "cond": 0 if i == 0 or rnd.random() < .6 else expr(names),
             "fx": [[rnd.choice(["+=","="]), rnd.choice(["me","opp"]), rnd.choice(names), expr(names)] for _ in range(rnd.randint(0,3))]} for i in range(n)]
    sp = {"id": "z%d" % t, "name": "z", "vars": vars_, "actions": acts,
          "passive": [[rnd.choice(["+=","="]), rnd.choice(["me","opp"]), rnd.choice(names), expr(names)] for _ in range(rnd.randint(0,2))],
          "end": [[expr(names), rnd.choice([1,-1])] for _ in range(rnd.randint(1,3))],
          "tiebreak": rnd.choice(names + [""]), "max_rounds": rnd.randint(3, 60),
          "value": [[rnd.choice(names), rnd.randint(-3, 3)] for _ in range(rnd.randint(0,2))]}
    if dsl.validate(sp): continue
    t0 = time.time()
    try:
        r = M.evaluate(sp, 1, 1)
        m = A.play(sp, 8, 7, 3); dsl.match_digest(sp, m)
        dsl.spec_text(sp)
    except Exception as ex:
        bad += 1; print("CRASH", type(ex).__name__, ex); json.dump(sp, open("/tmp/crash_%d.json" % bad, "w"))
        if bad > 3: break
print("done, crashes:", bad)
