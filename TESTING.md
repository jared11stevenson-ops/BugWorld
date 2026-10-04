# Testing

| Check | Result |
|---|---|
| `gdparse` on addons/claude_live/*.gd | run in build env (see commit); syntax only |
| relay/test.js (auth, routing, concurrency, drop handling) | PASS (Node, local) |
| Execution in Godot 4.x editor | NOT RUN |
| Android device | NOT RUN |
| Claude Code <-> plugin MCP handshake | NOT RUN |
| Acceptance test (1->5 live) | NOT RUN |

First on-device step: enable the plugin, call `self_test` and report its JSON.
