# Claude Live for Godot (Android-first)

Pure-GDScript Godot editor plugin that hosts an MCP server (Streamable HTTP, loopback only) **inside the editor**.
Claude Code connects to it directly, so edits land in the *same* open project, live. No Node, no relay, no git.

## Setup (once)
1. Copy `addons/claude_live/` into your project (or open this repo as the test project). Project > Project Settings > Plugins > enable **Claude Live**.
2. Token is auto-generated in Godot's user dir (`claude_live_token`; path printed in the Output panel).
3. In Claude Code **running on the same phone** (Termux): `claude mcp add --transport http godot http://127.0.0.1:6590/mcp --header "Authorization: Bearer $(cat <token file>)"`.
4. Ask Claude to run the `self_test` tool.

## Daily use
Prompt Claude Code, switch to Godot, watch. See KNOWN_LIMITATIONS.md and TESTING.md for what is and is not verified.
