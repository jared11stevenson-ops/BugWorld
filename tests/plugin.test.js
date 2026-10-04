import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { startGodot, sha256, sleep } from "./lib.js";

let g;
before(async () => { g = await startGodot(); });
after(async () => { await g?.stop(); });

const sceneText = () => g.read("main.tscn");

test("self_test passes inside real Godot", async () => {
  const r = await g.tool("self_test");
  assert.equal(r.json.all_passed, true, r.text);
  assert.match(r.json.godot, /^4\.\d/);
});

test("MCP handshake: initialize, tools/list, integer ids echoed as integers", async () => {
  const init = await g.rpc("initialize", { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "t", version: "0" } }, { id: 41 });
  assert.equal(init.body.id, 41);
  assert.equal(Number.isInteger(init.body.id), true);
  assert.equal(init.body.result.serverInfo.name, "claude-live-godot");
  const list = await g.rpc("tools/list");
  const names = list.body.result.tools.map((t) => t.name);
  for (const n of ["write_file", "read_file", "rollback", "self_test", "get_logs", "get_property"]) assert.ok(names.includes(n), n);
  const raw = await fetch(`http://127.0.0.1:${g.port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${g.token}` }, body: '{"jsonrpc":"2.0","id":7,"method":"ping"}' });
  assert.match(await raw.text(), /"id":7[,}]/); // not 7.0
});

test("HTTP auth and hardening", async () => {
  assert.equal((await g.rpc("ping", {}, { token: "wrong" })).status, 401);
  assert.equal((await g.rpc("ping", {}, { token: "" })).status, 401);
  assert.equal((await g.rpc("ping", {}, { headers: { origin: "http://evil.example" } })).status, 403);
  const get = await fetch(`http://127.0.0.1:${g.port}/mcp`, { headers: { authorization: `Bearer ${g.token}` } });
  assert.equal(get.status, 405);
  const nf = await fetch(`http://127.0.0.1:${g.port}/other`, { method: "POST", headers: { authorization: `Bearer ${g.token}` }, body: "{}" });
  assert.equal(nf.status, 404);
  const big = await fetch(`http://127.0.0.1:${g.port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${g.token}`, "content-length": String(9 * 1024 * 1024) }, body: "x" }).catch(() => ({ status: "closed" }));
  assert.ok([413, "closed"].includes(big.status), String(big.status));
});

test("path traversal is blocked for every file tool and nothing escapes the project", async () => {
  const outside = path.join(g.root, "outside");
  fs.mkdirSync(outside);
  const evil = [
    "../evil.txt", "res://../evil.txt", "a/../../evil.txt", "..\\evil.txt", "/etc/cl_evil.txt", "C:/cl_evil.txt",
    "user://evil.txt", "res://.git/config", ".git/config", "res://.godot/x.txt", "..", "res://sub/../../evil.txt",
  ];
  for (const p of evil) {
    for (const [tool, args] of [["write_file", { path: p, content: "pwn" }], ["read_file", { path: p }], ["delete_file", { path: p }], ["open_scene", { path: p }], ["validate_script", { path: p }], ["project_tree", { dir: p }], ["run_project", { scene: p }]]) {
      const r = await g.tool(tool, args);
      assert.equal(r.isError, true, `${tool}(${p}) must be rejected, got: ${r.text.slice(0, 120)}`);
    }
  }
  for (const f of [path.join(g.root, "evil.txt"), "/etc/cl_evil.txt", "/cl_evil.txt"]) assert.equal(fs.existsSync(f), false, f);
  assert.equal(g.exists(".git/config"), false);
});

test("path traversal via a symlink inside the project is blocked", async () => {
  const outside = path.join(g.root, "outside_sym");
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "secret.txt"), "TOPSECRET");
  fs.symlinkSync(outside, g.file("link"));
  const w = await g.tool("write_file", { path: "res://link/pwn.txt", content: "pwn" });
  assert.equal(w.isError, true, w.text);
  assert.equal(fs.existsSync(path.join(outside, "pwn.txt")), false, "write escaped through symlink");
  const r = await g.tool("read_file", { path: "res://link/secret.txt" });
  assert.equal(r.isError, true);
  assert.doesNotMatch(r.text, /TOPSECRET/);
  const t = await g.tool("project_tree", { dir: "res://link" });
  assert.doesNotMatch(t.text, /secret\.txt/);
  fs.unlinkSync(g.file("link"));
});

