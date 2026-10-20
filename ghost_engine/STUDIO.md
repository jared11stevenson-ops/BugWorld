# Ghost Engine Studio — the repeatable three-game production cycle

The universe is temporary. The games are permanent. The studio keeps learning.

```
python3 -m studio new-cycle [--prompt "any inspiration words"] [--seed N]     # random inspirations if no prompt/seed
python3 -m studio status
```

One command runs a whole cycle in about 2 minutes (4 cores, Godot 4.5 headless/xvfb) and archives the result in `archive/cycle_NNN/`.
`--quick` runs a small smoke cycle in /tmp and never touches the archive or the knowledge store.

## The cycle (what each stage really does)

| # | Stage | Implementation | Output |
|---|---|---|---|
| 1 | Inspiration | `studio/inspiration.py`: 49 real phenomena (9 fields), each with true one-line fact + abstract dynamics; 3 from distinct fields (random, or biased by prompt words) | 3 inspirations |
| 2 | One universe | `studio/universe.py`: name, 3 factions, 6 towns, palette, physical **law** (pulse/wells/drift) derived from the dynamics; **evolutionary search** over world rules (population 16 × 12 generations × 3 worlds × 600 ticks) then **72 branching alternate histories** (fork ticks × interventions × seeds); richest history becomes canon, pivotal events are mined from causal chains | universe.json, chronicle |
| 3 | **Idea exploration** (`studio/ideas.py`, replaces the old genre pool `studio/pool.py`, kept only as legacy): the universe's fused elements unlock families and modules; every simulatable candidate is played by tiered bots; scored on playability, depth, novelty vs every shipped idea, and fit to *each* inspiration; top idea of three different families is built | three ideas |
| 3a | *Trials* (strategy duel campaign) | `ghost.foundry` discovery loop, tilted by the universe's dynamics; 3 discovered concepts themed with universe vocabulary; escalating rivals | Godot project |
| 4 | *Steward* (world-sim) | the persistent world kernel with the evolved rules; influence points, previews on forked timelines, limited rewinds, drawn map; target = do-nothing timeline × 1.35 | Godot project |
| 5 | *Expedition* (real-time arcade, 2D or **3D**) and *Cordon* (**epidemic containment strategy**, new) | deterministic GDScript core with the universe's law; **difficulty evolved by headless Godot simulation** of a skilled and a novice bot, re-evaluated on fresh seeds each generation and validated on held-out seeds | Godot project |
| 6 | Verification gate | `studio/verify.py`: per game — self-test through the game's real code paths, no script errors, assets present, non-blank screenshots, Python twin of the simulation (campaign sessions replayed, steward digest+score replayed, arcade held-out skill/novice gap) | pass/fail per check |
| 7 | Archive | `archive/cycle_NNN/{games/*, evidence, universe.json, CHRONICLE.md, manifest.json}`; only games passing every check are listed as released | permanent record |
| 8 | Retrospective + RESET | `studio/retro.py` stores universe-independent lessons/priors/budget changes; `reset_state()` deletes the temporary universe state and asserts nothing universe-specific leaked into knowledge | `studio/knowledge/knowledge.json` |

Agent roles and their honest status are in `studio/agents.py` (programmatic stages with acceptance checks; LLM agents plug in through the foundry inbox).

## Pass 2 — "the body": plague / purge (cycle 3)

New capabilities added in this pass, each verified:

* **Genre pool** (5 genres, 4 families) with novelty-aware selection; cycle 3 chose Cordon + Expedition 3D + Trials for the prompt *"The Plague / the Purge"*.
* **Cordon** — new genre: deterministic integer SIR-style epidemic on a town network; quarantine / treat / **purge** (burn a town: capped, costs your conscience).
  GDScript core + Python twin (final-state digest parity), skilled/novice bots, difficulty tuner. Purge cap rule is tested through the real action path.
