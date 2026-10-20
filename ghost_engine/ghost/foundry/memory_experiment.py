"""Does preserved failure memory help future runs? Fresh pure-grammar proposals (no mutation, no inbox), same seeds,
cold start vs memory loaded from a previous run. Viable = passes every flag. Reports mean over several seeds."""
import json, os, statistics, tempfile
from . import loop as L, grammar as G

ROOT = L.ROOT


def run(seed, memory_from, n=160):
    with tempfile.TemporaryDirectory() as d:
        f = L.Foundry(d, seed=seed, workers=4, memory_from=memory_from, use_inbox=False)
        f._update_weights()
        props = f.propose(0, 0, n)
        recs = f.evaluate_batch(props, 0)
        G.KIND_W = None
        return sum(1 for r in recs if not r["flags"]) / max(1, len(recs)), statistics.mean(r["fitness"] for r in recs)


def main():
    mem = os.path.join(ROOT, "evidence", "foundry", "autonomous", "memory.json")
    rows = []
    for seed in range(11, 17):
        cold = run(seed, None)
        warm = run(seed, mem)
        rows.append({"seed": seed, "cold_viable": cold[0], "warm_viable": warm[0], "cold_fit": cold[1], "warm_fit": warm[1]})
        print(rows[-1])
    out = {"rows": rows, "cold_viable_mean": statistics.mean(r["cold_viable"] for r in rows),
           "warm_viable_mean": statistics.mean(r["warm_viable"] for r in rows),
           "paired_gain": statistics.mean(r["warm_viable"] - r["cold_viable"] for r in rows),
           "paired_gain_sd": statistics.pstdev(r["warm_viable"] - r["cold_viable"] for r in rows),
           "memory_source": "evidence/foundry/autonomous/memory.json (549 evaluated concepts)"}
    json.dump(out, open(os.path.join(ROOT, "evidence", "foundry", "memory_experiment.json"), "w"), indent=1)
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
