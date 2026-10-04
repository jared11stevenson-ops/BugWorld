# Testing

Everything below was run in the build sandbox (Ubuntu 24.04 x86-64, Node 22.22, Godot **4.5-stable official** and
**4.4.1-stable official** Linux binaries, Xvfb + Mesa llvmpipe software GL, Claude Code CLI 2.1.289). Nothing here ran on Android.

## Results (final code)

| Suite | Godot 4.5 | Godot 4.4.1 |
|---|---|---|
| `relay/test.js` (auth, routing, concurrency, drop, `/healthz`, throttle, in-flight cap) | PASS | n/a (no Godot) |
| `tests/plugin.test.js` (14 tests, headless editor) | 14/14 | 14/14 |
| `tests/relay.test.js` (5 tests, Godot client ⇄ real relay) | 5/5 | 5/5 |
| `tests/runtime.test.js` (6 tests, editor under Xvfb, real game) | 6/6 | 6/6 (game-log test asserts "unavailable") |
| **Total** | **25/25** | **25/25** |
| `tests/e2e/chain.mjs` (Godot → relay process → real `claude` CLI) | PASS, see below | not run |

Run: `cd tests && npm ci && GODOT_BIN=/path/to/godot node --test --test-concurrency=1 plugin.test.js relay.test.js runtime.test.js`
(`runtime.test.js` and the e2e script need `xvfb-run`; the headless suites do not). `cd relay && npm test` needs only Node.

## What each test proves

| Requirement | Test |
|---|---|
| `self_test` inside real Godot | `self_test passes inside real Godot` |
| Path traversal | `path traversal is blocked for every file tool…` — 12 hostile paths × 7 tools, and asserts nothing was created outside the project; plus a **symlink** variant |
| Stale-hash write rejection | `stale-hash write is rejected…` — file edited behind Claude's back; blind overwrite, missing `expected_sha` and phantom-file cases |
| Invalid GDScript rejection | `invalid GDScript / scene / JSON is rejected…` — 3 bad scripts, a bad `.tscn`, bad JSON; original file byte-identical afterwards |
| Rollback | `rollback restores update, create and delete…` and the live-editor variant below |
| Duplicate `request_id` replay | `duplicate request_id replays…` (tool level, write count unchanged, failures not cached) and `bridge-level duplicate delivery…` (same JSON-RPC id sent twice over the relay socket) |
| Godot client reconnects to relay | `reconnects after the relay restarts` (two outage cycles), plus `dials out…` and token-rejection cases |
| Dock *Load connection* logic | `importing a connection file…` (goes through `bridge.import_connection`, the function the dock button calls) |
| Live refresh | `a write to the OPEN scene shows up in the editor… rollback too` |
| Logger → `get_logs` | `get_logs: native Logger captures editor output and errors…`, `game stdout/warnings/errors are forwarded…` |
| Runtime inspection / game screenshot | `run_project -> game connects…`, `game_screenshot returns a real PNG…`, `edit main.tscn 1 -> 5 … re-run` |
| Editor screenshot | `editor screenshot (whole window and 2D viewport)…` |

## Bugs found by running it (all fixed, each now has a test)

1. `write_file` could write/read **outside the project through a symlink** inside it.
2. A failed call poisoned its `request_id`, so the retry replayed the old error.
3. `.tscn` validation only checked the header; broken scenes were accepted. Now loaded for real from a scratch copy.
4. Godot's `JSON.stringify` emits raw control characters (ANSI colour codes in logs, ESC in files) → invalid JSON for strict clients.
5. JSON-RPC ids came back as `1.0`.
6. The game probe stopped working after the first `run_project`: Godot reuses debugger sessions across runs.
7. `OS.add_logger` made the whole plugin fail to parse on Godot 4.4.
8. The editor `screenshot` tool returned a blank image (the 2D viewport does not render unless its tab is active).
9. `screenshot` crashed on a null texture when headless.
10. Relay needed a graceful `shutdown()` (upgraded sockets outlive `server.close()`).

## Measured numbers

| Measurement | Value |
|---|---|
| Plugin → relay connection after the MCP port is up | 9 ms (4.5), 19 ms (4.4.1) |
| Reconnect after relay returns (outage 3.5 s) | 3.6 s; second cycle (outage 1.5 s) 1.5 s. Backoff 1→2→4→8 s cap, so a long outage waits at most 8 s |
| `run_project` → game probe connected (software GL) | 1.3 s (4.5), 0.7 s (4.4.1) |
| Relay-measured tool latency (plugin processing + hop, local) | `read_file` 2–7 ms, `write_file` 13–21 ms, `run_project` 102 ms, `game_status` 228 ms, `game_screenshot` 116 ms |

## End-to-end chain (`tests/e2e/chain.mjs`, evidence in `evidence/e2e/`)

Setup, all real: relay as its own Node process (`RELAY_LOG=1`); connection file made by `tools/make-connection.mjs`; Godot 4.5 editor
(Xvfb) imported it via `CLAUDE_LIVE_IMPORT`; the exact printed `claude mcp add …` line was executed in a scratch `HOME`;
`claude mcp list` reported `godot … √ Connected`; Claude's built-in tools were disabled (`--tools ""`) so the only way to change
the project was the bridge. One Claude session, four separate prompts:

| Step | Claude tool calls | Wall time | Editor showed new value | Result |
|---|---|---|---|---|
| 1 → 2 | `read_file`, `write_file` (with `expected_sha`) | 8.7 s | 7.0 s after prompt | exactly 1 line changed (`1"`→`2"`) |
| 2 → 3 | same | 8.7 s | 7.0 s | 1 line |
| 3 → 4 | same | 8.3 s | 6.3 s | 1 line |
| 4 → 5 | same | 8.2 s | 6.2 s | 1 line; file sha256 `15d15d1d…` identical to a hand-edited 5 |
| bonus | `run_project`, `game_status`, `game_screenshot` | – | – | Claude reported the running game shows **5** |

Observed independently of Claude after every step: bytes on disk, the label text inside the open editor scene (`get_property`
on the local port), and an editor-viewport screenshot (`editor-after-step-N.png`; `editor-window-final.png` shows the whole editor
with `Main > Label` and "CODEX LIVE TEST 5"). Most of the 6–7 s is model latency; the relay hop is milliseconds.
The harness asserts its random token appears in no saved evidence file (it did not). The chain was run three times (the table is the last run);
per-step wall time was 5.8–6.8 s, 7.4–8.1 s and 8.2–8.7 s across runs, so expect a few seconds of variance.

## Not tested (needs a phone or an account)

Android install/permissions, the SAF file picker behind *Load connection*, the dock UI itself (only its import function is
tested), `wss://` to a real TLS host, an actual Fly.io/Render deployment (the Docker image was built and run locally),
Godot backgrounded on Android, script-editor text swap for an open unsaved `.gd` (no script editor in headless),
multiple simultaneous Claude clients, outages longer than a few seconds, Termux same-device mode.
