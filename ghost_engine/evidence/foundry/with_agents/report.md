# Foundry run `with_agents` (generated)

seed 2 · 12 generations × 48 proposals · inbox ON · 82.0s

## Loop vs random search (same evaluation budget)

| | evals | viable | MAP-Elites cells filled | best viable fitness (novel ≥0.15) | mean viable fitness |
|---|---|---|---|---|---|
| discovery loop | 571 | 235 | 73 | 0.998 | 0.773 |
| random control | 571 | 105 | 52 | 0.953 | 0.685 |

## Proposers (viable / proposed)

- agent: 6/8
- crossover: 53/72
- grammar: 34/216
- mutation: 141/272
- seed: 1/3

## Failure taxonomy (preserved in failures.json; fed back into proposals)

- dominant_strategy: 144
- stalemate: 100
- predetermined: 55
- dead_actions: 53
- no_skill_edge: 45
- misleading_value: 43
- no_interaction: 40
- dominant_line: 29
- inert_action: 18
- too_short: 18
- too_long: 13
- chaotic: 4

## What the loop learned (atom memory)

| atom kind | trials | viable | viable rate | most common flag |
|---|---|---|---|---|
| ? | 23 | 18 | 0.78 | dominant_strategy |
| charge | 299 | 133 | 0.44 | dominant_strategy |
| steal | 295 | 129 | 0.44 | dominant_strategy |
| counter | 338 | 143 | 0.42 | dominant_strategy |
| negate | 258 | 104 | 0.40 | dominant_strategy |
| sabotage | 235 | 86 | 0.37 | dominant_strategy |
| risk | 219 | 80 | 0.37 | dominant_strategy |
| cool | 237 | 82 | 0.35 | dominant_strategy |
| spend | 178 | 61 | 0.34 | dominant_strategy |
| hurt | 203 | 69 | 0.34 | stalemate |
| gain | 235 | 76 | 0.32 | dominant_strategy |
| shield_up | 221 | 65 | 0.29 | stalemate |
| break | 57 | 11 | 0.19 | dominant_strategy |

## Discoveries (validated on held-out seeds and unseen strategies)

### mu0454 — proposer `mutation`, gen 9

```
mu0454: gold 2 [0..20], rep 2 [0..5]
  [0] trade: my gold += ((their action == 0) ? 3 : ((their action == 1) ? -1 : 1)); my rep += 1
  [1] swindle: my gold += ((their action == 0) ? 4 : 0); their gold += ((their action == 0) ? -2 : 0); my rep += -2
  [2] embargo only if (my rep >= 2): my gold += ((their action == 1) ? 3 : 0); their gold += ((their action == 0) ? -1 : 0)
  [3] hoard: my gold += 1; my rep += ((their action == 1) ? 1 : 0)
  [4] counter4: their gold += ((their action == 3) ? -3 : 0); my gold += ((their action == 3) ? 1 : 0)
  each round: my gold += 1
  ends: (my gold >= 14) => I win; after 25 rounds higher 'gold' wins
```
- train fitness 0.974; **holdout fitness 0.971 ± 0.029**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.50; novelty vs seeds 0.90
- live actions 5/5, interaction 0.89, leverage 0.41, length 7.0, skill edge 1.00, cycles 2
- lineage (competing versions, holdout fitness): ag0001(agent:nonCombat/seed):0.83 → mu0312(mutation/add_action):0.95 → mu0454(mutation/passive):0.97

### mu0213 — proposer `mutation`, gen 4

```
mu0213: cash 5 [0..28], focus 0 [0..5]
  [0] shield_up0: my focus += 2; my cash += ((their action == 2) ? 3 : 0)
  [1] negate+cool1: my cash += ((their action == 1) ? 4 : 0); my cash += 1; my focus += -3
  [2] hurt2: their cash += -2
  [3] shield_up3: my focus += 2; my cash += ((their action == 0) ? 3 : 0)
  ends: (my cash >= 24) => I win; after 17 rounds higher 'cash' wins
```
- train fitness 0.936; **holdout fitness 0.922 ± 0.015**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.00; novelty vs seeds 0.89
- live actions 4/4, interaction 0.85, leverage 0.26, length 15.4, skill edge 1.00, cycles 3
- lineage (competing versions, holdout fitness): gr0103(grammar/seed):0.93 → mu0213(mutation/goal):0.92

### mu0436 — proposer `mutation`, gen 9

```
mu0436: cash 5 [0..24], shield 0 [0..6], fuel 3 [0..6], focus 0 [0..5]
  [0] steal0: their cash += -2; my cash += 2
  [1] risk1: my cash += 5; my shield += 1
  [2] spend+sabotage2 only if (my fuel >= 3): my fuel += -6; their cash += -9; their shield += 2
  [3] counter3: their cash += ((their action == 1) ? -6 : 0); my cash += ((their action == 1) ? 3 : 1)
  [4] negate4: my cash += ((their action == 5) ? 5 : 0); my cash += 1
  [5] counter+gain2: their cash += ((their action == 0) ? -4 : 0); my cash += ((their action == 0) ? 2 : 0); my cash += 2
  ends: (my cash >= 18) => I win; after 18 rounds higher 'cash' wins
```
- train fitness 0.958; **holdout fitness 0.952 ± 0.029**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.50; novelty vs seeds 0.75
- live actions 5/6, interaction 0.61, leverage 0.21, length 6.5, skill edge 0.72, cycles 8
- lineage (competing versions, holdout fitness): gr0025(grammar/seed):0.95 → mu0069(mutation/tweak):0.96 → mu0152(mutation/tweak):0.96 → mu0295(mutation/tweak):0.95 → cx0369(crossover/crossover):0.97 → mu0436(mutation/swap_atom):0.95

### mu0250 — proposer `mutation`, gen 5

```
mu0250: cash 5 [0..24], shield 0 [0..6], fuel 3 [0..6], energy 2 [0..6]
  [0] steal0: their cash += -2; my cash += 2
  [1] risk1: my cash += 5; my shield += 1
  [2] energy_play2: their energy += 2
  [3] counter3: their cash += ((their action == 1) ? -6 : 0); my cash += ((their action == 1) ? 3 : 0)
  [4] negate+charge4: my cash += ((their action == 3) ? 6 : 0); my cash += 1; my fuel += 3
  ends: (my cash >= 18) => I win; after 18 rounds higher 'cash' wins
```
- train fitness 0.877; **holdout fitness 0.890 ± 0.016**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.00; novelty vs seeds 0.85
- live actions 3/5, interaction 0.68, leverage 0.28, length 6.9, skill edge 1.00, cycles 3
- lineage (competing versions, holdout fitness): gr0025(grammar/seed):0.95 → mu0069(mutation/tweak):0.96 → mu0250(mutation/add_var):0.89

