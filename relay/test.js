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
console.log("relay tests passed");
srv.close(); process.exit(0);