* **3D + animation** — *Expedition 3D* renders the arcade core as a real 3D scene: procedural low-poly skyline and props, animated figure
  (limb swing, bob, flicker), pulsing/spinning emissive objects, particle bursts, camera shake, per-law visuals. Test asserts the 3D node pools match simulation state.
* **New physical laws** — *contagion* (spreading infection zones that crystals cure) and *purge* (fire wall with a moving gap), in core, bots and both views.
* **Audio** — 12 SFX, layered mood music (drone, pad, bass, heartbeat, hats, arpeggio; calm/tense/dread), ambient bed; mood derived from the universe law.
* **Lore from simulation** (`studio/lore.py`) — faction personalities from canon-history statistics, towns, prologue, epilogues; shown in the games.
* **Human feedback pipeline** — every game ends with a 1–5 rating written to `user://feedback.jsonl`; `python3 -m studio feedback import FILE` aggregates into knowledge (self-test records ignored).
* **Polish** — shell fade transitions, breathing emblem, unified theme; unique town names; compatibility renderer for portable GL.
* Inspiration bank: 60 entries (11 plague/purge-related: Black Death, quarantine, Snow's cholera map, SIR model, smallpox eradication, fire ecology, Great Fire of London, apoptosis, herd immunity, Justinian plague, humoral medicine) with real one-line facts; prompts select one entry per prompt word.

### Cycle 3 — *Wardchar* (humoral medicine & purging, forest fire ecology, John Snow's cholera map; law: purge, mood: tense)

| | result |
|---|---|
| games released (all checks pass) | 3 / 3: Cordon, Expedition 3D, Trials (distinct families) |
| Cordon (held-out seeds) | skilled bot 100% / novice 0%; Python twin digest + day + alive match; do-nothing wins 0/12 |
| Expedition 3D (held-out) | skilled 71% / novice 12%; 3D view matches state |
| world search / history branching | 72 alternate histories explored |

**Honest note on Cordon (as shipped in cycle 3):** the tuner hit its parameter bounds and the skilled bot won every held-out game. That is exactly what the pass-3 gate and fixes address; the archived cycle-3 Cordon predates them.

## Pass 3 — reset, update, evolve: "waterballoon fights / volleyball world" (cycle 4)

**Reset:** cycle 3's universe was destroyed at its end; cycle 4 started from an empty `studio/state/` with only the knowledge store carried over.

**The studio evolved before building (each item measured and tested):**

| Weakness found in pass 2 | Change | Evidence |
|---|---|---|
| Difficulty judged only by *perfect* bots (Cordon: skilled 100%) | Added an **average-human tier** (inattentive ~25%) next to expert and novice; fitness and gate target expert 70–95%, average 35–65%, novice ≤10% | `tuner.fitness`, `tuner.in_target_band` + tests |
| Gate too lenient (skilled ≥ 0.3) | **Target-band gate** (expert ≥60%, average 30–75%, novice ≤20%, expert−novice ≥40%, side-bias ≤20%, sane rally length) + **performance budget** (<3 ms/sim step) | `verify.py` |
| Tuner saturated at its bounds and shipped anyway | Saturation is detected, bounds are **widened within hard caps and the game is retuned once**; widened bounds persist in knowledge | live in cycle 4: Volley's first tuning hit `restitution: lo`, missed the band (novice 21%), retune succeeded (novice 12%) |
| Cordon trivially won (perfect quarantine seal) | Fog of war (reports 2 days late), leaky quarantine, long-range outbreak jumps | grid: expert 0.82 / average 0.78 / novice 0 at the extreme |
| Palettes never checked | Contrast guarantee (text ≥7:1, accent ≥4.5:1, secondary ≥3:1) | 0 violations across 300 universes |
| No genre for ball sports / water fights | **Two new genres**: *Volley* (3D beach volleyball tournament) and *Splash* (top-down water-balloon fight), plus new laws *gust* and *slick*, a *bright* music mood, 9 new inspirations | below |
| Python twin only for integer sims | **Float physics twin**: Volley's core uses only + − × ÷ √ so Python reproduces Godot bit for bit | digest-exact incl. a seed > 2³¹ |

**Bugs found *by the new machinery* and fixed (kept as studio lessons in `studio/knowledge/`):**
1. The Python twin caught an **int64 overflow in GDScript for seeds > 2³¹** (`seed * 2654435761`); regression test pins the digest.
2. A "random" hash correlated across agent indices made **identical AIs lose 20/20** on one team (seat bias). 100-match symmetric runs after the fix: 47/53 and 50/44. Lesson: bias needs ≥100 matches, 20 is noise.
3. **Skill tiers were inverted**: leading the target *hurt* (lead 1.0 won 40%, lead 0 won 95%) because enemies stop to throw; perfect dodging produced 0 hits in 80 matches. Tiers are now validated for monotonic win rates by ablation (duels 15 / 53 / 97%).
4. A screenshot review after release found bumpers coloured like the enemy team and sand that read as grass; fixed and the archived games were re-verified (`python -m studio.patch`, recorded in the manifest as `patches`).

### Cycle 4 — *Ebbsoak* (tidal pools, water balloon fights, rally scoring; law: gust, mood: bright)

| game | genre family | held-out results (tuned) | verification |
|---|---|---|---|
| *Splash* | arena (new) | expert 0.91 / average 0.44 / novice 0.12; side-bias 0.03 | self-test, determinism across two process runs (digest `2e004fae`), perf 24 µs/step, screenshots |
| *Beach Volley* | 3D sport (new) | expert 0.96 / average 0.50 / novice 0.12; side-bias 0.12; rally 3.0 touches | Python twin digest/ticks/score match, perf 16 µs/step |
| *Steward* | simulation | do-nothing loses, bot wins | Python twin digest + score match |

All three released; cycle wall time ~18 min (Splash and Volley tuning dominate: ~8 min each). 60 tests pass (`python3 -m unittest discover -s tests`).

**Limits of pass 3 (honest):**
* Volley's rallies are short (about 3 touches) — playable but not rich; Splash's skill expression comes mostly from *aiming straight and dodging*, a narrower skill space than the genre could have. Both are tuned against *bots*; no human has played them (rating pipeline exists, zero ratings).
* The "average human" tier is a model (25% inattention), not data.
* 3D is still procedural primitives; the beach, palms and umbrellas are boxes/cylinders/prisms. Animation is transform/sine-driven.
* Genre selection still picks from a fixed pool of 7; the studio cannot yet invent a genre. This pass added two, by hand.
* Splash's team size defaulted to 2; the tuner saturated at `team_size: lo, ally_level: lo` (duels make skill matter most) and the bounds were widened for next time.

## Pass 4 — inspirations make the UNIVERSE; games are drawn from it (cycle 5)

Correction from the user: inspirations are not game briefs. "Water balloon fight + volleyball" is fused into one universe, and that universe is searched for
game ideas. What changed:

* `studio/elements.py`: every inspiration decomposes into **elements** (projectile_arc, burst, soak, net, rally, touch_limit, wind, ...). The universe is the union.
  Elements carry (a) a codex law, (b) **physics constants shared by every game** (gravity, wind, slick, burst radius, restitution) and (c) the game modules they unlock.
* Game families expose **modules** that only exist when the universe holds the needed elements: Volley `ball` (rubber / water balloon), `net` (solid / porous),
  `score` (rally / soak); Splash `barrier` (open / net), `ret` (bat balloons back), `win` (elimination / hold the fountain). A plague-only universe cannot produce them.
  Volley modules are implemented in both `volley_core.gd` and `volley_twin.py` (digest parity-tested incl. the new state); splash modules are bot-tier tested.
* `studio/ideas.py`: candidate enumeration -> headless bot simulation of every candidate (one batched Godot run per family) -> scores
  (`fun` = untuned tuner fitness, `depth` = skill gradient, `novelty` = distance to the knowledge `idea_archive`, `fit` = coverage of each inspiration's elements,
  `revolution` = novelty x fit x depth) -> three ideas from three different families. Families without per-idea simulation (concept, steward, arcade3d) get a flagged neutral prior (0.45).
  Output is archived as `ideas.json` (full ranking and rationale).
* Shared universe in all games: `Codex` button on every title screen (laws, physics, real-world facts, factions with traits, sibling games), rival factions whose lore trait
  shifts the AI (offsets applied on top of the tuned rival, so they are *not* inside the validated tier bands), identical physics constants fed to every tuner base.

### Cycle 5 — *Puddlespike* (water balloon fights + volleyball; law: gust, mood: bright) — verified
Universe elements: projectile_arc, burst, soak, refill, friendly_fire, team, net, rally, touch_limit, serve, bounce, wind. Shared physics: wind 0.03, gravity x1.0, burst radius x1.0.
Idea space: 19 candidates over 5 families (cordon not unlocked); 16 played by bots. Selected (full ranking in `archive/cycle_005/ideas.json`):

| game | family | idea | score / fun / depth / novelty / fit | tuned held-out (expert / average / novice) |
|---|---|---|---|---|
| Puddlespike: Splash | top-down arena | net across the arena + bat balloons back + hold the fountain | 0.87 / 0.93 / 0.80 / 1.0 / 0.75 | 0.81 / 0.44 / 0.03, side bias 0.10 |
| Puddlespike: Beach Volley | 3D sport | water balloon + porous net + soak scoring | 0.85 / 0.91 / 1.0 / 1.0 / 0.63 | 0.83 / 0.50 / 0.17, side bias 0.04, rally 3.3 |
| Puddlespike: Trials | strategy duel | rule sets discovered by the foundry, themed from the universe | 0.41 / 0.45* / 0.45* / 0.15 / 0.54 | not tuned (*unsimulated prior) |

All three pass the gate. The gate failed once on first verification (volley Python twin): `0.55 - 0.10` is `0.45000000000000007` in GDScript but prints as `0.45` in JSON,
so the replay used a different AI. Fixed (AI values rounded to 4 decimals), the archived game patched with `studio.patch` and the failure kept in the lessons.
Screenshot review found the splash net existed in the simulation but was not drawn; fixed and patched. Total cycle time 570 s.

### Honest limits of this pass
* "Most unique / fun / revolutionary" is a measured proxy over a *finite, hand-authored* module space; the studio recombines modules, it does not invent new mechanics.
* No human has playtested anything. Fun is not measured.
* Faction trait offsets are small and unvalidated by the tier gate.
* The third game (strategy duel) is the weakest idea: concept/steward/arcade3d have no per-idea bot simulation, so they score a neutral prior and only win a slot when nothing simulated remains.
* Volley average rally is short (3.3 hits) with soak scoring; it passes the gate (>=2.5) but is a candidate for the next pass.

## What was produced and verified (cycles 1–2, earlier pass)

| | Cycle 1 — *Clocktimber* (predator-prey cycles, circadian rhythms, Easter Island) | Cycle 2 — *Pallorbasalt* (coral bleaching, the telegraph, plate tectonics; prompt-driven) |
|---|---|---|
| law | pulse | wells |
| world search fitness | 0.686 → 0.712 (158 evals) | 0.695 → 0.718 |
| alternate histories explored | 72 | 72 |
| games released (all checks pass) | 3 / 3 | 3 / 3 |
| arcade held-out: skilled / novice bot full-clear | 0.88 / 0.04 | 0.71 / 0.04 |
| reset check | ok | ok |

Run `python3 -m unittest discover -s tests` (47 tests, includes a full smoke cycle and the Godot parity/UI tests; needs `GODOT_BIN`).
Open any archived game with `godot --path archive/cycle_001/games/steward`.

**The second cycle found and fixed a real bug** (stored priors used a section lookup that knew only 3 economy keys) in the
knowledge-reuse path that cycle 1 could not exercise; regression test added.

**Production-tool improvements that were preserved** (see `studio/knowledge/`): the first arcade attempt was refused by the gate
(`attempts/attempt_000_arcade_gate_failure.json`); root causes — a dithering skilled bot, a wells force ~100× too weak, and a
winner's-curse tuner — were fixed, and the lesson is stored in the knowledge file. After cycle 1 the studio also keeps evolved world-rule
priors and validated arcade parameters per law, and adapts search budgets from measured search behaviour.

## What this is NOT (read this)

* **Still not polished.** 3D and animation exist only as *procedural primitives and transforms* (capsules, boxes, spheres, emissive materials,
  sine-driven limbs, particles) — no authored/sculpted assets, no skeletal rigs, no authored animation clips. Audio is synthesized, not composed.
  Screens are functional and coherent, not beautiful. `agents.py` states each role's status.
* **"Complete game" here means a complete, small loop**: title, rules, progression, win/lose/ending, save, audio, verified by bots.
  Depth is days-of-content smaller than a commercial game; Game 1 has 3 trials, Game 2 ten epochs, Game 3 three stages.
* **Lore is templated.** Universe names/factions/chronicle come from word lists plus real facts; the chronicle's causal chains are
  real simulation output but shallow (cascades of 1–3 events). No writer or LLM authored story this cycle.
* **No human has played any of the games** (the rating pipeline exists but has received zero ratings). "Verified" means bots, twins and screenshots; fun and difficulty-for-humans are unmeasured.
  The arcade difficulty is tuned for the studio's bots. Game 2's target margin (1.35×) is a fixed design choice.
* **Verification bots are strong by construction** (Game 1's bot simulates the rival exactly, Game 2's follows a fixed script):
  they prove winnability, not balance.
* The studio now has **five genre templates in four families**; a cycle varies which three it ships, and the universe re-skins and re-tunes them.
  It cannot yet *invent* a new genre/engine on its own. 3D is a different *view* of an existing core (Expedition 3D shares the 2D game's logic).
* Only Linux/headless/xvfb + Godot 4.5 verified. No export builds, no CI.

## Next priorities

1. Collect real human ratings (pipeline exists) and use them in selection and tuning.
2. Authored-quality assets: mesh/texture generation beyond primitives, skeletal animation, composed audio — each as a role with acceptance tests.
3. More genre templates (narrative/roguelike/3D-native) and a template-discovery loop so the studio can invent genres, not only select among them.
4. LLM writers/designers through the inbox contract for lore and concept proposals, with the same measured gate.


## Standing principles (from the owner; apply to every future pass)
1. **Inspirations shape the world, not the games.** "Water balloon fights" may be how the universe's factions go to war, its economy, its religion, its physics; none of the three games has to
   look like a water balloon fight. Games are drawn from everything the universe makes possible (genre-free), chosen for being unique, fun and revolutionary, as three different genres.
2. **Do not read instructions literally unless told to.** Intent over wording.
3. **The owner's job is only: give inspirations and play the games.** Everything else (new genres, mechanics, tooling, tests, self-repair, retrospectives) is the studio's job, every cycle.
4. **The studio must compound.** Each cycle must leave the studio measurably more capable than before.

### Known gap against these principles (honest)
Cycle 5 still derived game *families* from inspiration elements (the volley and splash families only unlock when net/balloon elements exist), i.e. too literal. Planned next:
* Decouple: the universe yields *dynamics, factions, conflict, economy, geography*; a genre-free idea generator (verbs x goals x constraints) proposes ideas, the universe supplies theme, lore, physics and rules.
* Each cycle adds at least one new genre/module to the library (studio grows its own idea space), validated by bot simulation before it can be chosen.
* Self-evolution log: every retrospective names one capability to build next and the next cycle starts by building it.
