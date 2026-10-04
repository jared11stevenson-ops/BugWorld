# Architecture

Goal: type a prompt in Claude Code, switch to Godot (Android), and watch the open project change. No git, zip,
copy/paste or manual refresh in daily use.

```
  Claude Code (anywhere)                relay (hosted, 1 instance)              Godot editor (phone)
  ─────────────────────                 ────────────────────────                ─────────────────────
  claude mcp add --transport http  ──►  POST /mcp  (Bearer token)
        MCP over HTTPS                    │  rewrites JSON-RPC id → r<n>
                                          ▼
                                       WebSocket /plugin  ◄── dials OUT ──────  plugin: bridge_client.gd
                                          │  one socket per token                  │ (reconnect + heartbeat)
                                          └────── request ───────────────────────► mcp_server.handle_message
                                          ◄───── response ──────────────────────── tools.gd  (read/write/scene/run…)
                                                                                    │ file write → editor refresh
                                                                                    ▼
                                                                          open scene / script reloads live
```

The phone never listens on a public port: the plugin dials **out** to the relay. The same plugin also serves MCP on
`127.0.0.1:6590` for Claude Code running on the same device (Termux) with no relay at all.

## Components

| Path | Role |
|---|---|
| `addons/claude_live/plugin.gd` | EditorPlugin: starts the local MCP server, the relay client, the dock, the log capture, the debugger plugin; registers the runtime autoload on enable. |
| `mcp_server.gd` | Minimal MCP (Streamable HTTP, JSON responses) on loopback; `handle_message` is shared with the relay client. Awaitable, so tools can wait for the running game. |
| `tools.gd` | The tools: path-confined file ops with compare-and-swap hashes, validation, snapshots/rollback, scene edits, run/stop, screenshots, logs, `game_*` inspection, `self_test`. |
| `bridge_client.gd` | Outbound WebSocket to the relay: bounded backoff (1→8 s), 15 s heartbeat, dead-peer detection, replay of duplicate request ids. `import_connection()` backs the dock's *Load connection*. |
| `dock.gd` | "Claude Live" dock: status text and the *Load connection* button (system file picker). |
| `runtime.gd` (autoload) | Runs inside the game process only when launched from the editor; read-only probe (screenshot, tree, property read, stats, log forwarding). |
| `debugger.gd` | Editor side of that probe (EditorDebuggerPlugin). |
| `compat.gd`, `log_capture.gd.txt` | Godot ≥ 4.5 `Logger` capture, compiled at runtime only when the class exists, so 4.4 still loads the plugin. |
| `json_util.gd` | Escapes control characters that Godot's `JSON.stringify` leaves raw (strict clients reject them). |
| `relay/relay.js` | ~110 lines of Node + `ws`. Forwards JSON-RPC, stores nothing, `/healthz`, auth throttle, in-flight cap. |
| `tools/make-connection.mjs`, `tools/connect.html` | Generate the secret, the connection file and the exact `claude mcp add` command. |

## A write, end to end

1. Claude calls `read_file res://main.tscn` → gets content + `sha256`.
2. Claude calls `write_file` with new content and `expected_sha`.
3. Plugin: confines the path → compares the hash (else `CONFLICT`) → validates (`.gd` is compiled, `.tscn/.tres` are actually loaded from a scratch copy, `.json` is parsed) → snapshots → atomic temp-file rename → reads back and verifies → refreshes the editor (`update_file`, `scan`, `reload_scene_from_path` for an open scene, script editor text swap for an open script).
4. The response carries a `txn` id; `rollback(txn)` restores the previous bytes.

## Why these choices

* **Outbound WebSocket:** phones sit behind NAT; nothing needs port-forwarding. Same design as the earlier Codex bridge.
* **Relay is dumb:** one token pairs both sides; it holds one in-memory socket, so it must run as exactly one instance.
* **Hash-checked writes:** the user can edit on the device while Claude works; a stale write is refused, never merged silently.
* **Idempotency at two levels:** `request_id` on tools (successes only are replayed) and relay-id replay in the bridge.

## Measured behaviour (details in TESTING.md)

Claude prompt → change visible in the open editor: 6.2–7.0 s in the recorded run, almost all of it model time. Relay-side
latency for `read_file`/`write_file`: 2–21 ms locally. Reconnect after a relay restart: 1.5–3.6 s. Game probe connects 0.7–1.3 s
after `run_project`. Not measured on a phone or across the public internet.
