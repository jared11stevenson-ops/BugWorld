#!/usr/bin/env node
// Generates the connection file for the Godot "Load connection" button and prints the exact
// commands to deploy the relay secret and to register the relay with Claude Code.
//
//   node tools/make-connection.mjs --url https://my-relay.fly.dev [--out ~/claude-live-connection.json] [--token <existing>]
//
// The secret is written only to the --out file (mode 0600, refused inside a git work tree)
// and to your terminal. It is never written to the project.
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";

function parse(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith("--")) throw new Error("unexpected argument " + argv[i]);
    o[argv[i].slice(2)] = argv[++i];
  }
  return o;
}

export function build({ url, token }) {
  if (!url) throw new Error("--url is required, e.g. --url https://my-relay.fly.dev");
  let u;
  try { u = new URL(url); } catch { throw new Error("--url is not a valid URL: " + url); }
  const local = ["127.0.0.1", "localhost", "::1"].includes(u.hostname);
  if (u.protocol === "ws:") u.protocol = "http:";
  if (u.protocol === "wss:") u.protocol = "https:";
  if (!["http:", "https:"].includes(u.protocol)) throw new Error("--url must be https://… (or http://localhost for local tests)");
  if (u.protocol === "http:" && !local) throw new Error("Refusing plain http to a non-local host: the token would travel unencrypted. Use https://");
  const base = u.origin;
  const tok = token || crypto.randomBytes(32).toString("hex");
  if (tok.length < 40) throw new Error("token must be at least 40 characters");
  const wsUrl = base.replace(/^http/, "ws");
  const file = { url: wsUrl, token: tok };
  const mcpUrl = base + "/mcp";
  return {
    file,
    token: tok,
    addCommand: `claude mcp add --transport http godot ${mcpUrl} --header "Authorization: Bearer ${tok}"`,
    flySecret: `fly secrets set RELAY_TOKENS=${tok}`,
    renderEnv: `RELAY_TOKENS=${tok}`,
  };
}

function insideGitWorkTree(dir) {
  try { return execFileSync("git", ["-C", dir, "rev-parse", "--is-inside-work-tree"], { stdio: ["ignore", "pipe", "ignore"] }).toString().trim() === "true"; } catch { return false; }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const a = parse(process.argv.slice(2));
    const r = build({ url: a.url, token: a.token });
    const out = path.resolve((a.out || path.join(os.homedir(), "claude-live-connection.json")).replace(/^~/, os.homedir()));
    if (insideGitWorkTree(path.dirname(out)) && !process.env.CLAUDE_LIVE_ALLOW_GIT_DIR) throw new Error(`Refusing to write a secret inside a git work tree (${path.dirname(out)}). Choose --out outside the repository.`);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, JSON.stringify(r.file, null, 2) + "\n", { mode: 0o600 });
    fs.chmodSync(out, 0o600);
    console.log(`Connection file written: ${out}   (secret; do not commit or share)\n`);
    console.log("1) Give the relay the secret (pick one):");
    console.log(`   Fly.io : ${r.flySecret}`);
    console.log(`   Render : set environment variable ${r.renderEnv}\n`);
    console.log("2) Register the relay with Claude Code (run where Claude Code runs):");
    console.log(`   ${r.addCommand}\n`);
    console.log("3) Put the file on the phone, open Godot > Claude Live dock > Load connection, pick it.");
  } catch (e) {
    console.error("error: " + e.message);
    process.exit(1);
  }
}
