# Deploying the relay (one time)

The relay is a ~100-line Node service. It stores nothing, forwards JSON-RPC between Claude Code and the
Godot plugin, and must run as **one always-on instance** (the plugin's WebSocket lives in its memory).

**Verified here:** `docker build`, running the image as non-root, `/healthz`, token auth, a headless Godot editor
connecting to the containerised relay and executing a tool call, `tools/make-connection.mjs`, `tools/connect.html`.
**Not run by the author (no Fly/Render account in the build sandbox):** the `fly` / Render dashboard steps below.

## 0. Generate the secret and connection file

Either run the script (on any computer with Node 18+; **choose an output path outside this repository**):

    node tools/make-connection.mjs --url https://YOUR-APP.fly.dev --out ~/claude-live-connection.json

or open `tools/connect.html` in a browser (works on the phone; fully client-side), enter the URL, tap Generate.
Both print the three things you need: the file for Godot, the relay secret, and the exact `claude mcp add` command.
You need the app name first, so pick it now (Fly: any unused name; Render: the service name).

## Fly.io

    cd relay
    fly auth login
    fly launch --no-deploy --copy-config --name YOUR-APP --region iad   # keeps relay/fly.toml; answer "no" to Postgres/Redis
    fly secrets set RELAY_TOKENS=<token printed in step 0>
    fly deploy --ha=false                                               # exactly one machine
    curl https://YOUR-APP.fly.dev/healthz                               # -> ok

`fly.toml` already sets `auto_stop_machines = "off"` and `min_machines_running = 1`. Do **not** scale above one machine.

## Render

1. New → **Blueprint** → pick this repository (it reads `relay/render.yaml`), or New → Web Service → Docker with *Root Directory* `relay`.
2. Instance type: **Starter or higher**. Free web services sleep after ~15 min idle and drop the WebSocket.
3. Environment → add `RELAY_TOKENS` = the token from step 0 (do not put it in git).
4. Open `https://YOUR-SERVICE.onrender.com/healthz` → `ok`.

## Any other Docker host

    docker build -t claude-live-relay relay
    docker run -d --restart=always -p 8080:8080 -e RELAY_TOKENS=<token> claude-live-relay

Put it behind TLS (the plugin refuses nothing, but the token must never travel over plain HTTP).
Behind a TLS-inspecting proxy, build with `--secret id=cabundle,src=/path/to/ca.pem` (optional, not stored in the image).

## Connect the two ends

1. **Claude Code** (where you type prompts): run the `claude mcp add --transport http godot https://YOUR-APP.fly.dev/mcp --header "Authorization: Bearer <token>"` line printed in step 0.
   The environment running Claude Code must be allowed to reach the relay host.
2. **Godot on the phone**: enable the *Claude Live* plugin, open its dock, tap **Load connection**, pick `claude-live-connection.json`.
   The dock should say *Connected*.
3. Prompt Claude Code, switch to Godot, watch the open project change.

## Rotating the secret

Generate a new one (step 0), `fly secrets set RELAY_TOKENS=<new>` (or edit the Render variable), `claude mcp remove godot` then
`claude mcp add …` again, and Load connection with the new file. The relay accepts a comma-separated list during a changeover.
