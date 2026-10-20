import json, itertools, sys, copy
from rt_lib import *
from ghost.foundry import seeds as S
def remap(e, p):
    """p[old]=new index; remap comparisons of (act X)==const and any act refs compared to ints."""
    if isinstance(e, list) and e:
        if e[0] in ("==", "!=") and isinstance(e[1], list) and e[1][0] == "act" and isinstance(e[2], int):
            return [e[0], e[1], p[e[2]]]
        return [remap(x, p) if isinstance(x, list) else x for x in e]
    return e
def permute(spec, order):
    """order = new list of old indices; action 0 (cond 0) must stay legal"""
    p = {old: new for new, old in enumerate(order)}
    s = copy.deepcopy(spec)
    s["actions"] = [copy.deepcopy(spec["actions"][o]) for o in order]
    for a in s["actions"]:
        a["cond"] = remap(a["cond"], p); a["fx"] = remap(a["fx"], p)
    s["passive"] = remap(s["passive"], p); s["end"] = remap(s["end"], p)
    return s
if __name__ == "__main__":
    path = sys.argv[1]
    spec = json.load(open(path)) if path.endswith(".json") else getattr(S, path)()
    n = len(spec["actions"]); res = {}
    for order in itertools.permutations(range(n)):
        s = permute(spec, order)
        if dsl.validate(s): continue
        r = M.evaluate(s, 1, 6)
        res[order] = (tuple(r["flags"]), round(r["fitness"], 3))
    from collections import Counter
    print(path, Counter(v[0] for v in res.values()).most_common())
    for o, v in list(res.items()):
        if v[0]: print("  order", o, v); break
