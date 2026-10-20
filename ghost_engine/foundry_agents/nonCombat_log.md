# nonCombat log (non-hp-duel concepts)
Scripts that generated the specs: /tmp/nc/*.py (d1..d7). Submitted file: /tmp/best.json -> foundry_inbox/nonCombat.json.

## Submitted (all flags NONE, novelty 0.84-0.86)
| id | idea | fitness | novelty |
|---|---|---|---|
| parley_trade | negotiation / trust: trade, swindle, embargo (rep-gated), hoard; first to 14 gold | 0.834 | 0.84 |
| borderlands_v2 | territory: settle / muster / march (RPS-like vs garrison and muster) ; first to 10 land | 0.988 | 0.86 |
| silent_auction_v2 | sealed bid: higher action index wins the round's points, bids cost coin, pass banks coin | 0.771 | 0.84 |
| rope_tug | tug-of-war on own ground: haul/heave/brace/yank with reactive counters | 0.795 | 0.84 |

## Iterations
1. First pass (d1): Silent Auction 0.735 NONE (dominance 0.83, borderline); Rope Tug 0.795 NONE. Both viable at once.
2. d2 new ideas: Parley 0.692 dead_actions (embargo took 91% of play: +1/+2 gold safe) ; Borderlands 0.672 NONE but muster 0% use ; Metronome Combo 0.451 dominant+dead (disrupt gave +1 score free, 100% use) ; Arms Parade 0.637 NONE, stalemate 0.23, parade 74%.
3. d3: embargo base gold 0 (+3 only if opp swindles) -> Parley 0.834 NONE. Disrupt no longer scores -> Metronome 0.713 stalemate/too_long (timeout .32, length 27). Parade = max(0,tech-opp shield) -> Arms 0.582 stalemate.
4. d4-d5: lowered score targets (9); Borderlands march stronger (-3/-4 on opp, +2 me) with garrison as punisher -> 0.937, cycles 3, dominance 0.17. Arms with shield decay: fortify dead.
5. d6: garrison cheap/punishing, Metronome disrupt rewards only successful denial of a bank (+2) -> Metronome 0.751 NONE (timeout exactly 0.30, borderline). Arms with tech-lead passive -> dominant_strategy 1.0 (0.583).
6. d7: muster +3 troops -> Borderlands 0.988 with balanced usage (29/18/24/29%). Auction costs 1/2/4 -> 0.771, dominance 0.67 (was 0.83). Auction v3 (pass +3) worse, dominance 0.83.

## Learned
- Reactive effects ("if their action == X") are the main source of interaction; a safe always-on positive action (embargo, disrupt, parade) quickly becomes dominant, fix by making its payoff conditional on the opponent's choice.
- Race-to-N win conditions with symmetric defensive actions drift into stalemate (Arms Parade, Metronome); lower N or reward successful denial.
- Cycles (RPS structure) appear naturally in Borderlands: march beats muster, garrison beats march, settle/muster punish garrison.

## Honest notes / weak designs
- Not submitted: Metronome Combo (viable by 0.751 but timeout_rate 0.30 sits on the flag threshold, disrupt 57% of use, slide only 7%: weak) and Arms Parade (best variant dominant_strategy; others stalemate). Both left in /tmp/nc.
- parley_trade: hoard is 60% of usage, so it is the practical default and the "trust/rep" variable matters little; 'rep' mostly gates embargo. Metrics happy, design shallow.
- rope_tug: the "tug" is actually first-to-10 own ground with attacks on the opponent's ground; closer to a race with interference than a true shared rope. Lowest skill edge (0.65).
- silent_auction_v2: the mid-bid (bid_mid) is least used, pass gives coin +2 and nothing else; metric dominance 0.67 is acceptable but the all-in bid_high is strong.
- borderlands_v2: ends also on land<=0 (a loss condition by elimination of territory), still territory-framed. Fitness 0.988 includes 4 cycles; part of that is metric-friendly RPS structure. Metrics are structural proxies, not fun.
