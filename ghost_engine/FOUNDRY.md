# Ghost Engine — the discovery pipeline

Ghost Engine is an evolutionary game foundry. The persistent world kernel (README.md) is the foundation; this file describes
the layer that **invents, tests, evolves, preserves and compiles whole game concepts**. Numbers come from `evidence/foundry/`
(generated). Read "What does not work yet" before trusting any of it.

## Audit: vision vs. what existed before this layer

| Vision requirement | Before | Now |
|---|---|---|
| Persistent, rewindable, branchable, causal worlds | done (world kernel, timelines, cause links) | unchanged; the same snapshot/branch idea now also measures *agency* in concept games (`leverage`) |
| AI proposes original mechanics as executable rules | **missing** (only 11 hand-picked integers were tuned) | mechanic DSL (`ghost/foundry/dsl.py`) expresses whole concepts as data; proposers: grammar, structural mutation/crossover, near-miss repair, and an agent inbox |
| Explore fundamentally different concepts | **missing** | races, heists, territory, auctions, tempo/charge, negotiation... all in one language; novelty is measured structurally vs. the seeds |
| Continuous discovery loop | **missing** | `ghost/foundry/loop.py`: propose → validate → simulate (parallel) → MAP-Elites archive → failure archive → memory → repeat |
| Failed experiments preserved and used | **missing** | every candidate (viable or not) logged with provenance and flags; failure taxonomy; near-miss failures are re-mutated; per-atom memory |
| Validated discovery → Godot gameplay | one fixed ruleset only | `compile_godot.py`: any spec → `godot/generated/` (data, scene per concept, golden traces, asset list) + generic playable arena |
| Living twin of the game | world kernel only | GDScript interpreter of the same DSL; parity on goldens + fuzzed specs; Godot play sessions are replayed in Python |
| Autonomous specialized agents producing executable evidence | none | 3 agents ran this session: two inventors (submitted specs through the same measured pipeline) and a red-team verifier (found real bugs; all fixed) |

## Pipeline

```
 seeds ─┐
 grammar ┼─► candidates ─► validate (static) ─► simulate (tournaments, branching leverage) ─► flags + fitness
 mutate/ │                                                                                      │
 cross   │        ┌────────── failure archive (kept, tagged, near-misses re-mutated) ◄───────────┤
 agents ─┘        │                                                                              ▼
 (inbox)          └─► memory (atom/operator/proposer stats) ─► proposal weights      MAP-Elites archive (viable only, by behaviour cell)
                                                                                                 │
                              held-out seeds + unseen strategies + lineage comparison ◄──────────┘
                                                                                                 ▼
                                    compile_godot ─► godot/generated ─► playable arena + parity twin + replay of real sessions
```

* **DSL** — two-player simultaneous game: integer vars, actions with legality conditions and `+=` effects, passives, end rules,
  value heuristic. Reactive rules (`['act','opp']`), resource gating, randomness (`rnd`, effects only). Deltas only, summed then
  clamped, so resolution cannot favour a seat. Validation also bounds expression size and rejects constructs that would be
  silently constant (see red-team fixes).
* **Metrics (structural proxies, not fun)** — robust dominance among static strategies (both seats measured), scripted two-move
  "dominant line" check, best-response diversity, RPS cycles, liveness (an action is live if the agent uses it or it is a winning
  pure response, and it can causally affect the result), decisiveness, length band, skill edge vs the *strongest* static strategies,
  payoff-matrix interaction, **leverage** (branch a match at each round, force each alternative action, count result flips),
  seat bias, luck (seed sensitivity), misleading-value and inert-action static checks.
* **Viable** = no flag. Fitness is a weighted mean of the parts (weights are my assumptions, stated in `metrics.py`).

## Results (honest)

Autonomous run, no agent input (`evidence/foundry/autonomous/report.md`, 12 generations × 48 proposals, seed 1):

| | evaluations | viable | archive cells | best viable fitness (novel) | mean viable fitness |
|---|---|---|---|---|---|
| discovery loop | 549 | **222** | **73** | 1.000 | 0.760 |
| random search, same budget | 549 | 96 | 47 | 0.988 | 0.732 |

Run with agent-authored specs in the inbox (`evidence/foundry/with_agents/`, seed 2): loop 235/571 viable and 73 cells vs random
105/571 and 52 cells. Viable rate by proposer: crossover 74–81%, mutation 44–52%, grammar fresh samples 16–19%.
Agent specs: 6 of 8 viable under the final (hardened) metrics; the loop mutated agent seed *Parley* (held-out fitness 0.83)
into `mu0454` (0.97) — lineage and every intermediate version are in the report. That concept is compiled and playable
(`evidence/screens/concept_arena.png`).

