// Minimal relay: Claude Code --(MCP HTTP, bearer)--> relay <--(outbound WS from Godot)-- plugin.
// Stateless apart from one live socket per pairing token. No project data is stored.
import http from "node:http";
import crypto from "node:crypto";
import { WebSocketServer } from "ws";

const TIMEOUT_MS = 60000;

export function createRelay({ tokens }) {
  // tokens: Set of pairing tokens (>=32 chars). Same token authenticates both sides of a pair.
  const plugins = new Map(); // token -> ws
  const pending = new Map(); // relayId -> {res, timer, token}
  let seq = 0;
  const ok = (t) => [...tokens].some((x) => x.length === t.length && crypto.timingSafeEqual(Buffer.from(x), Buffer.from(t)));

  const server = http.createServer((req, res) => {
    const token = (req.headers.authorization || "").replace(/^Bearer /, "");
    if (req.url !== "/mcp" || req.headers.origin) return res.writeHead(404).end();
    if (!token || !ok(token)) return res.writeHead(401).end("unauthorized");
    if (req.method !== "POST") return res.writeHead(405).end();
    let body = "";
    req.on("data", (c) => { body += c; if (body.length > 8e6) req.destroy(); });
    req.on("end", () => {
      let msg;
      try { msg = JSON.parse(body); } catch { return res.writeHead(400).end(); }
      if (Array.isArray(msg)) return res.writeHead(400).end("batches unsupported");
      const ws = plugins.get(token);
      const isNotification = msg.id === undefined || msg.id === null;
      if (!ws || ws.readyState !== 1) {
        if (isNotification) return res.writeHead(202).end();
        return res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({
          jsonrpc: "2.0", id: msg.id,
          error: { code: -32000, message: "Godot plugin is not connected. Open the project in Godot with the Claude Live plugin enabled." },
        }));
      }
      if (isNotification) { ws.send(JSON.stringify(msg)); return res.writeHead(202).end(); }
      const relayId = `r${++seq}`;
      const timer = setTimeout(() => {
        pending.delete(relayId);
        res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({ jsonrpc: "2.0", id: msg.id, error: { code: -32001, message: "Godot did not answer in time (it may be backgrounded or reconnecting). Retry; use request_id for safe retries." } }));
      }, TIMEOUT_MS);
      pending.set(relayId, { res, timer, origId: msg.id, token });
      ws.send(JSON.stringify({ ...msg, id: relayId }));
    });
  });

  const wss = new WebSocketServer({ noServer: true, maxPayload: 16e6 });
  server.on("upgrade", (req, sock, head) => {
    const token = (req.headers.authorization || "").replace(/^Bearer /, "");
    if (req.url !== "/plugin" || !token || !ok(token)) { sock.write("HTTP/1.1 401 Unauthorized\r\n\r\n"); return sock.destroy(); }
    wss.handleUpgrade(req, sock, head, (ws) => {
      const old = plugins.get(token);
      plugins.set(token, ws);
      if (old) old.close(4000, "replaced");
      ws.isAlive = true;
      ws.on("pong", () => (ws.isAlive = true));
      ws.on("message", (data) => {
        let m; try { m = JSON.parse(data.toString()); } catch { return; }
        if (m.type === "hb") return ws.send(JSON.stringify({ type: "hb" }));
        const p = pending.get(m.id);
        if (!p || p.token !== token) return; // duplicate/late reply: ignore
        pending.delete(m.id); clearTimeout(p.timer);
        p.res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({ ...m, id: p.origId }));
      });
      ws.on("close", () => { if (plugins.get(token) === ws) plugins.delete(token); });
    });
  });
  const sweep = setInterval(() => wss.clients.forEach((w) => { if (!w.isAlive) return w.terminate(); w.isAlive = false; w.ping(); }), 20000);
  server.on("close", () => clearInterval(sweep));
  return server;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const tokens = new Set((process.env.RELAY_TOKENS || "").split(",").filter((t) => t.length >= 32));
  if (!tokens.size) { console.error("Set RELAY_TOKENS=<comma list of >=32-char tokens>"); process.exit(1); }
  createRelay({ tokens }).listen(process.env.PORT || 8080, () => console.log("relay up"));
}
