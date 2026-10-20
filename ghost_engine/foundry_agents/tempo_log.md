# Tempo / commitment agent log

All numbers copied from `python3 -m ghost.foundry.check` output (fitness / flags / novelty_vs_seeds). Scratch generators lived in /tmp/t; final specs in /tmp/best.json and foundry_inbox/tempo.json.
Tempo emulation tricks: a `last` var set by a passive (`last = act(me)`) lets an action's cond forbid repeating itself (cooldown); `charge`/`mom`/`stage` vars are the charge-ups; `fuse` + passive tick is a delayed payoff.

## 1. Coil Duel (charge / release / parry / jab) - NOT submitted
Idea: jab > coil (strips charge), coil > parry (parry whiffs), parry > release (reflects charge), release > jab (big hit).
- v1: fitness 0.572, flags dead_actions (jab 96% of use), nov 0.56. Pure agents fall back to action 0 when release is illegal, which inflates jab.
- v2 (release cond charge>=1, parry riposte scaled by opp charge): 0.686 NONE nov 0.63, but parry 74% of use.
- sweeps: best 0.737 NONE nov 0.63, shares [0.29,0.17,0.01,0.53]. Release is ~1% used.
Learned: metric usage is dominated by fixed agents and a one-step-greedy adaptive agent, which undervalue conditional "setup" actions. Honest verdict: viable by flags but release is practically dead, so the charge->release cycle does not really exist (cycles=0). Weak.

## 2. Break Rotation (SUBMITTED, id break_rotation)
Idea: focus / slash / smash / dodge. slash interrupts smash, smash crushes dodge, dodge ripostes slash (RPS), focus builds momentum but loses to all attacks. Slash and smash cannot be repeated back to back (cooldown via `last`). Damage = base + momentum; landing a hit strips the victim's momentum, getting countered resets yours.
- 16 variants (hp, dmg, cooldown on/off, strip on/off): all NONE, fitness 0.83-0.90, nov 0.63-0.70; focus was dead (1-2% use) in all of them.
- focus tuning (mom gain / hp gain): (+2,0) 0.903; (+2,+2) 0.847; (+3,+1) **0.920** NONE nov 0.62 shares [0.11,0.39,0.36,0.14], cycles 4, dominance 0.17, length 11.2, leverage 0.52; (+1,+3) 0.869. Chose (+3,+1): all four actions live.
Learned: a safe "charge" move needs a real reason to exist (here: it maxes momentum in one go, so the next attack is +3). Honest note: skill edge 0.67 is the lowest part; novelty vs seeds is only 0.62 since it is an hp duel structurally.

## 3. Standoff (SUBMITTED, id standoff_nerve)
Idea: race to 3 points, nerve = ammo/composure. wait (+2 nerve), shoot (cost 1, scores vs wait/feint, wasted vs duck/shoot clash), duck (+1 nerve, drains shooter's nerve), feint (cost 1: scores vs duck, drains waiter's nerve).
- v1 (wait +1, feint free): 0.663 NONE but feint 88% use (feint nearly dominant), nov 0.84.
- v2 (feint costs nerve, wait +2, start 2): **0.765** NONE nov 0.84, shares [0.22,0.36,0.31,0.11], dominance 0.5, cycles 0, timeout_rate 0.18, length 11.6, interaction 0.80.
- other caps/starts: 0.700-0.765.
Learned: a free bluff action dominates; give it a resource cost. Honest note: cycles=0 and dominance 0.5 (duck is a very safe pure strategy), stalemate rate 0.18 is near the 0.3 flag threshold. Mind-game is real but shallow.

## 4. Slow Fuse (SUBMITTED, id slow_fuse)
Idea: delayed payoff. plant sets a 3-tick fuse on the opponent (explodes for 6, only if no fuse is running), defuse clears your own fuse and cancels an incoming plant, jab chips, rush deals 4 for 3 self-damage.
- first version: rush dominated (dominant_strategy on 5 of 8 variants).
- rush made expensive: fitness 0.737-0.772 NONE nov 0.65. Chosen hp 22, boom 6, jab 1, rush 4/cost 3: **0.772** NONE nov 0.65, shares [0.38,0.34,0.25,0.04].
Learned: delayed damage is a clean way to make commitment readable (the fuse is visible). Honest note: rush is effectively dead (4% use, borderline at the 5% liveness line), cycles=0, interaction 0.71 only. Closer to "three live actions" than a real 4-way mind-game.

## 5. Cash Chain (SUBMITTED, id cash_chain)
Idea: race to 12. build stage (combo), cash out stage^2 points, disrupt (denies a cash and gives +2, steals 2 stage from a builder, -1 vs hustle, otherwise costs 1 point), hustle (+1 safe).
- v1 (cash = 2*stage, disrupt free): all flagged stalemate (disrupt 70-90% use), 0.65-0.66.
- stage^2 payoff, build gives bonus point option, disrupt whiff cost: 8-12 variants, 0.52 (dead_actions) to 0.815.
- chosen (goal 12, build +1... see spec): **0.815** NONE nov 0.84, shares [0.73,0.14,0.14,0.0], cycles 1, timeout_rate 0.14, length 15.9.
Honest note: this is the weakest of the submitted ones. Hustle is 0% used by the agents (flag-wise "live" count passes at 3/4 only because of build/cash/disrupt) and build is 73% of use because pure agents fall back to action 0. The chain is rarely executed; I suspect part of the 0.815 is length/skill parts rather than real tempo play. Treat as metric-lucky.

## Overall learnings
- Fitness parts are driven by fixed pure-action agents, which fall back to action 0 when an action is illegal; conditional (charge-gated) actions therefore look dead. Keeping gated actions cheap to unlock helps.
- Cooldowns through `last` + RPS reactions (Break Rotation) gave the only design with real cycles (4) and all four actions live.
- Rankings by my confidence in real quality: Break Rotation > Standoff > Slow Fuse > Cash Chain.
