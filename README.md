# Claude Live for Godot (Android-first)

Type a prompt in Claude Code, switch to Godot, watch the open project change. A pure-GDScript editor plugin
(`addons/claude_live`) exposes the project as an MCP server; a tiny relay (`relay/`) lets Claude Code reach a phone that
cannot accept inbound connections. See **ARCHITECTURE.md** for the picture, **TESTING.md** for what was actually run, and
**KNOWN_LIMITATIONS.md** for what was not.

Status: verified end to end on Linux with a real Godot 4.5 editor, the relay and a real Claude Code CLI session.
**Not yet run on an Android device** (see KNOWN_LIMITATIONS.md → "Needs your phone").

## One-time setup

1. **Deploy the relay** (Fly.io or Render, ~5 min): `DEPLOY.md`.
2. **Make the connection file** (open `tools/connect.html`, or `node tools/make-connection.mjs --url https://YOUR-APP.fly.dev`).
   It prints the relay secret, the file for Godot and the exact command for step 4.
3. **Godot (phone):** copy `addons/claude_live/` into your project, enable *Project → Project Settings → Plugins → Claude Live*
   (enabling also registers the `ClaudeLiveRuntime` autoload), open the **Claude Live** dock, tap **Load connection**, pick the file.
4. **Claude Code:** run the printed `claude mcp add --transport http godot https://YOUR-APP.fly.dev/mcp --header "Authorization: Bearer …"`.

Same-device alternative (no relay): Claude Code in Termux talks to `http://127.0.0.1:6590/mcp` with the token in
`user://claude_live_token` (path printed in the Output panel at startup).

## Daily use

Prompt Claude Code. Tools it can use: read/write/delete files (hash-checked, validated, snapshotted, rollback), scene edits,
run/stop, editor and game screenshots, game tree/property inspection, logs. Full list in `PROTOCOL.md`.
Ask Claude to run `self_test` once after setup.

## Requirements

Godot 4.4+ (engine log capture needs 4.5+; the full test suite passes on 4.4.1 and 4.5.0). Node 18+ only for the relay and tools.

## Repo map

`addons/claude_live/` plugin · `relay/` hosted relay (+ Dockerfile, fly.toml, render.yaml) · `tools/` connection generator ·
`tests/` automated tests (real Godot) · `evidence/e2e/` recorded end-to-end run · docs: ARCHITECTURE, PROTOCOL, SECURITY,
TESTING, KNOWN_LIMITATIONS, OPEN_SOURCE, DEPLOY.