Discoveries (4 per run) are chosen to be structurally distinct from each other, novel vs the 3 seeds (novelty 0.68–0.94), viable on all 4
held-out seeds, and not dominated by 5 additional unseen strategies (mirror, greedy, counter...). Each report lists the rules as
text, held-out fitness ± std, and the lineage chain of ancestors evaluated on held-out seeds.

**Failure memory did not help (measured, negative result).** Fresh pure-grammar proposals with atom weights learned from a
549-concept run vs a cold start: viable rate 16.5% vs 15.5%, paired gain +0.9 ± 3.8 points over 6 seeds — not detectable
(`evidence/foundry/memory_experiment.json`). The loop's advantage over random search comes from archive-based
mutation/crossover and near-miss repair, not from the weights. The memory is preserved and logged but should not be credited.

**Red team (agent) and fixes.** An adversarial agent produced specs the first pipeline called viable although bad, and good specs it
flagged, plus DSL bugs (report: `foundry_agents/redteam_report.md`). Fixed and regression-tested: seat-order bias from `=` effects
(op removed), `act`/`rnd` silently constant in conds/end rules (now rejected), int64 divergence between engines (saturation),
`validate()` crash on malformed input, expression-size DoS, seat symmetry (both seats now measured + `seat_bias` flag),
cosmetic/decoy actions (static relevance), dice-decided games (`luck_dominated`), setup-then-finisher combos (`dominant_line`),
order-dependent baselines (cycle baseline dropped; "always-i" falls back to greedy). Side effect: the metrics got stricter —
of the three hand-written seeds only Heist is now viable (Slugfest: `dominant_strategy`; Sprint: `no_skill_edge`), and the
agents' own *Break Rotation* now fails `no_skill_edge`. Verdicts were not softened to restore them.

## Living twin for concepts

`godot/ghost/concept.gd` re-implements the interpreter and agents. `tests/concept_parity.gd` replays Python-generated match
digests: 400 matches over the compiled concepts + 13 fuzzed grammar specs + one spec exercising every operator
(rnd, truncating division of negatives, min/max, `!`, `&&`, `||`, saturation) — 0 mismatches; negative controls (negated division,
off-by-one rnd) fail 40 matches each. `tests/concept_ui_smoke.gd` plays every compiled concept to the end through the real arena UI;
`ghost.foundry.replay` re-simulates those recorded sessions (seed + human actions) in Python: 0 digest mismatches.
Full suite: 40 tests (`python3 -m unittest discover -s tests`, Godot tests need `GODOT_BIN`).

## Run it

```bash
python3 -m ghost.foundry.run_discovery NAME [--no-inbox] [--gens 12] [--per-gen 48] [--seed N]   # discover+validate+report+compile
python3 -m ghost.foundry.check spec.json [--submit NAME]      # evidence tool for agents / humans proposing a concept
python3 -m ghost.foundry.memory_experiment
godot --path godot        # main scene → "Concept games (discovered)" → double-click → play against the adaptive agent
```

## What does not work yet

* **No human has played any of this.** "Viable" means "passes structural proxies", not "fun". Fitness saturates (best 1.000), so
  it cannot rank among the best concepts. The proxies were gamed repeatedly (by the evolution earlier, by my own agents' designs, by
  the red-team); each time I patched the metric, so the current metrics are tuned against known exploits and will have more.
* **"Genuinely new" is only measured relative to my 3 seeds and my own grammar.** Structural novelty ≠ originality; the DSL is a
  restricted space (two players, simultaneous moves, integer vars). The agents' designs are creative inside that space; the grammar
  loop mostly recombines known atoms. No LLM runs *inside* the loop — agents contributed through the inbox in separate steps.
* **The skill proxy rests on a myopic 1-ply adapter** with an author-supplied value heuristic. Engine-building games (the red-team's
  *Foundry Economy*) are wrongly flagged; relabelling actions still shifts some verdicts (Slugfest: 13 of 18 orders agree).
* **Discoveries are not yet wired into the persistent world.** The world kernel's NPC fights use the fixed combat family; concept
  games are matches. Making a discovered mechanic the world's duel resolver is the next integration.
* The playable arena is generic built-in UI (no art/audio); `assets_required.json` per concept lists the needs.
* Verified only on Linux/headless/xvfb, Godot 4.5. No CI.

## Next

1. Human rating loop: collect arena ratings (the hook records seed+actions+rating) and test which proxy, if any, predicts them.
2. Put an LLM agent *inside* the loop (propose → read flags → revise) via the inbox contract, scheduled per generation.
3. Deeper agents (2-ply / rollout) to fix the myopic skill proxy; Pareto fitness instead of a weighted sum.
4. Wire a discovered concept into the world kernel as the duel resolver, keeping the twin parity tests.
