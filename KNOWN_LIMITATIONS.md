# Known limitations (honest status)

- **Nothing here has been executed in a real Godot editor.** The build environment cannot download Godot (GitHub/tuxfamily blocked). Only `gdparse` syntax checks ran (see TESTING.md). Treat as an untested first draft.
- **Claude Code cloud sessions cannot reach a phone's localhost.** This design works when Claude Code runs on the phone (Termux) against the same project folder, or on a PC on the same machine. The cloud/mobile-app case needs an outbound-connection relay plus a remote MCP endpoint; not built. Cloud sessions also work on a git clone, which conflicts with "no GitHub".
- Termux and Godot Android must share the project folder (shared storage + all-files access). Not verified.
- Godot may pause the editor when backgrounded on Android; the intended use (Godot foreground) is the safe case, but Claude Code in Termux needs a wake lock. Unverified.
- Editor-refresh calls (`update_file`, `reload_scene_from_path`, CodeEdit text swap) are written from API docs, unrun. Behaviour for open, unsaved scripts is untested.
- Log capture (`get_logs`) is a stub: Godot's `Logger` hook (4.5+) is not wired yet. No runtime/game screenshot; `screenshot` captures the editor viewport only.
- Heartbeat/reconnect: HTTP is stateless, so the MCP client reconnects per request; no long-lived socket exists to heartbeat.
- Scene tree edits bypass UndoRedo.
