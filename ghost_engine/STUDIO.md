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
| 3 | Genre pool selection (`studio/pool.py`): 5 genres in 4 families, scored by the universe's dynamics + novelty bonus for genres not shipped in the last two cycles; one game per family | three genres |
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

**Honest note on Cordon:** the tuner hit its parameter bounds and the skilled bot still wins every held-out game — it is hard for naive play, easy for a competent player; real difficulty for humans is unknown.

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
