# Ghost Engine red-team report

All specs are saved next to this file as `redteam_*.json`; all numbers below were copied from tool output
(`python3 -m ghost.foundry.check foundry_agents/<file>` run from `ghost_engine/`). Reproduce everything with
`python3 foundry_agents/rt_prove.py` (task 1 evidence), `python3 foundry_agents/rt_bugs.py` (task 3), `python3 foundry_agents/rt_perm.py slugfest` (task 2).
Helpers: `rt_lib.py`, `rt_perm.py` (action-relabel invariance test), `rt_fuzz.py`, `rt_crashfuzz.py` (1500 random validate-passing specs: 0 crashes), `rt_det.py` (4 PYTHONHASHSEEDs: identical output: no nondeterminism found).
No files in `ghost/` or `godot/` were edited.

Root cause shared by most findings: **every metric except `dominance` is computed from a stationary/greedy proxy (the adapter and the author-supplied `value` heuristic), not from the win condition**, and the fight matrix `W` only ever plays the lower id as seat 0 (`W[(j,i)] = 1 - W[(i,j)]` is assumed, never measured).

---
## Task 1. Specs the pipeline calls VIABLE (flags NONE) that are degenerate

### 1A. `redteam_seat.json` "Raid Seat Bias": seat 1 wins every game (fooled: seat symmetry is assumed, never measured)
Rules (spec_text): `raid: my pts += (opp played bank ? 4 : 0); their pts = (their pts - 2)` plus `bank` (+2) and `guard`.
Effects are applied seat0-first, so a `"="` on the opponent overwrites seat 0's own `+=` of the same round but not seat 1's.
```
fitness=0.966 flags=NONE (viable) novelty_vs_seeds=0.94
metrics: {'dominance': 0.17, 'distinct_best_responses': 3, 'cycles': 3, 'live_actions': 3, 'n_actions': 3, 'timeout_rate': 0.0, 'length': 11.45, 'skill': 1.0, 'interaction': 0.99, 'leverage': 0.56}
```
Proof (rt_prove.py): adapter vs adapter, 300 seeds: `seat0 wins=0 seat1 wins=300 draws=0`. This spec has the highest fitness of my set (0.966).
Why fooled: `evaluate` only plays pair (i,j), i<j, and infers the swapped seat as `1-W`. Any engine-order asymmetry is invisible; `dominance` sees "higher id beats lower id" as ordinary counterplay.

### 1B. `redteam_dice.json` "Dice Duel": decided by `d6`, choice worth almost nothing (fooled: `skill`, `leverage`, `interaction`)
Four actions that are all "my pts += d6" with a +1 bonus if the opponent picked a specific action.
```
fitness=0.624 flags=NONE (viable) novelty_vs_seeds=0.87
metrics: {'dominance': 0.5, 'distinct_best_responses': 5, 'cycles': 0, 'live_actions': 2, 'n_actions': 4, 'timeout_rate': 0.0, 'length': 8.52, 'skill': 0.6, 'interaction': 1.25, 'leverage': 0.07}
action_shares: [0.0, 0.14, 0.0, 0.86]
```
Proof: best fixed policy (roll_safe) vs plain roll over 400 seeds: `wins=170 losses=180 draws=50` (the "best" action loses). Adapter vs random: 210/126.
Why fooled: `skill` (0.60 >= 0.55) is the adapter's mean win rate against 8 policies, several of which are weak/identical, so a tiny edge passes; `interaction` is computed on expected payoffs (rnd -> n//2, variance erased), so the +1 cosmetic bonuses give it 1.25 (the ratio is unbounded, see fix 7); `leverage` 0.07 clears the 0.05 floor by 0.02. `dead_actions` passes at exactly the minimum (2 of 4 live). Note dice are a single roll per player per round: a human would call this "roll d6 four times".

### 1C. `redteam_decoy.json` "Style Points": a live-looking cosmetic action (fooled: `liveness`, `skill`)
`flourish` / `showboat` only change `style`, which is not in any end rule; `value` weights style 3 so the adapter loves it.
```
fitness=0.850 flags=NONE (viable) novelty_vs_seeds=0.94
metrics: {'dominance': 0.0, 'distinct_best_responses': 3, 'cycles': 3, 'live_actions': 3, 'n_actions': 5, 'timeout_rate': 0.1, 'length': 11.68, 'skill': 0.85, 'interaction': 0.46, 'leverage': 0.41}
action_shares: [0.35, 0.0, 0.2, 0.42, 0.03]
```
Proof: adapter usage vs always-bank over 50 games = `[100, 0, 0, 200, 0]`: 2/3 of its moves are the no-op `flourish`; `raid` is never played (dead), yet `live_actions=3` (flourish counts). Always-flourish loses 0-100 to always-bank and always-guard, i.e. the "live" action never helps win.
Why fooled: liveness = share of adapter *usage* >= 5%; usage is driven by `value`, which the spec author controls, not by anything that affects the result. Skill stays 0.85 because the baselines are dumb enough to lose even to a bot that wastes 2/3 of its turns.

