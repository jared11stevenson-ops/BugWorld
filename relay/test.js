import assert from "node:assert";
import WebSocket from "ws";
import { createRelay } from "./relay.js";
const T = "a".repeat(40);
const srv = createRelay({ tokens: new Set([T]) });
await new Promise((r) => srv.listen(0, r));
const port = srv.address().port;
const post = (body, tok = T) => fetch(`http://127.0.0.1:${port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${tok}`, "content-type": "application/json" }, body: JSON.stringify(body) });

assert.equal((await post({ jsonrpc: "2.0", id: 1, method: "ping" }, "bad")).status, 401);
let r = await (await post({ jsonrpc: "2.0", id: 1, method: "ping" })).json();
assert.match(r.error.message, /not connected/);

const ws = new WebSocket(`ws://127.0.0.1:${port}/plugin`, { headers: { authorization: `Bearer ${T}` } });
await new Promise((r) => ws.on("open", r));
ws.on("message", (d) => { const m = JSON.parse(d); if (m.method) ws.send(JSON.stringify({ jsonrpc: "2.0", id: m.id, result: { echo: m.method } })); });
r = await (await post({ jsonrpc: "2.0", id: 7, method: "tools/list" })).json();
assert.deepEqual(r, { jsonrpc: "2.0", id: 7, result: { echo: "tools/list" } });
assert.equal((await post({ jsonrpc: "2.0", method: "notifications/initialized" })).status, 202);
const rs = await Promise.all([1, 2, 3, 4, 5].map((i) => post({ jsonrpc: "2.0", id: 100 + i, method: "m" + i }).then((x) => x.json())));
rs.forEach((x, i) => assert.equal(x.id, 101 + i) || assert.equal(x.result.echo, "m" + (i + 1)));
// unauthorized websocket
await new Promise((res) => { const bad = new WebSocket(`ws://127.0.0.1:${port}/plugin`, { headers: { authorization: "Bearer nope" } }); bad.on("error", res); bad.on("unexpected-response", res); });
// plugin drop => clear error
ws.close(); await new Promise((r) => setTimeout(r, 100));
r = await (await post({ jsonrpc: "2.0", id: 9, method: "ping" })).json();
assert.match(r.error.message, /not connected/);
// health endpoint (no auth, used by Fly/Render)
assert.equal((await fetch(`http://127.0.0.1:${port}/healthz`)).status, 200);
// brute-force throttle: repeated bad tokens from one client get 429, a good token from it is then also throttled for the window
const srv2 = createRelay({ tokens: new Set([T]) });
await new Promise((r) => srv2.listen(0, r));
const p2 = srv2.address().port;
const bad2 = () => fetch(`http://127.0.0.1:${p2}/mcp`, { method: "POST", headers: { authorization: "Bearer " + "q".repeat(40) }, body: "{}" });
const codes = []; for (let i = 0; i < 25; i++) codes.push((await bad2()).status);
assert.equal(codes[0], 401); assert.equal(codes[24], 429);
await srv2.shutdown();
// in-flight cap: 64 stalled requests fill the relay, the 65th gets a clear busy error
const srv3 = createRelay({ tokens: new Set([T]) });
await new Promise((r) => srv3.listen(0, r));
const p3 = srv3.address().port;
const ws3 = new WebSocket(`ws://127.0.0.1:${p3}/plugin`, { headers: { authorization: `Bearer ${T}` } });
await new Promise((r) => ws3.on("open", r)); // plugin never answers
const stalled = []; for (let i = 0; i < 64; i++) stalled.push(fetch(`http://127.0.0.1:${p3}/mcp`, { method: "POST", headers: { authorization: `Bearer ${T}` }, body: JSON.stringify({ jsonrpc: "2.0", id: i + 1, method: "x" }) }).catch(() => {}));
await new Promise((r) => setTimeout(r, 300));
const over = await (await fetch(`http://127.0.0.1:${p3}/mcp`, { method: "POST", headers: { authorization: `Bearer ${T}` }, body: JSON.stringify({ jsonrpc: "2.0", id: 999, method: "x" }) })).json();
assert.match(over.error.message, /busy/);
await srv3.shutdown();
console.log("relay tests passed");
srv.close(); process.exit(0);
