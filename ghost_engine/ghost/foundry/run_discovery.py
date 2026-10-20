"""End-to-end foundry run: discover -> validate -> compare -> preserve evidence -> compile to Godot.
  python -m ghost.foundry.run_discovery NAME [--no-inbox] [--gens N] [--per-gen N] [--seed N] [--no-compile]"""
import argparse, json, os, random, statistics, time
from . import dsl, grammar as G, metrics as M, seeds as S, loop as L, compile_godot as CG

ROOT = L.ROOT
EV = os.path.join(ROOT, "evidence", "foundry")


def control_random(n_evals, seed, fights):
    """Random-search control with the same evaluation budget: no archive, no learning, no mutation."""
    rnd = random.Random(seed + 999)
    sigs = [G.signature(s) for s in S.all_seeds()]
    rows = []
    for i in range(n_evals):
        sp, me = G.random_spec(rnd, f"ctl{i}")
        r = M.evaluate(sp, seed, fights)
        nov = min(G.distance(G.signature(sp), s) for s in sigs)
        rows.append((r, nov))
    G.KIND_W = None
    viable = [(r, n) for r, n in rows if not r["flags"]]
    cells = {L.cell_of(r) for r, _ in viable}
    nov_viable = [(r["fitness"], n) for r, n in viable if n >= 0.15]
    return {"evals": n_evals, "viable": len(viable), "cells": len(cells),
            "best_fitness_viable_novel": max((f for f, _ in nov_viable), default=0),
            "mean_fitness_viable": statistics.mean(r["fitness"] for r, _ in viable) if viable else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--no-inbox", action="store_true")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--per-gen", type=int, default=48)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--memory-from", default=None)
    a = ap.parse_args()
    run_dir = os.path.join(EV, a.name)
    t0 = time.time()
    F = L.Foundry(run_dir, seed=a.seed, memory_from=a.memory_from, use_inbox=not a.no_inbox)
    F.run(generations=a.gens, per_gen=a.per_gen)
    n_evals = len(F.cands)
    disc = F.discoveries(top=4)
    out = []
    for d in disc:
        rec = d["rec"]
        chain = []
        for cid in d["lineage"]:
            c = F.cands[cid]
            if c["valid"]:
                h = F.holdout(c["spec"])
                chain.append({"id": cid, "proposer": c["proposer"], "op": c["meta"].get("op", ""), "holdout_fitness": h["fitness_mean"],
                              "viable_seeds": h["viable_seeds"], "flags_train": c["flags"]})
        out.append({"id": rec["id"], "proposer": rec["proposer"], "gen": rec["gen"], "spec": rec["spec"], "text": dsl.spec_text(rec["spec"]),
                    "fitness_train": rec["fitness"], "novelty_vs_seeds": rec["novelty_vs_seeds"], "metrics": rec["metrics"],
                    "holdout": d["holdout"], "lineage": chain, "signature": rec["signature"]})
    ctl = control_random(n_evals, a.seed, F.fights)
    elites = [F.cands[i] for i in F.archive.values()]
    loop_stats = {"evals": n_evals, "viable": sum(1 for c in F.cands.values() if c["valid"] and not c["flags"]), "cells": len(F.archive),
                  "best_fitness_viable_novel": max((e["fitness"] for e in elites if e.get("novelty_vs_seeds", 0) >= .15), default=0),
                  "mean_fitness_viable": statistics.mean(e["fitness"] for e in elites) if elites else 0}
    by_prop = {}
    for c in F.cands.values():
        d = by_prop.setdefault(c["proposer"].split(":")[0].split("/")[0], {"n": 0, "viable": 0})
        d["n"] += 1; d["viable"] += 0 if c["flags"] else 1
    summary = {"name": a.name, "seed": a.seed, "inbox": not a.no_inbox, "gens": a.gens, "per_gen": a.per_gen, "elapsed_s": round(time.time() - t0, 1),
               "loop": loop_stats, "random_control": ctl, "by_proposer": by_prop, "discoveries": [d["id"] for d in out],
               "failure_taxonomy": json.load(open(os.path.join(run_dir, "failures.json")))["taxonomy"]}
    json.dump(out, open(os.path.join(run_dir, "discoveries.json"), "w"), indent=1)
    json.dump(summary, open(os.path.join(run_dir, "summary.json"), "w"), indent=1)
    write_report(run_dir, summary, out, F)
    if not a.no_compile and out:
        ents = [{"spec": s, "evidence": {"source": "seed", "summary": "hand-written seed (reference)"}} for s in S.all_seeds()]
        for d in out:
            ents.append({"spec": d["spec"], "evidence": {"source": d["proposer"], "id": d["id"], "fitness_train": d["fitness_train"],
                         "holdout_fitness": d["holdout"]["fitness_mean"], "novelty_vs_seeds": d["novelty_vs_seeds"], "run": a.name,
                         "summary": f"discovered by {d['proposer']} gen {d['gen']}; holdout fitness {d['holdout']['fitness_mean']:.2f}; novelty {d['novelty_vs_seeds']:.2f}"}})
        print("compiled:", CG.compile_concepts(ents))
    print(json.dumps(summary, indent=1))


