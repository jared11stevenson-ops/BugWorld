import test from "node:test";
import assert from "node:assert/strict";
import { WebSocketServer } from "ws";
import http from "node:http";
import { createRelay } from "../relay/relay.js";
import { startGodot, freePort, sleep, sha256 } from "./lib.js";

const TOKEN = "t".repeat(48);
const listen = (srv, port) => new Promise((r) => srv.listen(port, "127.0.0.1", r));
const closeAll = (srv) => srv.shutdown();
const post = (port, body, token = TOKEN) => fetch(`http://127.0.0.1:${port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${token}`, "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
const callTool = async (port, name, args = {}, id = Math.floor(Math.random() * 1e6)) => {
  const j = await post(port, { jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } });
  if (j.error) throw new Error(j.error.message);
  const text = j.result.content[0].text; let json; try { json = JSON.parse(text); } catch {}
  return { isError: !!j.result.isError, text, json };
};
async function until(fn, ms, label) { const t0 = Date.now(); for (;;) { try { const v = await fn(); if (v) return Date.now() - t0; } catch {} if (Date.now() - t0 > ms) throw new Error("timeout: " + label); await sleep(100); } }

test("Godot client dials out to the relay; Claude-side MCP calls reach the editor through it", async () => {
  const rport = await freePort();
  const relay = createRelay({ tokens: new Set([TOKEN]) });
  await listen(relay, rport);
  const g = await startGodot({ relayCfg: { url: `ws://127.0.0.1:${rport}`, token: TOKEN } });
  try {
    const t = await until(async () => !(await post(rport, { jsonrpc: "2.0", id: 1, method: "ping" })).error, 20000, "plugin connects to relay");
    console.log(`# measured: relay connection established ${t} ms after the MCP port was ready`);
    const init = await post(rport, { jsonrpc: "2.0", id: 2, method: "initialize", params: {} });
    assert.equal(init.result.serverInfo.name, "claude-live-godot");
    assert.equal(init.id, 2);
    const st = await callTool(rport, "status");
    assert.equal(st.json.relay, "connected");
    const w = await callTool(rport, "write_file", { path: "res://via_relay.txt", content: "hello" });
    assert.equal(w.isError, false, w.text);
    assert.equal(g.read("via_relay.txt"), "hello");
    // wrong token never reaches the editor
    const bad = await fetch(`http://127.0.0.1:${rport}/mcp`, { method: "POST", headers: { authorization: "Bearer " + "x".repeat(48) }, body: "{}" });
    assert.equal(bad.status, 401);
    // concurrent calls through the relay keep ids straight
    const rs = await Promise.all([1, 2, 3, 4, 5, 6].map((i) => callTool(rport, "write_file", { path: `res://c${i}.txt`, content: "c" + i }, 900 + i)));
    rs.forEach((r, i) => { assert.equal(r.isError, false); assert.equal(g.read(`c${i + 1}.txt`), "c" + (i + 1)); });
  } finally { await g.stop(); await closeAll(relay); }
});

test("Godot client reconnects after the relay restarts (and during an outage keeps retrying)", async () => {
  const rport = await freePort();
  let relay = createRelay({ tokens: new Set([TOKEN]) });
  await listen(relay, rport);
  const g = await startGodot({ relayCfg: { url: `ws://127.0.0.1:${rport}`, token: TOKEN } });
  try {
    await until(async () => !(await post(rport, { jsonrpc: "2.0", id: 1, method: "ping" })).error, 20000, "initial connect");
    await closeAll(relay); // relay goes away (deploy / crash / network)
    const down = Date.now();
    await sleep(3500); // client must survive an outage with its backoff running
    relay = createRelay({ tokens: new Set([TOKEN]) });
    await listen(relay, rport);
    const ms = await until(async () => !(await post(rport, { jsonrpc: "2.0", id: 1, method: "ping" })).error, 40000, "reconnect after relay restart");
    console.log(`# measured: reconnected ${ms} ms after the relay came back (outage ${Date.now() - down - ms} ms)`);
    const w = await callTool(rport, "write_file", { path: "res://after_reconnect.txt", content: "ok" });
    assert.equal(w.isError, false, w.text);
    assert.equal(g.read("after_reconnect.txt"), "ok");
    // a second outage cycle, to be sure state resets cleanly
    await closeAll(relay);
    await sleep(1500);
    relay = createRelay({ tokens: new Set([TOKEN]) });
    await listen(relay, rport);
    const ms2 = await until(async () => !(await post(rport, { jsonrpc: "2.0", id: 1, method: "ping" })).error, 40000, "second reconnect");
    console.log(`# measured: second reconnect ${ms2} ms`);
  } finally { await g.stop(); await closeAll(relay); }
});

