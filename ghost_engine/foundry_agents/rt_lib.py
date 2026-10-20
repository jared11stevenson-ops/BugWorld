import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ghost.foundry import dsl, metrics as M, agents as A

def ev(spec, seed=1, fights=6):
    r = M.evaluate(spec, seed, fights)
    return r

def seat_report(spec, games=40):
    """Play every ordered pair of fixed policies in BOTH seats; report p0/p1 win totals and swap-asymmetry."""
    n = len(spec["actions"]); ids = list(range(n)) + [A.CYCLE, A.ADAPTER]
    w0 = w1 = d = 0
    for i in ids:
        for j in ids:
            for k in range(games // 4):
                m = A.play(spec, i, j, 1000 + k)
                if m["winner"] == 0: w0 += 1
                elif m["winner"] == 1: w1 += 1
                else: d += 1
    return {"seat0_wins": w0, "seat1_wins": w1, "draws": d}

def brief(spec):
    r = ev(spec)
    mt = r["metrics"]
    return r["flags"], {k: round(v, 2) for k, v in mt.items() if k != "action_shares"}, [round(x, 2) for x in mt.get("action_shares", [])]

if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = json.load(open(p))
        print(p, brief(s), seat_report(s))
