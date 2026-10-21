# HOLLOWMERE

*The hour that never ends.* A third-person dark-fantasy action-adventure for the browser (WebGL2, three.js).

Every clock in the House of Hollowmere stopped at the same minute. You are the last Warden: carry a lantern through a fog-bound estate,
recover the three Hands of the Master Clock, and end the hour.

## Play
    cd game && python3 -m http.server 8000     # any static server; open http://localhost:8000
Add `?q=low` for a no-shadow / no-bloom mode on weak GPUs.

| Key | Action |
|---|---|
| WASD / mouse | move / camera (click to capture mouse) |
| Shift | run (stamina) |
| Space | roll (i-frames; dodges the clock's shockwave) |
| Left click | sword strike (aim-assist) |
| E | interact: light candles (checkpoint + heal), open chests |
| Esc | pause |

## Contents
- ~190 m dead-forest estate: courtyard, three guarded zones, checkpoints, fog, fireflies, PBR + HDRI lighting, bloom / grade / grain.
- Two enemy types (statues that wake, busts that dive), a boss (the Master Clock: tolling shockwaves + summons), death/respawn, ending.
- Fully synthesised adaptive audio.

Layout: `index.html` UI · `src/main.js` game · `src/audio.js` sound · `assets/` CC0 models/textures/HDRI · `vendor/three` · `tools/` fetch + optimizer · `CREDITS.md`.

## Honest status
A playable vertical slice, not a finished AAA title: one map, two enemy types, one boss, a code-posed hero (no skeletal animation),
no save game, gamepad or touch. Verified headlessly on software GL (load, combat, boss, ending, no console errors); not tuned on a real GPU.
