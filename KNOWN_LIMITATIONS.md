# Known limitations (measured status)

## Needs your phone (I could not do these)

1. **Install on Android Godot 4.4+/4.5+ and enable the plugin.** Expect to confirm: the plugin loads, the Output panel shows
   `[claude_live] MCP ready…`, and the dock appears. Run `self_test` once.
2. **Tap *Load connection* and pick the downloaded file** (Android system picker). Only the function behind the button is tested.
   The dock should switch to "Connected".
3. **Check the game launch on-device:** `run_project` then `game_status`. On the desktop the game process connects to the
   editor debugger over localhost; Android's editor runs the game in a separate process and this was not verified there.
4. **Background behaviour:** switch Claude Code ↔ Godot while a prompt runs. Android may pause or kill Godot when it is
   not in the foreground; the relay then answers "plugin is not connected" or times out after 60 s. Reconnect logic is tested
   on Linux only (≤ 8 s backoff), not the phone's sleep/wake or network handover.
5. **Delete the connection file** from shared storage after loading it (it holds the secret).

## Needs your accounts

* Actual Fly.io / Render deployment and a `wss://` handshake against a real certificate (`DEPLOY.md` steps were not run by me;
  the image was built and run with Docker locally, including a Godot editor connecting to it).
* A LICENSE (OPEN_SOURCE.md).

## Behaviour limits found while testing

* **Godot 4.4 has no `Logger`:** `get_logs` says `unavailable` and game stdout/errors are not captured. 4.5+ captures editor and
  game output (verified on 4.5.0).
* **Screenshots need a real display.** Headless returns a clear error. `game_screenshot` works only if the game itself has a renderer.
* **A running game does not hot-reload.** Edits are visible in the editor immediately (verified); the game shows them after
  `stop_project` + `run_project` (verified, takes ~1.3 s to reconnect). Live game patching is not implemented.
* **Open scene with unsaved edits:** writing the same `.tscn` reloads it from disk (`reload_scene_from_path`) and discards
  unsaved in-editor changes. Not tested; Godot may prompt.
* **Open `.gd` in the script editor:** the text swap path is written from the API docs; untested (headless has no script editor).
  Scripts on disk and the loaded `GDScript` cache are refreshed.
* **Scene-tree tools** (`add_node`, `set_property`, `remove_node`, …) bypass UndoRedo; only `set_property`/`get_property`/`open_scene`/
  `get_scene_tree` were exercised by tests.
* **Single relay instance only**; relay state is in memory. Two Claude clients with the same token share one plugin socket.
* **Latency is dominated by the model**, not the bridge (~6–7 s per step measured, relay hop in milliseconds).
* `.tscn/.tres` validation is "does Godot load it", which does not catch every semantic mistake (e.g. wrong property names
  load with a warning).
* The runtime autoload is registered in `project.godot` by enabling the plugin; remove the addon from release exports.
* Claude Code 2.1.x sends an unsupported `server/discover` first; the `-32601` reply is harmless.
* No Godot 4.6+ testing; versions other than 4.4.1 and 4.5.0 are unverified.
