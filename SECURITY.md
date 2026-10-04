# Security

## What the token means

Whoever holds the token can read and write every file in the open project **and run it** (`write_file` + `run_project`).
Treat it like a password to the project, and in practice to the Godot app's sandbox on the phone. There is no per-tool
permission model; Claude Code's own tool-approval prompts are the only gate.

## Defences that exist (and the test that proves each)

| Property | Where | Test (see TESTING.md) |
|---|---|---|
| Every path confined to the project; `..`, absolute, `C:`, `user://`, `.git`, `.godot` rejected for all file tools | `tools.gd: safe_path` | `path traversal is blocked for every file tool…` |
| Symlinks inside the project cannot be used to escape (found and fixed by testing) | `safe_path` | `…via a symlink inside the project is blocked` |
| Stale/blind writes refused (hash compare-and-swap) | `t_write_file` | `stale-hash write is rejected…` |
| Invalid GDScript/scene/JSON never reaches disk | `validate_text` | `invalid GDScript / scene / JSON is rejected…` |
| Local server: loopback only, bearer token, rejects any `Origin` (browser/DNS-rebinding), 8 MB cap | `mcp_server.gd` | `HTTP auth and hardening` |
| Relay: token on both sides (constant-time compare), no project data stored, per-IP failed-auth throttle, in-flight cap, 8 MB / 16 MB size caps | `relay.js` | `relay/test.js`, `relay.test.js` |
| Secrets stay out of the project: token and connection config live in `user://`; generator refuses to write inside a git work tree | `bridge_client.gd`, `make-connection.mjs` | `importing a connection file…` (asserts not in project), `a relay that rejects the token…` (asserts token not in Godot's log) |
| Relay log is opt-in and records only method/tool name, duration, outcome | `relay.js` | `evidence/e2e/relay.log` |
| Game probe is read-only and ignores unknown ops | `runtime.gd` | `runtime.test.js` |

## Known weaknesses (not fixed)

* **The relay operator sees all traffic** (plain JSON inside TLS). Self-host it; do not use a relay you do not control.
* **Token at rest is plaintext**: `user://claude_live_token` and `user://claude_live_relay.json` (app-private on Android,
  but not encrypted), and the downloaded connection file in shared storage until you delete it. Delete it after loading.
* The local server compares its token with `!=` (not constant-time). It is loopback-only; the relay uses a constant-time compare.
* `allow_invalid=true` bypasses validation by design.
* Anything Claude reads (project files, logs) may contain prompt-injection text. The write tools will act on whatever
  Claude decides; review diffs, and use `rollback`.
* The runtime autoload ships with the addon folder. Exclude `addons/claude_live` from release exports; it is inert
  without the editor debugger, but there is no reason to ship it.
* Relay throttling keys on `Fly-Client-IP` / `X-Forwarded-For`, which a direct client can spoof; token strength (256 bit), not
  the throttle, is the real protection.
* No audit trail beyond `list_transactions` (last 30 snapshots).

## Reporting

Open an issue without including a token. If a token was ever pasted anywhere, rotate it (DEPLOY.md, "Rotating the secret").
