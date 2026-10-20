import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio import cycle


def main():
    ap = argparse.ArgumentParser(prog="studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new-cycle", help="run a full production cycle (3 games)")
    n.add_argument("--prompt", default=None, help="inspiration prompt (words/phenomena bias the pick); omit for a random pick")
    n.add_argument("--seed", type=int, default=None)
    n.add_argument("--quick", action="store_true", help="small search budgets (smoke test)")
    sub.add_parser("status", help="show archive and studio knowledge summary")
    a = ap.parse_args()
    if a.cmd == "new-cycle":
        m = cycle.run_cycle(a.prompt, a.seed, a.quick)
        print(json.dumps({"cycle": m["cycle"], "universe": m["universe"], "released": m["released"], "timings_s": m["timings_s"], "reset": m["reset"]}, indent=1))
        sys.exit(0 if len(m["released"]) == 3 and m["reset"]["ok"] else 2)
    else:
        k = cycle.load_knowledge()
        idx = os.path.join(cycle.ARCHIVE, "index.json")
        print(json.dumps({"archive": json.load(open(idx)) if os.path.exists(idx) else [], "budget": k["budget"], "improvements": k["improvements"][-3:], "lessons": k["lessons"][-3:]}, indent=1))


main()
