"""Living Twin check: replay Python-generated cases (incl. randomly fuzzed rulesets) through the headless Godot
kernel and compare state digests. Usage: GODOT_BIN=/path/to/godot python -m ghost.twin [n_fuzz] [ticks]"""
import json, os, random, subprocess, sys, tempfile, time
from .kernel import world as W
from .lab import causal as CA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GODOT = os.environ.get("GODOT_BIN", "/tmp/g/Godot_v4.5-stable_linux.x86_64")


def run_godot(args, timeout=900):
    cmd = [GODOT, "--headless", "--path", os.path.join(ROOT, "godot")] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def parity(n_fuzz=12, ticks=300):
    rnd = random.Random(2024)
    cases = []
    for name in ("v0_baseline", "v1_evolved"):
        with open(os.path.join(ROOT, "rulesets", name + ".json")) as f:
            cases.append({"rules": json.load(f), "seed": 41, "ticks": ticks})
    for i in range(n_fuzz):
        cases.append({"rules": CA.random_rules(rnd), "seed": 1000 + i, "ticks": ticks})
    t0 = time.time()
    exp = []
    for c in cases:
        s = W.new_world(c["seed"], c["rules"])
        W.run(s, c["ticks"])
        exp.append({"digest": W.digest_hex(s), "events": len(s["events"])})
    py_s = time.time() - t0
    with tempfile.TemporaryDirectory() as d:
        cp, op = os.path.join(d, "cases.json"), os.path.join(d, "out.json")
        with open(cp, "w") as f:
            json.dump(cases, f)
        r = run_godot(["--script", "res://tests/trace.gd", "--", cp, op])
        if not os.path.exists(op):
            raise RuntimeError("godot produced no output:\n" + r.stdout[-2000:] + r.stderr[-2000:])
        with open(op) as f:
            got = json.load(f)
    bad = [(i, exp[i], got["results"][i]) for i in range(len(cases)) if exp[i] != got["results"][i]]
    return {"cases": len(cases), "ticks_each": ticks, "mismatches": len(bad), "detail": bad[:3],
            "python_s": round(py_s, 2), "godot_s": round(got["ms"] / 1000, 2)}


if __name__ == "__main__":
    res = parity(int(sys.argv[1]) if len(sys.argv) > 1 else 12, int(sys.argv[2]) if len(sys.argv) > 2 else 300)
    print(json.dumps(res))
    sys.exit(1 if res["mismatches"] else 0)
