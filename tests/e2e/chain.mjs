// Full chain, locally: headless-ish Godot editor (Xvfb) -> relay (separate process) -> real `claude` CLI over MCP.
// Run:  GODOT_BIN=... node tests/e2e/chain.mjs      Evidence goes to evidence/e2e/ (secrets scrubbed).
import { spawn, execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { startGodot, freePort, sleep, REPO } from "../lib.js";

const OUT = path.join(REPO, "evidence", "e2e");
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
const work = fs.mkdtempSync(path.join(os.tmpdir(), "cl-chain-"));
const HOME = path.join(work, "home");           // scratch HOME: claude's config lives here, not in the real one
const CWD = path.join(work, "cwd");
fs.mkdirSync(HOME); fs.mkdirSync(CWD);
const STRIP = fs.readFileSync("/tmp/g/strip.txt", "utf8").trim().split(/\s+/).filter((x) => x !== "-u"); // session identity vars of the *outer* session
const cleanEnv = { ...process.env, HOME };
for (const k of STRIP) delete cleanEnv[k];

const summary = { started: new Date().toISOString(), steps: [] };
let TOKEN = "";
const scrub = (s) => (TOKEN ? s.split(TOKEN).join("<TOKEN>") : s);
const save = (name, text) => fs.writeFileSync(path.join(OUT, name), scrub(text));
const log = (...a) => console.log(...a);

// 1. relay (real relay.js in its own process, with the opt-in operational log)
const rport = await freePort();
const connFile = path.join(work, "claude-live-connection.json");
const gen = execFileSync("node", [path.join(REPO, "tools/make-connection.mjs"), "--url", `http://127.0.0.1:${rport}`, "--out", connFile], { encoding: "utf8" });
TOKEN = JSON.parse(fs.readFileSync(connFile, "utf8")).token;
const addCmd = gen.split("\n").find((l) => l.includes("claude mcp add")).trim();
const relayLog = path.join(work, "relay.log");
const relay = spawn("node", [path.join(REPO, "relay/relay.js")], { env: { ...process.env, PORT: String(rport), RELAY_TOKENS: TOKEN, RELAY_LOG: "1" }, stdio: ["ignore", fs.openSync(relayLog, "a"), fs.openSync(relayLog, "a")] });
await sleep(800);
log("relay up on", rport, "| health:", (await fetch(`http://127.0.0.1:${rport}/healthz`)).status);

// 2. Godot editor (Xvfb) imports the generated connection file exactly like the dock's Load connection
const g = await startGodot({ display: true, env: { CLAUDE_LIVE_IMPORT: connFile } });
await g.tool("open_scene", { path: "res://main.tscn" });
const labelText = async () => (await g.tool("get_property", { node: "Label", property: "text" })).json.value;
const connectedT0 = Date.now();
for (;;) { const r = await fetch(`http://127.0.0.1:${rport}/mcp`, { method: "POST", headers: { authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "ping" }) }).then((x) => x.json()); if (!r.error) break; if (Date.now() - connectedT0 > 60000) throw new Error("plugin never connected to relay"); await sleep(300); }
log("editor connected to relay; initial label:", JSON.stringify(await labelText()));

// 3. register the relay with Claude Code using the exact command the generator printed
const reg = spawnSync("bash", ["-lc", addCmd], { cwd: CWD, env: cleanEnv, encoding: "utf8" });
log("claude mcp add ->", scrub((reg.stdout + reg.stderr).trim().split("\n").pop()));
const list = spawnSync("claude", ["mcp", "list"], { cwd: CWD, env: cleanEnv, encoding: "utf8", timeout: 60000 });
save("claude-mcp-list.txt", list.stdout + list.stderr);
log(scrub(list.stdout).trim().split("\n").filter((l) => /godot/.test(l)).join("\n"));
summary.mcp_list = scrub(list.stdout).trim().split("\n").filter((l) => /godot/.test(l));

// 4. one Claude step at a time, in ONE Claude session
const sid = crypto.randomUUID();
async function claudeStep(n, prompt, first) {
  const args = ["-p", prompt, "--output-format", "stream-json", "--verbose", "--tools", "", "--allowedTools", "mcp__godot", ...(first ? ["--session-id", sid] : ["--resume", sid])];
  const t0 = Date.now();
  const p = spawn("claude", args, { cwd: CWD, env: cleanEnv, stdio: ["ignore", "pipe", "pipe"] });
  let out = "", err = ""; p.stdout.on("data", (d) => (out += d)); p.stderr.on("data", (d) => (err += d));
  const done = new Promise((res) => p.on("close", res));
  return { t0, p, done, get out() { return out; }, get err() { return err; } };
}
const parseEvents = (out) => out.split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
const sha = (s) => crypto.createHash("sha256").update(s).digest("hex");

