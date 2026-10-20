import sys, json, random
from rt_lib import *
from ghost.foundry import grammar as G
rnd = random.Random(int(sys.argv[1]))
out = []
for t in range(int(sys.argv[2])):
    sp, me = G.random_spec(rnd, "f%d" % t)
    r = M.evaluate(sp, 1, 6)
    if r["flags"]: continue
    sr = seat_report(sp, 16)
    out.append((sp, r, sr))
    print(t, sp["name"], round(r["fitness"],2), sr, flush=True)
json.dump([o[0] for o in out], open("/tmp/fuzz_viable_%s.json" % sys.argv[1], "w"))