test("importing a connection file (what the dock's Load connection does) makes the editor dial out; bad files are refused", async () => {
  const fs = await import("node:fs");
  const rport = await freePort();
  const relay = createRelay({ tokens: new Set([TOKEN]) });
  await listen(relay, rport);
  const root = fs.mkdtempSync("/tmp/cl-conn-");
  const conn = `${root}/conn.json`;
  fs.writeFileSync(conn, JSON.stringify({ url: `ws://127.0.0.1:${rport}`, token: TOKEN }));
  const g = await startGodot({ env: { CLAUDE_LIVE_IMPORT: conn } });
  try {
    await until(async () => !(await post(rport, { jsonrpc: "2.0", id: 1, method: "ping" })).error, 20000, "connect after import");
    const stored = JSON.parse(fs.readFileSync(`${g.userDir}/claude_live_relay.json`, "utf8"));
    assert.equal(stored.token, TOKEN); // stored under the user dir, outside the project
    assert.equal(g.exists("claude_live_relay.json"), false);
    assert.doesNotMatch(JSON.stringify(await g.tool("project_tree", { dir: "res://", depth: 3 })), /claude_live_relay/);
  } finally { await g.stop(); }
  const bad = `${root}/bad.json`;
  fs.writeFileSync(bad, JSON.stringify({ url: "ws://x", token: "short" }));
  const g2 = await startGodot({ env: { CLAUDE_LIVE_IMPORT: bad } });
  try {
    assert.equal((await g2.tool("status")).json.relay, "disabled");
    assert.match(g2.log, /not a valid connection/);
  } finally { await g2.stop(); await closeAll(relay); fs.rmSync(root, { recursive: true, force: true }); }
});

test("bridge-level duplicate delivery of the same JSON-RPC id is replayed, not re-executed", async () => {
  // A mock relay that deliberately sends the same request twice (as a flaky network / retrying relay could).
  const rport = await freePort();
  const wss = new WebSocketServer({ port: rport, host: "127.0.0.1" });
  const sock = new Promise((res) => wss.on("connection", (ws, req) => { assert.equal(req.headers.authorization, "Bearer " + TOKEN); res(ws); }));
  const g = await startGodot({ relayCfg: { url: `ws://127.0.0.1:${rport}`, token: TOKEN } });
  try {
    const ws = await sock;
    const replies = [];
    ws.on("message", (d) => { const m = JSON.parse(d); if (m.id !== undefined) replies.push(m); });
    const req = { jsonrpc: "2.0", id: "dup-1", method: "tools/call", params: { name: "write_file", arguments: { path: "res://bridge_dup.txt", content: "once" } } };
    ws.send(JSON.stringify(req));
    await until(() => replies.length >= 1, 10000, "first reply");
    fs_write(g, "bridge_dup.txt", "changed-meanwhile"); // if the second delivery re-executed it would clobber/err
    ws.send(JSON.stringify(req));
    await until(() => replies.length >= 2, 10000, "replayed reply");
    assert.equal(JSON.stringify(replies[1]), JSON.stringify(replies[0]));
    assert.equal(g.read("bridge_dup.txt"), "changed-meanwhile");
    const st = JSON.stringify({ jsonrpc: "2.0", id: "s1", method: "tools/call", params: { name: "status", arguments: {} } });
    ws.send(st); await until(() => replies.length >= 3, 10000, "status");
    assert.equal(JSON.parse(JSON.parse(replies[2].result.content[0].text) && replies[2].result.content[0].text).stats.writes, 1);
    // heartbeat is answered without an id
    ws.send('{"type":"hb"}');
  } finally { await g.stop(); wss.close(); }
});

function fs_write(g, rel, text) { import("node:fs").then((fs) => fs.writeFileSync(g.file(rel), text)); }

test("a relay that rejects the token never gets a session and the editor keeps retrying quietly", async () => {
  const rport = await freePort();
  const relay = createRelay({ tokens: new Set(["z".repeat(48)]) });
  await listen(relay, rport);
  const g = await startGodot({ relayCfg: { url: `ws://127.0.0.1:${rport}`, token: TOKEN } });
  try {
    await sleep(4000);
    const st = await g.tool("status");
    assert.notEqual(st.json.relay, "connected");
    assert.doesNotMatch(g.log, new RegExp(TOKEN)); // secret must never be logged
  } finally { await g.stop(); await closeAll(relay); }
});
