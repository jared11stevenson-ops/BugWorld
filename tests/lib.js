// Test harness: copies the project to a temp dir, runs a real headless Godot editor with the plugin,
// and talks to it over its loopback MCP port. Needs GODOT_BIN (Godot 4.4+ Linux binary).
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import net from "node:net";
import crypto from "node:crypto";

export const GODOT = process.env.GODOT_BIN || "/tmp/g/Godot_v4.5-stable_linux.x86_64";
export const REPO = path.resolve(import.meta.dirname, "..");
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const sha256 = (s) => crypto.createHash("sha256").update(s).digest("hex");

export function freePort() {
  return new Promise((res) => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); }); });
}

function copyProject(dst) {
  for (const f of ["project.godot", "main.gd", "main.gd.uid", "main.tscn"]) if (fs.existsSync(path.join(REPO, f))) fs.copyFileSync(path.join(REPO, f), path.join(dst, f));
  fs.cpSync(path.join(REPO, "addons"), path.join(dst, "addons"), { recursive: true });
}

/** relayCfg: optional {url, token}; written to the plugin's user dir before start (as the dock would). */
export async function startGodot({ relayCfg, env = {}, display = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "cl-test-"));
  const project = path.join(root, "project");
  const xdg = path.join(root, "xdg");
  fs.mkdirSync(project);
  copyProject(project);
  const userDir = path.join(xdg, "godot", "app_userdata", "Claude Live Test");
  fs.mkdirSync(userDir, { recursive: true });
  if (relayCfg) fs.writeFileSync(path.join(userDir, "claude_live_relay.json"), JSON.stringify(relayCfg));
  const port = await freePort();
  let log = "";
  // display=true: real (software-rendered) editor under Xvfb, needed to launch the game and take screenshots.
  const cmd = display ? "xvfb-run" : GODOT;
  const args = display
    ? ["-a", "-s", "-screen 0 1280x720x24", GODOT, "--rendering-driver", "opengl3", "--editor", "--path", project]
    : ["--headless", "--editor", "--path", project];
  const proc = spawn(cmd, args, {
    detached: true,
    env: { ...process.env, XDG_DATA_HOME: xdg, XDG_CONFIG_HOME: path.join(root, "xdgc"), XDG_CACHE_HOME: path.join(root, "xdgk"), CLAUDE_LIVE_PORT: String(port), ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  proc.stdout.on("data", (d) => (log += d));
  proc.stderr.on("data", (d) => (log += d));
  const g = {
    root, project, userDir, port, proc, get log() { return log; },
    token: "",
    async rpc(method, params = {}, { token, headers = {}, id = 1 } = {}) {
      const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
        method: "POST",
        headers: { authorization: `Bearer ${token ?? g.token}`, "content-type": "application/json", ...headers },
        body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
      });
      return { status: res.status, body: res.status === 200 ? await res.json() : await res.text() };
    },
    /** Calls a tool; returns {isError, text, json}. */
    async tool(name, args = {}) {
      const { status, body } = await g.rpc("tools/call", { name, arguments: args });
      if (status !== 200) throw new Error(`HTTP ${status}: ${body}`);
      const r = body.result;
      const text = r.content?.[0]?.text ?? "";
      let json; try { json = JSON.parse(text); } catch {}
      return { isError: !!r.isError, text, json, raw: r };
    },
    file: (rel) => path.join(project, rel),
    read: (rel) => fs.readFileSync(path.join(project, rel), "utf8"),
    exists: (rel) => fs.existsSync(path.join(project, rel)),
    async stop() { try { process.kill(-proc.pid, "SIGKILL"); } catch {} await sleep(300); fs.rmSync(root, { recursive: true, force: true }); },
  };
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) {
    if (/MCP ready/.test(log)) break;
    if (proc.exitCode !== null) throw new Error("godot exited early:\n" + log.slice(-2000));
    await sleep(200);
  }
  g.token = fs.readFileSync(path.join(userDir, "claude_live_token"), "utf8").trim();
  for (let i = 0; i < 100; i++) { try { const r = await g.rpc("ping"); if (r.status === 200) break; } catch {} await sleep(200); }
  return g;
}
