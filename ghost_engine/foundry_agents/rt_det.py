"""Determinism probe: print a digest of evaluate() + 3 match digests for many specs. Run under different PYTHONHASHSEED and compare."""
import json, sys, random, glob, os
from rt_lib import *
from ghost.foundry import grammar as G, seeds as S
rnd = random.Random(7)
specs = S.all_seeds() + [G.random_spec(rnd, "g%d" % i)[0] for i in range(60)]
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "redteam_*.json"))):
    specs.append(json.load(open(f)))
out = []
for sp in specs:
    if dsl.validate(sp): continue
    r = M.evaluate(sp, 1, 6)
    d = [dsl.match_digest(sp, A.play(sp, 8, 7, k)) for k in range(3)]
    out.append((sp["id"], r["flags"], round(r["fitness"], 9), d, dsl.spec_hash(sp)))
print(json.dumps(out))
