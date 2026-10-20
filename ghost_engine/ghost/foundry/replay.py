"""Living-twin replay: re-simulate human/agent sessions recorded by the Godot arena in Python and compare digests."""
import json, os
from . import dsl, agents as A
from .compile_godot import GEN


def replay(rec, spec):
    n = len(spec["actions"])
    m = dsl.new_match(spec, rec["seed"])
    h = A.new_hist(n)
    for a in rec["actions"]:
        if m["done"]:
            return None
        a1 = A.choose(spec, rec["opp"], m, 1, h)
        s0, s1 = dsl.step(spec, m, a, a1)
        A.observe(h, s0)
    return {"digest": "%08x" % dsl.match_digest(spec, m), "winner": m["winner"], "rounds": m["round"], "done": m["done"]}


def verify(records_path):
    specs = {c["spec"]["id"]: c["spec"] for c in json.load(open(os.path.join(GEN, "concepts_export.json")))}
    recs = json.load(open(records_path))
    bad = []
    for r in recs:
        got = replay(r, specs[r["concept"]])
        if not got or got["digest"] != r["digest"] or got["winner"] != r["winner"] or got["rounds"] != r["rounds"]:
            bad.append((r["concept"], r["seed"], got, r["digest"]))
    return {"sessions": len(recs), "mismatches": len(bad), "detail": bad[:3]}
