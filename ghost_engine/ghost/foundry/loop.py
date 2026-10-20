"""The autonomous discovery loop: propose -> validate -> simulate -> archive (quality-diversity) -> learn from failures -> repeat.
Proposers: seeds, the grammar (random + failure-weighted), structural mutation/crossover of archive elites AND near-miss failures,
and an inbox of specs authored by outside agents. Everything is seeded and logged with provenance."""
import glob, hashlib, json, os, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor
from . import dsl, grammar as G, metrics as M, seeds as S, agents as A

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INBOX = os.path.join(ROOT, "foundry_inbox")
HOLDOUT_SEEDS = (101, 102, 103, 104)
VIABLE_MIN_FITNESS = 0.0


def _eval(args):
    spec, seed, fights = args
    return M.evaluate(spec, seed, fights)


def cell_of(r):
    mt = r["metrics"]
    L = mt["length"]
    lb = 0 if L < 8 else (1 if L < 14 else 2)
    ib = 0 if mt["interaction"] < .3 else (1 if mt["interaction"] < .7 else 2)
    return f"L{mt['live_actions']}|len{lb}|int{ib}|cyc{1 if mt['cycles'] else 0}|n{mt['n_actions']}"


class Foundry:
    def __init__(self, run_dir, seed=1, fights=6, workers=4, memory_from=None, use_inbox=True):
        self.dir = run_dir
        os.makedirs(run_dir, exist_ok=True)
        self.rnd = random.Random(seed)
        self.seed, self.fights, self.workers = seed, fights, workers
        self.cands = {}        # id -> record
        self.seen = set()
        self.archive = {}      # cell -> record id
        self.failures = []     # record ids
        self.memory = {"atoms": {}, "ops": {}, "proposers": {}}
        if memory_from and os.path.exists(memory_from):
            self.memory = json.load(open(memory_from))
        self.seed_sigs = [G.signature(s) for s in S.all_seeds()]
        self.counter = 0
        self.log = open(os.path.join(run_dir, "candidates.jsonl"), "w")
        self.gen_log = []
        self.inbox_seen = set()
        self.use_inbox = use_inbox
        self.prior = {}          # multiplicative proposal prior per atom kind (e.g. set from a universe's dynamics)

    # ---------------------------------------------------------------- bookkeeping
    def _uid(self, prefix):
        self.counter += 1
        return f"{prefix}{self.counter:04d}"

    def _update_weights(self):
        w = {}
        for k in G.ATOM_KINDS:
            st = self.memory["atoms"].get(k, {"trials": 0, "viable": 0})
            w[k] = (st["viable"] + 1) / (st["trials"] + 4) * 4 * self.prior.get(k, 1.0)
        G.KIND_W = w

    def _learn(self, rec):
        viable = not rec["flags"]
        for k in set(rec["meta"].get("atoms", [])):
            for kk in k.split("+"):
                st = self.memory["atoms"].setdefault(kk, {"trials": 0, "viable": 0, "flags": {}})
                st["trials"] += 1
                st["viable"] += 1 if viable else 0
                for f in rec["flags"]:
                    st["flags"][f] = st["flags"].get(f, 0) + 1
        op = rec["meta"].get("op")
        if op:
            st = self.memory["ops"].setdefault(op, {"trials": 0, "viable": 0, "improved": 0})
            st["trials"] += 1
            st["viable"] += 1 if viable else 0
            st["improved"] += 1 if rec.get("improved_on_parent") else 0
        pr = self.memory["proposers"].setdefault(rec["proposer"], {"trials": 0, "viable": 0})
        pr["trials"] += 1
        pr["viable"] += 1 if viable else 0

    # ---------------------------------------------------------------- evaluation of a batch
    def evaluate_batch(self, proposals, gen):
        fresh = []
        for p in proposals:
            h = dsl.spec_hash(p["spec"])
            if h in self.seen:
                continue
            self.seen.add(h)
            p["hash"] = h
            fresh.append(p)
        if not fresh:
            return []
        jobs = [(p["spec"], self.seed, self.fights) for p in fresh]
        if self.workers > 1 and len(jobs) > 4:
            with ProcessPoolExecutor(self.workers) as ex:
                results = list(ex.map(_eval, jobs, chunksize=4))
        else:
            results = [_eval(j) for j in jobs]
        out = []
        for p, r in zip(fresh, results):
            rec = {"id": p["spec"]["id"], "gen": gen, "proposer": p["proposer"], "meta": p.get("meta", {}), "parents": p.get("parents", []),
                   "hash": p["hash"], "spec": p["spec"], "fitness": r["fitness"], "flags": r["flags"], "metrics": r["metrics"],
                   "parts": r["parts"], "errors": r["errors"]}
            if r["valid"]:
                sig = G.signature(p["spec"])
                rec["novelty_vs_seeds"] = min(G.distance(sig, s) for s in self.seed_sigs)
                rec["signature"] = sorted(sig)
                par = self.cands.get(p["parents"][0]) if p.get("parents") else None
                rec["improved_on_parent"] = bool(par and par["valid"] and rec["fitness"] > par["fitness"] + 1e-9)
            rec["valid"] = r["valid"]
            self.cands[rec["id"]] = rec
            self._learn(rec)
            if not rec["flags"]:
                c = cell_of(r)
                rec["cell"] = c
                cur = self.cands.get(self.archive.get(c))
                if cur is None or rec["fitness"] > cur["fitness"]:
                    rec["replaced"] = cur["id"] if cur else None
                    self.archive[c] = rec["id"]
            else:
                self.failures.append(rec["id"])
            slim = {k: v for k, v in rec.items() if k != "signature"}
            self.log.write(json.dumps(slim) + "\n"); self.log.flush()
            out.append(rec)
        return out

    # ---------------------------------------------------------------- proposers
    def ingest_inbox(self):
        props = []
        if not self.use_inbox:
            return props
        for path in sorted(glob.glob(os.path.join(INBOX, "*.json"))):
            raw = open(path).read()
            if hashlib.md5(raw.encode()).hexdigest() in self.inbox_seen:
                continue
            self.inbox_seen.add(hashlib.md5(raw.encode()).hexdigest())
            try:
                obj = json.loads(raw)
            except Exception as ex:
                print("inbox: unreadable", path, ex); continue
            for sp in (obj if isinstance(obj, list) else [obj]):
                if not isinstance(sp, dict) or dsl.validate(dict(sp, id="x", name=sp.get("name", "x") if isinstance(sp.get("name"), str) else "x")):
                    print("inbox: rejected invalid spec in", path); continue
                who = "agent:" + os.path.splitext(os.path.basename(path))[0]
                sp = dict(sp); sp["id"] = self._uid("ag"); sp.setdefault("name", sp["id"])
                sp.pop("rationale", None)
                props.append({"spec": sp, "proposer": who, "meta": {"atoms": [], "driver": sp["vars"][0][0]}})
        return props

    def parents_pool(self):
        elites = [self.cands[i] for i in self.archive.values()]
        near = sorted((self.cands[i] for i in self.failures if self.cands[i]["valid"] and len(self.cands[i]["flags"]) <= 2),
                      key=lambda r: -r["fitness"])[:max(5, len(self.failures) // 8)]
        return elites, near

    def propose(self, n_mut, n_cross, n_fresh):
        self._update_weights()
        elites, near = self.parents_pool()
        props = []
        def pick(pool, key):
            ws = [max(0.05, key(r)) for r in pool]
            return self.rnd.choices(pool, weights=ws)[0]
        for _ in range(n_mut):
            use_near = near and (not elites or self.rnd.random() < 0.3)
            par = pick(near, lambda r: r["fitness"]) if use_near else pick(elites, lambda r: r["fitness"] + r.get("novelty_vs_seeds", 0))
            sp, me = G.mutate(par["spec"], par["meta"], self.rnd, self._uid("mu"))
            props.append({"spec": sp, "meta": me, "parents": [par["id"]], "proposer": "mutation" + ("/near-miss" if use_near else "")})
        for _ in range(n_cross if len(elites) >= 2 else 0):
            a, b = self.rnd.sample(elites, 2)
            sp, me = G.crossover(a["spec"], a["meta"], b["spec"], b["meta"], self.rnd, self._uid("cx"))
            props.append({"spec": sp, "meta": me, "parents": [a["id"], b["id"]], "proposer": "crossover"})
        for _ in range(n_fresh):
            sp, me = G.random_spec(self.rnd, self._uid("gr"))
            props.append({"spec": sp, "meta": me, "parents": [], "proposer": "grammar"})
        return props

    # ---------------------------------------------------------------- main loop
    def run(self, generations=10, per_gen=48, quiet=False):
        t0 = time.time()
        gen0 = [{"spec": s, "meta": {"atoms": [], "driver": s["vars"][0][0]}, "parents": [], "proposer": "seed"} for s in S.all_seeds()]
        gen0 += self.ingest_inbox()
        gen0 += self.propose(0, 0, per_gen)
        for g in range(generations + 1):
            if g == 0:
                batch = gen0
            else:
                batch = self.ingest_inbox() + self.propose(int(per_gen * .5), int(per_gen * .2), int(per_gen * .3))
            recs = self.evaluate_batch(batch, g)
            viable = [r for r in recs if not r["flags"]]
            elites = [self.cands[i] for i in self.archive.values()]
            row = {"gen": g, "evaluated": len(recs), "viable": len(viable), "archive_cells": len(self.archive),
                   "best_fitness": max((e["fitness"] for e in elites), default=0),
                   "mean_archive_fitness": statistics.mean(e["fitness"] for e in elites) if elites else 0,
                   "best_novelty": max((e["novelty_vs_seeds"] for e in elites), default=0),
                   "failures_total": len(self.failures), "elapsed_s": round(time.time() - t0, 1)}
            self.gen_log.append(row)
            if not quiet:
                print(json.dumps(row))
        self.save()
        return self

    def save(self):
        json.dump(self.memory, open(os.path.join(self.dir, "memory.json"), "w"), indent=1, sort_keys=True)
        json.dump({c: self.archive[c] for c in sorted(self.archive)}, open(os.path.join(self.dir, "archive.json"), "w"), indent=1)
        json.dump(self.gen_log, open(os.path.join(self.dir, "generations.json"), "w"), indent=1)
        tax = {}
        for i in self.failures:
            for f in self.cands[i]["flags"]:
                tax[f] = tax.get(f, 0) + 1
        json.dump({"taxonomy": tax, "n": len(self.failures),
                   "examples": {f: [i for i in self.failures if f in self.cands[i]["flags"]][:3] for f in tax}},
                  open(os.path.join(self.dir, "failures.json"), "w"), indent=1, sort_keys=True)

    # ---------------------------------------------------------------- validation of discoveries
    def lineage(self, rid):
        chain = [rid]
        while self.cands[chain[-1]]["parents"]:
            nxt = self.cands[chain[-1]]["parents"][0]
            if nxt not in self.cands:
                break
            chain.append(nxt)
        return chain[::-1]

    def holdout(self, spec):
        """Fresh seeds + extra unseen strategies (mirror, greedy, counter) -> does it still look viable?"""
        rs = [M.evaluate(spec, sd, self.fights) for sd in HOLDOUT_SEEDS]
        flags = {}
        for r in rs:
            for f in r["flags"]:
                flags[f] = flags.get(f, 0) + 1
        n = len(spec["actions"])
        fixed = list(range(n)) + [A.CYCLE, A.RANDOM, A.MIRROR, A.GREEDY, A.COUNTER]
        worst = {}
        for i in fixed:
            ws = []
            for j in fixed:
                if i != j:
                    ws.append(statistics.mean((1.0 if (m := A.play(spec, i, j, 5000 + i * 31 + j + k))["winner"] == 0 else (0.5 if m["winner"] == -1 else 0.0)) for k in range(6)))
            worst[i] = min(ws)
        return {"fitness_mean": statistics.mean(r["fitness"] for r in rs), "fitness_std": statistics.pstdev(r["fitness"] for r in rs),
                "flag_counts_over_seeds": flags, "viable_seeds": sum(1 for r in rs if not r["flags"]),
                "extended_dominance": max(worst.values()), "extended_top": max(worst, key=lambda i: worst[i])}

    def discoveries(self, top=5, min_novelty=0.15):
        elites = [self.cands[i] for i in self.archive.values() if self.cands[i]["proposer"] != "seed"]
        cand = [e for e in elites if e.get("novelty_vs_seeds", 0) >= min_novelty]
        cand.sort(key=lambda e: -(e["fitness"] + 0.5 * e["novelty_vs_seeds"]))
        out = []
        for e in cand[:top * 6]:
            h = self.holdout(e["spec"])
            out.append({"rec": e, "holdout": h, "lineage": self.lineage(e["id"])})
        out = [o for o in out if o["holdout"]["viable_seeds"] >= 3 and o["holdout"]["extended_dominance"] < 0.85]
        out.sort(key=lambda o: -(o["holdout"]["fitness_mean"] + 0.5 * o["rec"]["novelty_vs_seeds"]))
        chosen = []
        for o in out:   # greedy diversity: each discovery must be structurally distinct from those already chosen
            sig = set(o["rec"]["signature"])
            if all(G.distance(sig, set(c["rec"]["signature"])) >= 0.2 for c in chosen):
                chosen.append(o)
        return chosen[:top]
