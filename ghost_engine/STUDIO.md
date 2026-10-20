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
| 3 | Game 1 — *Trials* (strategy duel campaign) | `ghost.foundry` discovery loop, tilted by the universe's dynamics; 3 discovered concepts themed with universe vocabulary; escalating rivals | Godot project |
| 4 | Game 2 — *Steward* (world-sim) | the persistent world kernel with the evolved rules; influence points, previews on forked timelines, limited rewinds, drawn map; target = do-nothing timeline × 1.35 | Godot project |
| 5 | Game 3 — *Expedition* (real-time arcade) | deterministic GDScript core with the universe's law; **difficulty evolved by headless Godot simulation** of a skilled and a novice bot, re-evaluated on fresh seeds each generation and validated on held-out seeds | Godot project |
| 6 | Verification gate | `studio/verify.py`: per game — self-test through the game's real code paths, no script errors, assets present, non-blank screenshots, Python twin of the simulation (campaign sessions replayed, steward digest+score replayed, arcade held-out skill/novice gap) | pass/fail per check |
| 7 | Archive | `archive/cycle_NNN/{games/*, evidence, universe.json, CHRONICLE.md, manifest.json}`; only games passing every check are listed as released | permanent record |
| 8 | Retrospective + RESET | `studio/retro.py` stores universe-independent lessons/priors/budget changes; `reset_state()` deletes the temporary universe state and asserts nothing universe-specific leaked into knowledge | `studio/knowledge/knowledge.json` |

Agent roles and their honest status are in `studio/agents.py` (programmatic stages with acceptance checks; LLM agents plug in through the foundry inbox).

## What was produced and verified

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

* **Not polished, not 3D, not animated.** All art is procedural 2D vector drawing (palette, emblem, map, shapes). There is no 3D asset
  pipeline and no animation pipeline (`art_3d`, `animation` are declared MISSING in `agents.py`). Audio is synthesized blips and a
  generated arpeggio loop, not composed music. Screens are functional, not beautiful.
* **"Complete game" here means a complete, small loop**: title, rules, progression, win/lose/ending, save, audio, verified by bots.
  Depth is days-of-content smaller than a commercial game; Game 1 has 3 trials, Game 2 ten epochs, Game 3 three stages.
* **Lore is templated.** Universe names/factions/chronicle come from word lists plus real facts; the chronicle's causal chains are
  real simulation output but shallow (cascades of 1–3 events). No writer or LLM authored story this cycle.
* **No human has played any of the games.** "Verified" means bots, twins and screenshots; fun and difficulty-for-humans are unmeasured.
  The arcade difficulty is tuned for the studio's bots. Game 2's target margin (1.35×) is a fixed design choice.
* **Verification bots are strong by construction** (Game 1's bot simulates the rival exactly, Game 2's follows a fixed script):
  they prove winnability, not balance.
* The three genres are the three **templates** the studio can build today; "unlimited succession" of *different* genre sets is not yet
  possible — new universes re-skin and re-tune these templates (new rules, laws, themes, discovered concepts) rather than invent new
  game engines.
* Only Linux/headless/xvfb + Godot 4.5 verified. No export builds, no CI.

## Next priorities

1. Human playtest loop (rating hooks exist in the foundry arena; add to all three games) and feed ratings into the retrospective.
2. Asset pipelines: 3D (procedural meshes first), animation (tweens/skeletal), richer composed audio — each as a role with acceptance tests.
3. More genre templates (and a template-discovery loop) so a cycle's three games can differ in kind, not only in rules and theme.
4. LLM writers/designers through the inbox contract for lore and concept proposals, with the same measured gate.