### 1D. `redteam_combo.json` "Unblockable Combo": a 2-move trick wins 100% (fooled: `dominance` only tests stationary policies)
`charge` sets charge=2 (passive decays 1), `finisher` (needs charge>=1) deals 12 = instant kill, unblockable.
```
fitness=0.720 flags=NONE (viable) novelty_vs_seeds=0.50
metrics: {'dominance': 0.42, 'distinct_best_responses': 3, 'cycles': 2, 'live_actions': 2, 'n_actions': 4, 'timeout_rate': 0.09, 'length': 9.61, 'skill': 0.74, 'interaction': 0.36, 'leverage': 0.52}
action_shares: [0.24, 0.0, 0.76, 0.0]
```
Proof (scripted bot: round0 charge, round1 finisher, seat 0) against all 12 pipeline policies, 20 seeds each: 20/0/0 wins/losses/draws vs always0..5, cycle, adapter, counter, mirror, greedy; 19/0/1 vs random. The adapter and cycle can never execute the combo (finisher never legal for always-i; charge has zero heuristic payoff), so the engine reports `dominance 0.42` and 2/4 live actions (finisher and charge have 0.0 share).
Why fooled: dominance = worst case of always-action-i/cycle/random. Any non-stationary dominant line (setup then payoff, with period != n for cycle) is invisible.

### 1E. `redteam_inert_rnd.json` "Slugfest Sudden Death": a rule that is printed but can never fire
Slugfest plus end rule `(d100 < 30) => I win` (the rules text printed by `spec_text` says so).
```
fitness=0.800 flags=NONE (viable) novelty_vs_seeds=0.08
metrics: {'dominance': 0.5, ... 'length': 11.95, 'skill': 0.89, 'interaction': 0.56, 'leverage': 0.33}   # identical to plain Slugfest
```
Proof: 0 / 300 games ended by the rnd rule. Cause: `step()` evaluates end rules with `mode=1` (expected value), so `rnd n` is the constant n//2 (here 50). See bug B3.

---
## Task 2. GOOD games that get FLAGGED (false negatives)

### 2A. `redteam_fn_slugfest_perm.json`: the repository's own seed Slugfest with two actions swapped (`rest` <-> `bomb`) is flagged `dominant_strategy`
Identical rules, only list order changed (`rt_perm.permute` rewrites every `["act",..]==k` reference).
```
Slugfest (original):           fitness=0.800 flags=NONE (viable)
Slugfest relabeled:            fitness=0.689 flags=['dominant_strategy']
metrics: {'dominance': 1.0, 'distinct_best_responses': 2, ... 'live_actions': 4, ... 'skill': 0.83, 'interaction': 0.54, 'leverage': 0.26}
```
`rt_perm.py slugfest` output: `[((), 15), (('dominant_strategy',), 3)]`, i.e. 3 of the 18 valid orderings (24 permutations minus those putting a conditional action at index 0) of the same game are rejected.
Why: `dominance` includes the `cycle` baseline, whose behaviour is the action *order*. Original order: cycle plays strike, guard, bomb, rest and draws vs always-bomb (W=0.5). Swapped order: cycle plays rest before bomb, loses to always-bomb (W=1.0), so always-bomb "dominates". Always-bomb also falls back to action 0 when energy runs out, another order-dependent artifact.

### 2B. `redteam_fn_sprint_perm.json`: seed Sprint with `trip` moved to index 0 is flagged `stalemate`
```
fitness=0.651 flags=['stalemate'] novelty_vs_seeds=0.00
metrics: {'dominance': 0.5, ..., 'timeout_rate': 0.33, 'length': 19.45, 'skill': 0.75, 'interaction': 1.1, 'leverage': 0.36}
```
`rt_perm.py sprint`: `[((), 16), (('stalemate',), 2)]`. Why: `sanitize` replaces an illegal action by action 0, and the always-i baselines (`dash` needs fuel) fall back to it constantly. With the non-progressing `trip` at index 0, six policy pairs (list printed by my script: (0,1),(0,2),(0,3),(0,6),(0,7),(2,6)) never finish, so timeout_rate=0.33 > 0.30. `timeout_rate` counts stalls between dumb baselines, not between competent players (the adapter-mirror length 19.45 is not even the cause).

