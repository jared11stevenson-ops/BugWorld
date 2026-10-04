# Protocol

## 1. Claude Code ⇄ relay (and ⇄ plugin directly)

MCP over HTTP, JSON responses only (no SSE), protocol version string `2025-03-26`.

    POST /mcp          Authorization: Bearer <token>      body: one JSON-RPC message
    GET  /healthz      (relay only, no auth)              → 200 "ok"

Methods implemented: `initialize`, `ping`, `tools/list`, `tools/call`. Notifications are accepted (202, no body).
Any other method returns JSON-RPC `-32601`. (Claude Code 2.1.x first probes `server/discover`; the `-32601` reply is
expected and it then falls back to `initialize`. Observed in `evidence/e2e/relay.log`.)
The local server accepts JSON-RPC batches; the relay rejects them (400). `GET /mcp` → 405.

Status codes: `401` bad/missing token, `403` request had an `Origin` header (browser), `404` other path, `405` non-POST,
`413` body > 8 MB, `429` (relay) too many failed auth attempts from one client IP (20 per 60 s).

JSON-RPC error codes from the relay: `-32000` plugin not connected, `-32001` plugin did not answer in 60 s,
`-32002` relay busy (64 requests in flight).

Tool results: `{content:[{type:"text"|"image",…}], isError?:true}`. Ids are echoed as integers when they were integers.

## 2. Relay ⇄ plugin

    WebSocket  wss://<relay>/plugin     Authorization: Bearer <token>   (handshake header)

Relay → plugin: the client's JSON-RPC message with `id` replaced by `r<n>` (notifications forwarded unchanged).
Plugin → relay: the JSON-RPC response with the same `r<n>`; the relay maps it back to the client's id.
`{"type":"hb"}` in either direction is a heartbeat (plugin sends every 15 s; relay echoes). The plugin closes a socket
silent for 45 s and reconnects. A second plugin connecting with the same token replaces the first (close code 4000).
The plugin remembers the last 128 answered ids and replays the stored response if the same id arrives again.

## 3. Tools

| Tool | Notes |
|---|---|
| `project_tree`, `read_file` | `read_file` returns `sha256` of the text. |
| `write_file` | `expected_sha` required for existing files; `allow_invalid` opts out of validation; `request_id` idempotency key. |
| `delete_file`, `rollback`, `list_transactions` | Snapshots: last 30, stored in `user://`. |
| `validate_script`, `scan_filesystem` | |
| `get_scene_tree`, `open_scene`, `save_scene`, `add_node`, `set_property`, `get_property`, `remove_node`, `move_node`, `connect_signal` | Operate on the scene open in the editor. |
| `run_project`, `stop_project` | |
| `screenshot` | `view`: `editor` (whole window, default), `2d`, `3d`. Needs a real display. |
| `get_logs` | `since` cursor, `limit`, `level` (`all`/`problems`), `source` (`all`/`editor`/`game`), `clear`. Needs Godot ≥ 4.5; says `unavailable` otherwise. |
| `game_status`, `game_tree`, `game_get_property`, `game_screenshot` | Inspect the **running** game (read-only). |
| `self_test`, `status` | |

Paths accept `res://…` or project-relative; anything resolving outside the project (`..`, absolute, drive letters,
`user://`, `.git`, `.godot`, or crossing a symlink) is rejected.

## 4. Plugin ⇄ running game (editor debugger channel)

Messages with prefix `claude_live:`. Game → editor: `hello`, `log`, `reply`. Editor → game: `cmd` with
`[id, op, args]`, `op ∈ {screenshot, tree, get, stats}`. The game never evaluates code from the editor.

## 5. Connection file

    {"url": "wss://<relay-host>", "token": "<≥32 chars>"}

Stored by the plugin in `user://claude_live_relay.json` (outside the project). `CLAUDE_LIVE_IMPORT=<path>` imports one at
editor start (same code as the dock button). `CLAUDE_LIVE_PORT` changes the local MCP port.