def write_report(run_dir, summary, disc, F):
    L_ = []
    w = L_.append
    w(f"# Foundry run `{summary['name']}` (generated)\n")
    w(f"seed {summary['seed']} · {summary['gens']} generations × {summary['per_gen']} proposals · inbox {'ON' if summary['inbox'] else 'OFF'} · {summary['elapsed_s']}s\n")
    w("## Loop vs random search (same evaluation budget)\n")
    w("| | evals | viable | MAP-Elites cells filled | best viable fitness (novel ≥0.15) | mean viable fitness |")
    w("|---|---|---|---|---|---|")
    for k, v in (("discovery loop", summary["loop"]), ("random control", summary["random_control"])):
        w(f"| {k} | {v['evals']} | {v['viable']} | {v['cells']} | {v['best_fitness_viable_novel']:.3f} | {v['mean_fitness_viable']:.3f} |")
    w("\n## Proposers (viable / proposed)\n")
    for k, v in sorted(summary["by_proposer"].items()):
        w(f"- {k}: {v['viable']}/{v['n']}")
    w("\n## Failure taxonomy (preserved in failures.json; fed back into proposals)\n")
    for k, v in sorted(summary["failure_taxonomy"].items(), key=lambda kv: -kv[1]):
        w(f"- {k}: {v}")
    w("\n## What the loop learned (atom memory)\n")
    w("| atom kind | trials | viable | viable rate | most common flag |")
    w("|---|---|---|---|---|")
    for k, st in sorted(F.memory["atoms"].items(), key=lambda kv: -kv[1]["viable"] / max(1, kv[1]["trials"])):
        fl = max(st["flags"].items(), key=lambda kv: kv[1])[0] if st.get("flags") else "-"
        w(f"| {k} | {st['trials']} | {st['viable']} | {st['viable']/max(1,st['trials']):.2f} | {fl} |")
    w("\n## Discoveries (validated on held-out seeds and unseen strategies)\n")
    for d in disc:
        h = d["holdout"]
        w(f"### {d['id']} — proposer `{d['proposer']}`, gen {d['gen']}\n")
        w("```\n" + d["text"] + "\n```")
        w(f"- train fitness {d['fitness_train']:.3f}; **holdout fitness {h['fitness_mean']:.3f} ± {h['fitness_std']:.3f}**, viable on {h['viable_seeds']}/4 holdout seeds; "
          f"extended dominance (10+ strategies) {h['extended_dominance']:.2f}; novelty vs seeds {d['novelty_vs_seeds']:.2f}")
        mt = d["metrics"]
        w(f"- live actions {mt['live_actions']}/{mt['n_actions']}, interaction {mt['interaction']:.2f}, leverage {mt['leverage']:.2f}, length {mt['length']:.1f}, skill edge {mt['skill']:.2f}, cycles {mt['cycles']}")
        w("- lineage (competing versions, holdout fitness): " + " → ".join(f"{c['id']}({c['proposer']}/{c['op'] or 'seed'}):{c['holdout_fitness']:.2f}" for c in d["lineage"]) + "\n")
    with open(os.path.join(run_dir, "report.md"), "w") as f:
        f.write("\n".join(L_) + "\n")


if __name__ == "__main__":
    main()