### 2C. `redteam_fn_economy.json` "Foundry Economy": an engine-building game flagged `dead_actions` + `no_skill_edge` purely because the myopic adapter never invests
```
fitness=0.636 flags=['dead_actions', 'no_skill_edge'] novelty_vs_seeds=0.88
metrics: {... 'live_actions': 1, 'n_actions': 4, ... 'skill': 0.53, 'interaction': 0.26, 'leverage': 0.26}
action_shares: [1.0, 0.0, 0.0, 0.0]
```
Mills (passive income), muster, raid-vs-block counterplay are all real, but the 1-ply greedy adapter sees `build_mill` as -4 gold and always hoards. Knife-edge proof (rt output): changing only the author's `value` weight on `mills`: 2 -> flags both; 3 -> flags both; 4 -> viable with shares `[0.94, 0, 0, 0.06]` (still 94% hoard). So the verdict flips on one number in `value`, while play quality is the same.
(Reference: `redteam_fn_rps.json` best-of-3 RPS is correctly viable at fitness 0.908, `redteam_fn_fencing.json` is viable; `rt_perm.py` finds 0 flips for RPS (6 orders) and fencing (96 orders), so the relabel problem is specific to games with illegal-fallback or order-sensitive cycle behaviour.)

---
## Task 3. dsl.py correctness findings (all reproduced by `rt_bugs.py`; output pasted below)

