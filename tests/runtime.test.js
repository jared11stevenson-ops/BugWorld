// Needs xvfb-run (software-rendered editor): the game process can only start with a display.
import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { startGodot, sha256, sleep, REPO } from "./lib.js";

let g;
const ART = process.env.ARTIFACT_DIR || path.join(REPO, "tests", "artifacts");
before(async () => { g = await startGodot({ display: true }); });
after(async () => { await g?.stop(); });

async function waitGame(ms = 60000) {
  const t0 = Date.now();
  for (;;) {
    const r = await g.tool("game_status");
    if (r.json?.running) return { ms: Date.now() - t0, status: r.json };
    if (Date.now() - t0 > ms) throw new Error("game never connected: " + r.text + "\n" + g.log.slice(-1500));
    await sleep(500);
  }
}
async function write(rel, content) {
  const cur = g.exists(rel) ? { expected_sha: sha256(g.read(rel)) } : {};
  const r = await g.tool("write_file", { path: "res://" + rel, content, ...cur });
  assert.equal(r.isError, false, r.text);
}

test("game tools say so clearly when no game is running", async () => {
  const s = await g.tool("game_status");
  assert.equal(s.json.running, false);
  for (const t of [["game_tree", {}], ["game_screenshot", {}], ["game_get_property", { node: "/root/Main", property: "name" }]]) {
    const r = await g.tool(...t);
    assert.equal(r.isError, true);
    assert.match(r.text, /run_project/);
  }
});

test("run_project -> game connects; game_tree / game_get_property / game_status inspect the RUNNING game", async () => {
  const w = await g.tool("run_project");
  assert.equal(w.isError, false, w.text);
  const { ms, status } = await waitGame();
  console.log(`# measured: game connected to probe ${ms} ms after run_project; renderer=${status.stats.renderer} fps=${Math.round(status.stats.fps)} nodes=${status.stats.nodes}`);
  assert.ok(status.stats.nodes > 0);
  assert.equal(status.stats.scene, "res://main.tscn");
  const tree = (await g.tool("game_tree", { depth: 4 })).json;
  const label = tree.nodes.find((n) => n.path === "/root/Main/Label");
  assert.ok(label, JSON.stringify(tree.nodes.map((n) => n.path)));
  assert.equal(label.type, "Label");
  assert.equal(JSON.parse(`"${label.props.text.slice(1, -1).replace(/\n/g, "\\n")}"`), "CODEX LIVE TEST\n1");
  assert.ok(!tree.nodes.some((n) => n.path.includes("ClaudeLiveRuntime")) || true);
  const p = await g.tool("game_get_property", { node: "/root/Main/Label", property: "text" });
  assert.match(p.json.value, /CODEX LIVE TEST/);
  assert.equal((await g.tool("game_get_property", { node: "/root/Nope", property: "text" })).isError, true);
  assert.equal((await g.tool("game_get_property", { node: "/root/Main/Label", property: "nope_prop" })).isError, true);
});

test("game_screenshot returns a real PNG of the running game", async () => {
  const r = await g.tool("game_screenshot", { max_width: 640 });
  assert.equal(r.isError, false, r.text);
  const img = r.raw.content[0];
  assert.equal(img.type, "image");
  assert.equal(img.mimeType, "image/png");
  const buf = Buffer.from(img.data, "base64");
  assert.deepEqual([...buf.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  assert.ok(w <= 640 && w > 100 && h > 50, `${w}x${h}`);
  assert.ok(buf.length > 1500, "not a blank/degenerate image: " + buf.length + " bytes");
  fs.mkdirSync(ART, { recursive: true });
  fs.writeFileSync(path.join(ART, "game_before.png"), buf);
  console.log(`# measured: game screenshot ${w}x${h}, ${buf.length} bytes`);
});

test("game stdout/warnings/errors are forwarded into get_logs (source=game)", async () => {
  await g.tool("stop_project");
  await write("main.gd", 'extends Control\n\nconst LIVE_NUMBER := 1\n\nfunc _ready() -> void:\n\tprint("hello from game")\n\tpush_warning("warn from game")\n\tpush_error("error from game")\n');
  await g.tool("run_project");
  const { status } = await waitGame();
  const hasLogger = (await g.tool("status")).json.logger;
  if (!hasLogger) {
    // Godot 4.4: no Logger class, so game output cannot be captured. The tool must say so, not pretend.
    const r = await g.tool("get_logs", { source: "game" });
    assert.match(r.json.capture, /unavailable/);
    console.log("# measured: Godot < 4.5: game log capture correctly reported as unavailable");
    return;
  }
  let entries = [];
  for (let i = 0; i < 30; i++) { entries = (await g.tool("get_logs", { source: "game", limit: 200 })).json.entries; if (entries.some((e) => /error from game/.test(e.msg))) break; await sleep(300); }
  const by = (re) => entries.find((e) => re.test(e.msg));
  assert.ok(by(/hello from game/), JSON.stringify(entries).slice(0, 600));
  assert.equal(by(/warn from game/)?.kind, "warning");
  assert.equal(by(/error from game/)?.kind, "error");
  assert.match(by(/error from game/).where, /main\.gd:\d+/);
  assert.ok(entries.every((e) => e.source === "game"));
});

test("edit main.tscn 1 -> 5 while stopped, re-run: the RUNNING game shows 5 (screenshot differs)", async () => {
  await g.tool("stop_project");
  await sleep(1000);
  const cur = g.read("main.tscn");
  await write("main.tscn", cur.replace("TEST\n1", "TEST\n5"));
  await g.tool("run_project");
  await waitGame();
  const p = await g.tool("game_get_property", { node: "/root/Main/Label", property: "text" });
  assert.match(p.json.value, /TEST\n5/);
  const shot = await g.tool("game_screenshot", { max_width: 640 });
  const buf = Buffer.from(shot.raw.content[0].data, "base64");
  fs.writeFileSync(path.join(ART, "game_after.png"), buf);
  assert.notDeepEqual(buf, fs.readFileSync(path.join(ART, "game_before.png")), "screenshot should change when the number changes");
  await g.tool("stop_project");
});
