# Foundry run `autonomous` (generated)

seed 1 · 12 generations × 48 proposals · inbox OFF · 81.1s

## Loop vs random search (same evaluation budget)

| | evals | viable | MAP-Elites cells filled | best viable fitness (novel ≥0.15) | mean viable fitness |
|---|---|---|---|---|---|
| discovery loop | 549 | 222 | 73 | 1.000 | 0.760 |
| random control | 549 | 96 | 47 | 0.988 | 0.732 |

## Proposers (viable / proposed)

- crossover: 59/73
- grammar: 42/216
- mutation: 120/257
- seed: 1/3

## Failure taxonomy (preserved in failures.json; fed back into proposals)

- dominant_strategy: 159
- stalemate: 105
- dead_actions: 69
- predetermined: 51
- no_skill_edge: 50
- no_interaction: 45
- too_short: 29
- misleading_value: 19
- too_long: 17
- dominant_line: 15
- inert_action: 15
- chaotic: 2

## What the loop learned (atom memory)

| atom kind | trials | viable | viable rate | most common flag |
|---|---|---|---|---|
| ? | 13 | 10 | 0.77 | dominant_strategy |
| negate | 403 | 208 | 0.52 | dominant_strategy |
| gain | 346 | 174 | 0.50 | dominant_strategy |
| spend | 221 | 107 | 0.48 | stalemate |
| counter | 208 | 99 | 0.48 | dominant_strategy |
| hurt | 226 | 100 | 0.44 | stalemate |
| shield_up | 303 | 121 | 0.40 | dominant_strategy |
| steal | 173 | 67 | 0.39 | dominant_strategy |
| break | 208 | 80 | 0.38 | dominant_strategy |
| cool | 269 | 102 | 0.38 | dominant_strategy |
| risk | 233 | 79 | 0.34 | dominant_strategy |
| charge | 173 | 53 | 0.31 | stalemate |
| sabotage | 84 | 19 | 0.23 | dominant_strategy |

## Discoveries (validated on held-out seeds and unseen strategies)

### mu0250 — proposer `mutation`, gen 5

```
mu0250: score 0 [0..26], shield 0 [0..6]
  [0] negate0: my score += ((their action == 1) ? 6 : 0); my score += 1
  [1] negate1: my score += ((their action == 2) ? 3 : 0); my score += 1
  [2] gain2: my score += 2
  each round: my shield += -1
  ends: (my score >= 23) => I win; after 22 rounds higher 'score' wins
```
- train fitness 0.940; **holdout fitness 0.940 ± 0.000**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.00; novelty vs seeds 0.94
- live actions 3/3, interaction 1.01, leverage 0.30, length 8.9, skill edge 0.97, cycles 2
- lineage (competing versions, holdout fitness): gr0224(grammar/seed):0.93 → mu0250(mutation/goal):0.94

### mu0114 — proposer `mutation`, gen 2

```
mu0114: pos 0 [0..21], energy 2 [0..6], heat 0 [0..10]
  [0] cool+gain0: my heat += -3; my pos += 1
  [1] spend1 only if (my energy >= 1): my energy += -1; their pos += -5
  [2] risk2: my pos += 3; my heat += 1
  [3] break+gain3: their pos += ((their action == 2) ? -5 : -1); my pos += 1
  [4] negate4: my pos += ((their action == 3) ? 4 : 0); my pos += 1
  ends: (my heat >= 10) => I lose; (my pos >= 15) => I win; after 30 rounds higher 'pos' wins
```
- train fitness 0.966; **holdout fitness 0.979 ± 0.022**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.17; novelty vs seeds 0.68
- live actions 5/5, interaction 0.83, leverage 0.40, length 12.7, skill edge 0.89, cycles 3
- lineage (competing versions, holdout fitness): gr0086(grammar/seed):0.90 → mu0114(mutation/passive):0.98

### mu0108 — proposer `mutation`, gen 2

```
mu0108: pos 0 [0..21], energy 2 [0..6], heat 0 [0..10]
  [0] cool+gain0: my heat += -3; my pos += 1
  [1] spend1 only if (my energy >= 1): my energy += -1; their pos += -5
  [2] risk2: my pos += 3; my heat += 1
  [3] break+gain3: their pos += ((their action == 2) ? -5 : -1); my pos += 1
  [4] negate4: my pos += ((their action == 3) ? 4 : 0); my pos += 1
  [5] sabotage5: their energy += 2
  each round: my pos += 1
  ends: (my heat >= 10) => I lose; (my pos >= 15) => I win; after 30 rounds higher 'pos' wins
```
- train fitness 0.969; **holdout fitness 0.963 ± 0.011**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.75; novelty vs seeds 0.71
- live actions 5/6, interaction 0.60, leverage 0.31, length 8.4, skill edge 1.00, cycles 4
- lineage (competing versions, holdout fitness): gr0086(grammar/seed):0.90 → mu0108(mutation/add_action):0.96

### mu0294 — proposer `mutation/near-miss`, gen 6

```
mu0294: score 0 [0..26], heat 0 [0..10], fuel 3 [0..6]
  [0] gain0: my score += 2
  [1] negate1: my score += ((their action == 3) ? 5 : 0); my score += 1
  [2] break2: their score += ((their action == 4) ? -4 : -1)
  [3] gain3: my score += 3
  [4] negate4: my score += ((their action == 1) ? 2 : 0); my score += 1
  each round: my heat += -1
  ends: (my heat >= 10) => I lose; (my score >= 20) => I win; after 21 rounds higher 'score' wins
```
- train fitness 0.840; **holdout fitness 0.862 ± 0.002**, viable on 4/4 holdout seeds; extended dominance (10+ strategies) 0.00; novelty vs seeds 0.88
- live actions 3/5, interaction 0.83, leverage 0.36, length 10.9, skill edge 0.78, cycles 2
- lineage (competing versions, holdout fitness): gr0023(grammar/seed):0.72 → mu0194(mutation/near-miss/tweak):0.72 → mu0294(mutation/near-miss/swap_atom):0.86