### Interpretation of the bug output
| id | finding | severity |
|----|---------|----------|
| B1 | **Resolution is not simultaneous for `=`**. Effects apply in list order: seat0 action, seat1 action, seat0 passive, seat1 passive. Two `=` on one var: seat 1 wins. `=`(snapshot-1) on seat 0 erases seat 0's same-round `+=`, but not on seat 1. Passive `=` overrides action effects. Drives spec 1A. | high |
| B2 | `cond` is evaluated by `legal()` with `acts=[0,0]`; `["act",..]` in a cond is constant 0, so the action printed "only if their action > 0" is never legal. Validator accepts it. | high |
| B3 | `rnd` in `end` rules (and conds) uses mode 1 => constant n//2. Printed rule "d100 < 10" never fires; "d100 >= 50" fires every game at round 1. (Godot twin copies the same behaviour: `int(e[1]) / 2`.) Spec 1E. | high |
| B4 | No bound on integer literals/products. Python uses bignums; GDScript int64 wraps. 3037000500*3037000500 is positive in Python (clamped to max) and negative after int64 wrap, so the `>0` end rule would differ between engines. | medium (parity) |
| B5 | Clamp only after all effects: at the cap, a +9 heal swallows a -4 hit completely (hp stays 10). Sequential semantics would leave hp 6..10 depending on order. Unexpected for authors; also makes "overheal" a free shield. | medium |
| B6 | `validate()` raises uncaught `AttributeError` when an action is not a dict (`except (KeyError, TypeError, ValueError)` misses it). Also accepts a list as an action name (returns [] but `spec_text` joins fail later), float max_rounds=3.5, `True` as var init. | low-medium (the loop's inbox path catches only json errors; one bad agent file would kill `ingest_inbox` -> `run`) |
| B8 | Expression size is limited by depth only: a 16-effect spec of depth-10 sums validates and makes `evaluate(fights=1)` take 5.8 s (normal 0.1 s); depth 12 with 6 actions is ~100x worse. An agent can DoS the discovery loop through the inbox. | medium |
| B9 | `seed_state` masks to 31 bits so seed and seed+2^31 alias (harmless today). | info |
Checked and found OK: truncating `tdiv` (-7/2=-3, 7/-2=-3, x/0=0 identical to test), snapshot semantics of expression evaluation, RNG draw order, determinism (identical `evaluate()` + match digests under PYTHONHASHSEED 0/1/2/999), 1500 random validate-passing specs through `evaluate()` (0 crashes, no non-termination because `max_rounds<=60` is enforced by `validate` and `evaluate` calls it; but `agents.play`/`dsl.step` themselves never validate).

### rt_bugs.py output
```
B1 '=' vs '+=' ordering: mirrored play is NOT symmetric (seat 1's effects apply last)
  both play raid from x=5/5: seat0.x=4 seat1.x=6  (symmetric would be equal)
  both play set(opp.x=0, me.x=9): seat0.x=0 seat1.x=9  -> last writer (seat 1) always wins the collision
B2 'cond' is evaluated with acts=[0,0] -> any ['act',..] in cond is silently constant
  spec text:   [1] needs_opp_act only if (their action > 0): my y += 10
  legal(action1) = False (always False: can never be played)
B3 'rnd' in end/cond is evaluated in expected mode (n//2): rule text says d100 but value is constant 50
  rule:   ends: (d100 < 10) => I win; after 5 rounds higher 'x' wins
  games ended by the 10% chance rule: 0 / 200 (expected ~ 1-(0.9^5) = 41%)
  rule 'd100 >= 50' ends every game at round [1, 1, 1] (true intent: ~50%/round)
B4 no int64 guard: Python bignum vs GDScript int64 wraparound (cross-engine divergence)
  validate(): []
  python x=4611686018427387904 (clamped); true product=9223372037000250000; int64-wrapped product=-9223372036709301616 (sign differs => GDScript would pick different branch)
B5 clamp happens only after ALL effects: overheal at cap absorbs damage; no per-effect clamping
  seat0 at cap 10 plays heal(+4) while hit(-4) lands: hp=10 (sequential clamp would give 10-4=6 then +4=10, or 10 then -4=6)
  heal(+9) vs hit(-4) at cap: hp=10 -> the hit is fully absorbed by wasted overheal (net +5 clamps to 10)
B6 validate() crashes (uncaught AttributeError) on malformed-but-parseable specs
  action is a string     -> CRASH AttributeError: 'str' object has no attribute 'get'
  fx entry is a dict     -> returned ["bad effect {'a': 1}"]
  end rule is an int     -> returned ["malformed spec: TypeError('cannot unpack non-iterable int 
  vars is an int         -> returned ['malformed spec: TypeError("\'int\' object is not iterable"
  passive None           -> returned ['malformed spec: TypeError("\'NoneType\' object is not iter
  value entry int        -> returned ["malformed spec: TypeError('cannot unpack non-iterable int 
  name is a list         -> returned []
  unhashable var name    -> returned ['malformed spec: TypeError("unhashable type: \'list\'")']
  max_rounds NaN         -> returned ['max_rounds out of range 3..60']
  tiebreak list          -> returned ['tiebreak var unknown']
  spec is a list         -> returned ["malformed spec: TypeError('list indices must be integers o
B7 validate accepts specs that crash/misbehave at play time
  max_rounds=True -> ['max_rounds out of range 3..60']
  var init True accepted -> []
  float max_rounds 3.5: []
B8 expression SIZE is bounded only by depth (12): 2^11 leaf evals per effect; a 'valid' spec can make evaluate() take minutes
  tree depth  4: validate=[]  20 payoff() calls 0.000s
  tree depth  8: validate=[]  20 payoff() calls 0.005s
  tree depth 10: validate=[]  20 payoff() calls 0.018s
  evaluate(fights=1), 4 actions x 4 depth-10 effects: 5.9s (normal spec ~0.1s); validate=[]
B9 xorshift seed_state(seed): seeds 0 and 2^31 alias (seed masked to 31 bits)
  seed_state(5)==seed_state(5+2**31): True
```

### rt_prove.py output (task 1 evidence)
```
== SEAT BIAS (redteam_seat.json): adapter vs adapter, 300 seeds
 seat0 wins=0 seat1 wins=300 draws=0
 always-raid mirror: seat0=0 seat1=0 draws=300
== COMBO (redteam_combo.json): scripted 'charge, finisher' bot in seat 0 vs all 12 pipeline policies, 20 seeds each
  vs always0   win=20 loss=0 draw=0
  vs always1   win=20 loss=0 draw=0
  vs always2   win=20 loss=0 draw=0
  vs always3   win=20 loss=0 draw=0
  vs always4   win=20 loss=0 draw=0
  vs always5   win=20 loss=0 draw=0
  vs cycle     win=20 loss=0 draw=0
  vs random    win=19 loss=0 draw=1
  vs adapter   win=20 loss=0 draw=0
  vs counter   win=20 loss=0 draw=0
  vs mirror    win=20 loss=0 draw=0
  vs greedy    win=20 loss=0 draw=0
== DICE (redteam_dice.json): adapter(seat0) vs random win/loss over 400 seeds; and result vs sum of own dice
 adapter wins=210 random wins=126 draws=64  (choice worth only ~21% edge)
 best fixed (roll_safe) vs plain roll: wins=170 losses=180 draws=50
== DECOY: how many adapter moves are the cosmetic action?
 adapter usage (bank,raid,guard,flourish,showboat): [100, 0, 0, 200, 0]
 always-flourish (never touches pts) vs always-bank: wins=0 losses=100 draws=0
 always-flourish (never touches pts) vs always-guard: wins=0 losses=100 draws=0
```

---
## Prioritized fixes
1. **Measure seat symmetry** (metrics.py): play each ordered pair in both seats and compare `W[(i,j)]` with `1-W[(j,i)]`; add flag `seat_bias` when the adapter-mirror p0/p1 win rate differs by more than e.g. 0.15. Kills 1A immediately.
2. **Make resolution truly simultaneous** (dsl.py `_apply`): accumulate all `+=` per (player,var) first, then apply `=` by a deterministic symmetric rule (e.g. forbid `=` on `opp`, or error/validate-reject two `=` writers, or let passive `=` be the only writer). Add a validator check rejecting `=` targeting `opp` or reject specs where both players' action fx write the same var with `=`.
3. **Ground metrics in the win condition, not in `value`**: compute liveness/interaction from outcome sensitivity (win-rate swing when the action is replaced), not adapter usage and heuristic payoffs. A static check that every var in `value` can reach an `end`/`tiebreak` var through effects (reject/flag decoy vars) fixes 1C. Also flag actions whose fx touch only vars not read by any end/cond/tiebreak/other effect.
4. **Add non-stationary and relabel-invariant baselines**: evaluate dominance against the best response computed by search (e.g. depth-2 expectimax or a small hill-climb over scripted 2-3 move sequences) and make `cycle` order-independent (average over random permutations of actions). Run the metric under 2-3 random action permutations and take the worst/median flags: this fixes 2A/2B and catches 1D.
5. **Stalemate/timeout should be measured between competent policies** (adapter vs adapter, adapter vs counter), not across all baseline pairs where `sanitize` falls back to action 0. Or make the fallback "nearest legal" rather than action 0.
6. **Fix `rnd` in end/cond (B3)**: either reject `rnd` inside `end`/`cond` in `validate`, or evaluate `end` in rolled mode (and do the same in godot/ghost/concept.gd). Likewise reject `["act",..]` inside `cond` (B2) or pass the real acts (impossible pre-commit; reject is correct).
7. **Bound `interaction`** to [0,1] (`min(1, inter/(mag))`; it reached 1.25 in 1B) and require `skill` to beat the *best* weak baseline by a margin, not the mean of 8 policies. Compute `skill` against a stronger opponent set (counter/greedy/mirror are defined in agents.py but unused by metrics).
8. **Put a luck metric next to leverage** (variance of result given the same action sequence across seeds; flag games where >X% of results are decided by `rnd`). 1B passes `predetermined` with 0.07 vs a 0.05 floor.
9. **Harden validate()**: catch `AttributeError`/`Exception` around the whole body, require action to be a dict with str name, require `isinstance(x,int) and not isinstance(x,bool)` for var/max_rounds, bound literals to +-2^31 and total node count (e.g. <= 200 per expression, <= 2000 per spec), and clamp-with-check intermediate products to int64 range to keep the GDScript twin identical (B4, B6, B8).
10. **Document or change clamp semantics** (B5): either clamp per effect group or state "overheal is wasted before damage is applied"; add a regression test.
11. **Wire robustness into `viable`** in loop.py: archive admission is `not rec["flags"]` from one seed; `Foundry.holdout()` (fresh seeds + mirror/greedy/counter) is only a post-hoc report and still has no seat swap, relabel or scripted-sequence test. Require flags to be absent under >=2 evaluation seeds and 2 action orderings (and the seat-swap check from fix 1) before archiving.

## Five-line summary
1. Five specs pass with flags NONE yet are bad: seat-1-always-wins (300/300), d6-decided, cosmetic-action-as-"live", unblockable 2-move combo (20/20 vs every policy), and a printed-but-inert `d100` rule.
2. Metrics are proxies of the author's `value` heuristic and of stationary baselines; seat symmetry and non-stationary strategies are never tested.
3. The repo's own seeds fail when merely relabelled (Slugfest -> dominant_strategy, Sprint -> stalemate) and an engine-builder is flagged only because the greedy adapter is myopic (verdict flips with one `value` weight).
4. dsl.py: `=` effects resolve in seat order (not simultaneous), `rnd`/`act` in end/cond are constants, no int64 bound vs GDScript, clamp-after-sum overheal shield, validate() crashes on a non-dict action, and expression size allows slow-DoS; determinism, tdiv and snapshot semantics held up.
5. Top fixes: measure both seats, forbid/define `=` collisions, derive liveness from outcome sensitivity (not `value`), make baselines order- and strategy-robust, harden validate(); details and runnable repros are in this file and `foundry_agents/rt_*.py`.