test("stale-hash write is rejected and leaves the file untouched", async () => {
  const p = "res://stale.txt";
  const c1 = await g.tool("write_file", { path: p, content: "v1" });
  assert.equal(c1.isError, false);
  const sha1 = c1.json.sha256;
  assert.equal(sha1, sha256("v1"));
  fs.writeFileSync(g.file("stale.txt"), "edited-outside"); // the user edits on the device meanwhile
  const w = await g.tool("write_file", { path: p, content: "v2", expected_sha: sha1 });
  assert.equal(w.isError, true);
  assert.match(w.text, /CONFLICT/);
  assert.equal(g.read("stale.txt"), "edited-outside");
  const noSha = await g.tool("write_file", { path: p, content: "v3" });
  assert.equal(noSha.isError, true);
  assert.equal(g.read("stale.txt"), "edited-outside");
  const ghost = await g.tool("write_file", { path: "res://ghost.txt", content: "x", expected_sha: sha1 });
  assert.equal(ghost.isError, true);
  assert.equal(g.exists("ghost.txt"), false);
  const ok = await g.tool("write_file", { path: p, content: "v4", expected_sha: sha256("edited-outside") });
  assert.equal(ok.isError, false);
  assert.equal(g.read("stale.txt"), "v4");
});

test("invalid GDScript / scene / JSON is rejected and the old file survives", async () => {
  const good = "extends Node\nfunc ok() -> int:\n\treturn 1\n";
  const w = await g.tool("write_file", { path: "res://v.gd", content: good });
  assert.equal(w.isError, false, w.text);
  for (const bad of ["func (((", "extends Node\nfunc f(:\n\tpass\n", "extends Node\nvar x = \n"]) {
    const r = await g.tool("write_file", { path: "res://v.gd", content: bad, expected_sha: sha256(good) });
    assert.equal(r.isError, true, bad);
    assert.match(r.text, /REJECTED/);
    assert.equal(g.read("v.gd"), good);
  }
  const nw = await g.tool("write_file", { path: "res://new_bad.gd", content: "func (((" });
  assert.equal(nw.isError, true);
  assert.equal(g.exists("new_bad.gd"), false);
  const v = await g.tool("validate_script", { source: "func (((" });
  assert.equal(v.json.valid, false);
  assert.equal((await g.tool("validate_script", { source: good })).json.valid, true);
  const scene = sceneText();
  const badScene = scene + '\n[node name="X" type="Label" parent="."\nbroken (((';
  const s = await g.tool("write_file", { path: "res://main.tscn", content: badScene, expected_sha: sha256(scene) });
  assert.equal(s.isError, true, s.text);
  assert.equal(sceneText(), scene);
  const j = await g.tool("write_file", { path: "res://x.json", content: "{nope" });
  assert.equal(j.isError, true);
  const forced = await g.tool("write_file", { path: "res://forced.gd", content: "func (((", allow_invalid: true });
  assert.equal(forced.isError, false); // explicit opt-in still works
  await g.tool("delete_file", { path: "res://forced.gd" });
});

test("rollback restores update, create and delete; unknown txn is an error", async () => {
  const p = "res://rb.txt";
  const a = await g.tool("write_file", { path: p, content: "one" });
  const b = await g.tool("write_file", { path: p, content: "two", expected_sha: a.json.sha256 });
  assert.equal(g.read("rb.txt"), "two");
  assert.equal((await g.tool("rollback", { txn: b.json.txn })).isError, false);
  assert.equal(g.read("rb.txt"), "one");
  assert.equal((await g.tool("rollback", { txn: a.json.txn })).isError, false); // undo the create
  assert.equal(g.exists("rb.txt"), false);
  const c = await g.tool("write_file", { path: p, content: "three" });
  const d = await g.tool("delete_file", { path: p, expected_sha: c.json.sha256 ?? sha256("three") });
  assert.equal(g.exists("rb.txt"), false);
  assert.equal((await g.tool("rollback", { txn: d.json.txn })).isError, false);
  assert.equal(g.read("rb.txt"), "three");
  assert.equal((await g.tool("rollback", { txn: "nope" })).isError, true);
  const list = await g.tool("list_transactions");
  assert.ok(list.json.length > 0);
});

test("duplicate request_id replays the first result and does not re-execute", async () => {
  const before = (await g.tool("status")).json.stats.writes;
  const args = { path: "res://dup.txt", content: "first", request_id: "req-dup-1" };
  const r1 = await g.tool("write_file", args);
  const r2 = await g.tool("write_file", args);
  const r3 = await g.tool("write_file", { ...args, content: "DIFFERENT" }); // same key: replay, not execute
  assert.equal(r1.isError, false);
  assert.equal(r2.text, r1.text);
  assert.equal(r3.text, r1.text);
  assert.equal(g.read("dup.txt"), "first");
  assert.equal((await g.tool("status")).json.stats.writes, before + 1);
  // A failed call must not poison its request_id: the retry after fixing the cause has to run.
  const bad = await g.tool("write_file", { path: "res://dup2.gd", content: "func (((", request_id: "req-dup-2" });
  assert.equal(bad.isError, true);
  const fixed = await g.tool("write_file", { path: "res://dup2.gd", content: "extends Node\n", request_id: "req-dup-2" });
  assert.equal(fixed.isError, false, fixed.text);
});

