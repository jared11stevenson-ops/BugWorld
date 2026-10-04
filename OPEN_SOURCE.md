# Open-source status

## License: not chosen yet (needs your decision)

There is **no LICENSE file** in this repository, so by default nobody else may legally reuse it. Pick one before publishing.
MIT or Apache-2.0 would match Godot (MIT) and the only runtime dependency (`ws`, MIT).

## Third-party code

| Component | License | How used |
|---|---|---|
| Godot Engine 4.4 / 4.5 | MIT | Runtime for the plugin and the tests; binaries are downloaded by the tester, not vendored. |
| `ws` (npm) | MIT (checked: `relay/node_modules/ws/package.json`) | Relay and test WebSocket library. |
| Node.js, Docker base image `node:22-alpine` | MIT / mixed OSS | Runtime/base image of the relay. |

No third-party source is copied into this repo; `package-lock.json` files pin the npm dependencies.

## Release checklist (what was checked, what was not)

* Secrets scan of the working tree (64-hex, `Bearer …`, `sk-`, `ghp_`, private-key headers): the only matches are SHA-256
  content hashes in `evidence/e2e/summary.json`. The e2e harness additionally asserts that its randomly generated token does
  not appear in any saved evidence file. **Checked by the author's run, not by an independent scanner.**
* `.gitignore` excludes `node_modules`, `.godot/`, `tests/artifacts/` and any `*connection*.json`.
* Not done: a license, a code-of-conduct, contribution guide, a Godot Asset Library listing, version tags, CI.
* Suggested CI: `cd relay && npm ci && npm test` (no Godot needed); the Godot suites need a Godot binary and, for the runtime
  suite, `xvfb-run` (see TESTING.md).