for (let k = 1; k <= 4; k++) {
  const before = g.read("main.tscn");
  const prompt = `You are connected to a live Godot editor through the "godot" MCP server. Use ONLY that server's tools. Step ${k}: in res://main.tscn the Label text is "CODEX LIVE TEST" followed by a newline and the number ${k}. Change that number to ${k + 1} and change nothing else. Then reply with one line: the sha256 returned by the write.`;
  const run = await claudeStep(k, prompt, k === 1);
  let seenAt = null;
  const watch = (async () => { for (;;) { const v = await labelText(); if (v.includes(`TEST\n${k + 1}`)) { seenAt = Date.now() - run.t0; return; } if (Date.now() - run.t0 > 240000) return; await sleep(100); } })();
  const code = await run.done;
  await Promise.race([watch, sleep(5000)]);
  const wall = Date.now() - run.t0;
  const after = g.read("main.tscn");
  const ev = parseEvents(run.out);
  save(`step-${k}.stream.jsonl`, run.out);
  const toolCalls = [];
  for (const e of ev) if (e.type === "assistant") for (const c of e.message?.content ?? []) if (c.type === "tool_use") toolCalls.push({ tool: c.name, path: c.input?.path, has_expected_sha: !!c.input?.expected_sha });
  const result = ev.find((e) => e.type === "result");
  const relayLines = fs.readFileSync(relayLog, "utf8").split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const diffLines = before.split("\n").map((l, i) => [l, after.split("\n")[i]]).filter(([a, b]) => a !== b);
  const rec = {
    step: k, expect: `${k} -> ${k + 1}`, claude_exit: code, claude_is_error: result?.is_error, claude_final_text: scrub(String(result?.result ?? "")).slice(0, 300),
    claude_tool_calls: toolCalls, wall_ms: wall, editor_showed_new_value_ms_after_prompt: seenAt,
    editor_label_now: await labelText(), file_changed_lines: diffLines.length, file_sha256: sha(after),
    only_digit_changed: diffLines.length === 1 && diffLines[0][0] === `${k}"` && diffLines[0][1] === `${k + 1}"`,
    relay_replies_total: relayLines.filter((l) => l.ev === "reply").length,
  };
  summary.steps.push(rec);
  log(`step ${k}:`, JSON.stringify({ ...rec, claude_final_text: rec.claude_final_text.slice(0, 80) }));
  if (code !== 0) { log("claude stderr:", scrub(run.err).slice(0, 500)); }
  // visual proof from the editor viewport after each step
  await sleep(800);
  const shot = await g.tool("screenshot", { view: "2d", max_width: 640 });
  if (!shot.isError) fs.writeFileSync(path.join(OUT, `editor-after-step-${k}.png`), Buffer.from(shot.raw.content[0].data, "base64"));
}

// 5. bonus: Claude drives the running game and screenshots it, through the relay
{
  const prompt = `Using only the "godot" MCP server: run the project, wait until the game is running (poll game_status), then take a game_screenshot and tell me in one sentence what number the label shows.`;
  const run = await claudeStep(5, prompt, false);
  const code = await run.done;
  const ev = parseEvents(run.out);
  save("step-5-game.stream.jsonl", run.out);
  const result = ev.find((e) => e.type === "result");
  const calls = []; for (const e of ev) if (e.type === "assistant") for (const c of e.message?.content ?? []) if (c.type === "tool_use") calls.push(c.name);
  summary.game_step = { claude_exit: code, tools: calls, final_text: scrub(String(result?.result ?? "")).slice(0, 400) };
  log("game step:", JSON.stringify(summary.game_step));
  await g.tool("stop_project");
}

await sleep(2500);
{ const w = await g.tool("screenshot", { view: "editor" }); if (!w.isError) fs.writeFileSync(path.join(OUT, "editor-window-final.png"), Buffer.from(w.raw.content[0].data, "base64")); }
summary.final = { label: await labelText(), file_tail: g.read("main.tscn").split("\n").slice(-4).join("\\n") };
summary.relay_log_lines = fs.readFileSync(relayLog, "utf8").split("\n").filter(Boolean).length;
summary.finished = new Date().toISOString();
save("summary.json", JSON.stringify(summary, null, 2));
save("relay.log", fs.readFileSync(relayLog, "utf8"));
save("godot-editor.log", g.log.split("\n").filter((l) => !/ALSA|^\[ *\d+%|\[ DONE/.test(l)).join("\n"));
const leaked = fs.readdirSync(OUT).filter((f) => fs.readFileSync(path.join(OUT, f)).includes(TOKEN));
log("token present in evidence files:", leaked.length ? leaked : "none");
await g.stop(); relay.kill();
fs.rmSync(work, { recursive: true, force: true });
process.exit(leaked.length ? 1 : 0);
