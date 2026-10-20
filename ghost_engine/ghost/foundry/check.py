"""Agent-facing tool. Validate + simulate a concept spec and print measured evidence.
  python -m ghost.foundry.check spec.json            # evaluate (spec.json = one spec or a list)
  python -m ghost.foundry.check spec.json --submit NAME   # also drop viable specs into foundry_inbox/NAME.json"""
import json, os, sys
from . import dsl, metrics as M, grammar as G, seeds as S, loop


def main(argv):
    path = argv[0]
    obj = json.load(open(path))
    specs = obj if isinstance(obj, list) else [obj]
    sigs = [G.signature(s) for s in S.all_seeds()]
    ok = []
    for sp in specs:
        print("=" * 70)
        errs = dsl.validate(sp)
        if errs:
            print("INVALID:", errs); continue
        print(dsl.spec_text(sp))
        r = M.evaluate(sp, 1, 6)
        mt = r["metrics"]
        nov = min(G.distance(G.signature(sp), s) for s in sigs)
        print(f"fitness={r['fitness']:.3f} flags={r['flags'] or 'NONE (viable)'} novelty_vs_seeds={nov:.2f}")
        print("metrics:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in mt.items() if k != "action_shares"})
        print("action_shares:", [round(x, 2) for x in mt["action_shares"]])
        print("parts:", {k: round(v, 2) for k, v in r["parts"].items()})
        if not r["flags"]:
            ok.append(sp)
    if "--submit" in argv:
        name = argv[argv.index("--submit") + 1]
        os.makedirs(loop.INBOX, exist_ok=True)
        with open(os.path.join(loop.INBOX, name + ".json"), "w") as f:
            json.dump(ok, f, indent=1)
        print(f"submitted {len(ok)} viable spec(s) to foundry_inbox/{name}.json")


if __name__ == "__main__":
    main(sys.argv[1:])