test("live refresh: a write to the OPEN scene shows up in the editor with no manual step; rollback too", async () => {
  assert.equal((await g.tool("open_scene", { path: "res://main.tscn" })).isError, false);
  const text = () => g.tool("get_property", { node: "Label", property: "text" }).then((r) => r.json.value.slice(1, -1));
  assert.equal(await text(), "CODEX LIVE TEST\n1");
  const cur = sceneText();
  const w = await g.tool("write_file", { path: "res://main.tscn", content: cur.replace("TEST\n1", "TEST\n5"), expected_sha: sha256(cur) });
  assert.equal(w.isError, false, w.text);
  let seen = ""; for (let i = 0; i < 20 && seen !== "CODEX LIVE TEST\n5"; i++) { seen = await text(); if (seen !== "CODEX LIVE TEST\n5") await sleep(100); }
  assert.equal(seen, "CODEX LIVE TEST\n5");
  assert.equal((await g.tool("rollback", { txn: w.json.txn })).isError, false);
  for (let i = 0; i < 20 && seen !== "CODEX LIVE TEST\n1"; i++) { seen = await text(); if (seen !== "CODEX LIVE TEST\n1") await sleep(100); }
  assert.equal(seen, "CODEX LIVE TEST\n1");
});

test("split / slow HTTP request is reassembled", async () => {
  const { default: net } = await import("node:net");
  const body = JSON.stringify({ jsonrpc: "2.0", id: 5, method: "ping" });
  const head = `POST /mcp HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer ${g.token}\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\n\r\n`;
  const reply = await new Promise((res, rej) => {
    const s = net.connect(g.port, "127.0.0.1");
    let out = ""; s.on("data", (d) => (out += d)); s.on("close", () => res(out)); s.on("error", rej);
    s.write(head.slice(0, 20));
    setTimeout(() => s.write(head.slice(20) + body.slice(0, 5)), 150);
    setTimeout(() => s.write(body.slice(5)), 300);
  });
  assert.match(reply, /200 OK/);
  assert.match(reply, /"id":5/);
});

test("screenshot reports a clear error when headless instead of crashing", async () => {
  const r = await g.tool("screenshot");
  assert.equal(r.isError, true);
  assert.match(r.text, /headless/);
});

test("control characters in file content / logs never produce invalid JSON", async () => {
  fs.writeFileSync(g.file("ansi.txt"), "\x1b[31mred\x1b[0m bell\x07 tab\t end\n");
  const res = await fetch(`http://127.0.0.1:${g.port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${g.token}` }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "read_file", arguments: { path: "res://ansi.txt" } } }) });
  const raw = await res.text();
  assert.doesNotMatch(raw, /[\x00-\x1f]/); // strict JSON: no raw control chars
  const inner = JSON.parse(JSON.parse(raw).result.content[0].text);
  assert.equal(inner.content, "\x1b[31mred\x1b[0m bell\x07 tab\t end\n");
  const logs = await fetch(`http://127.0.0.1:${g.port}/mcp`, { method: "POST", headers: { authorization: `Bearer ${g.token}` }, body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "get_logs", arguments: {} } }) });
  JSON.parse(await logs.text());
});

test("get_logs: native Logger captures editor output and errors; cursor and filters work", async () => {
  const st = await g.tool("status");
  const [maj, min] = (await g.tool("self_test")).json.godot.match(/^(\d+)\.(\d+)/).slice(1).map(Number);
  if (maj === 4 && min < 5) {
    // Godot 4.4: no Logger class. The plugin must still run and say so honestly.
    assert.equal(st.json.logger, false);
    const r = await g.tool("get_logs");
    assert.match(r.json.capture, /unavailable/);
    return;
  }
  assert.equal(st.json.logger, true, "engine Logger should be active on Godot 4.5+");
  let r = await g.tool("get_logs", { source: "editor" });
  assert.equal(r.json.capture, "engine Logger");
  assert.ok(r.json.entries.some((e) => /MCP ready/.test(e.msg)), "startup line captured");
  await g.tool("validate_script", { source: "func (((" }); // makes the engine log a parse error
  const first = (await g.tool("get_logs", { level: "problems" })).json;
  const err = first.entries.find((e) => /Parse Error|Expected function name/i.test(e.msg));
  assert.ok(err, "parse error captured: " + JSON.stringify(first.entries).slice(0, 400));
  assert.match(err.kind, /error/);
  assert.match(err.where, /gdscript|\.gd:\d+/i);
  assert.ok(first.entries.every((e) => e.kind !== "info"));
  const again = (await g.tool("get_logs", { since: first.next })).json; // cursor: only newer entries
  assert.ok(again.entries.every((e) => e.seq > first.next));
  assert.ok(again.next >= first.next);
  assert.equal((await g.tool("get_logs", { limit: 2 })).json.entries.length <= 2, true);
  const all = JSON.stringify((await g.tool("get_logs", { limit: 500 })).json);
  assert.doesNotMatch(all, new RegExp(g.token), "token must never appear in logs");
  const cleared = await g.tool("get_logs", { clear: true });
  assert.equal((await g.tool("get_logs", {})).json.entries.length >= 0, true);
});
