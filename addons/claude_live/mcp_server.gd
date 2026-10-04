@tool
extends RefCounted
## Minimal MCP Streamable-HTTP server (JSON responses only) over TCPServer.
## Loopback only; bearer-token auth; requests handled on the main thread.

const DEFAULT_PORT := 6590
const MAX_BODY := 8 * 1024 * 1024
const PROTOCOL := "2025-03-26"

var port: int = DEFAULT_PORT
var tools
var _tcp := TCPServer.new()
var _clients: Array = []  # {peer, buf, born}
var _token := ""


func _init(p_tools) -> void:
	tools = p_tools
	var env := OS.get_environment("CLAUDE_LIVE_PORT")
	if env.is_valid_int():
		port = env.to_int()
	_token = _load_or_create_token()


func token_path() -> String:
	return OS.get_user_data_dir().path_join("claude_live_token")


func _load_or_create_token() -> String:
	var path := token_path()
	if FileAccess.file_exists(path):
		var t := FileAccess.get_file_as_string(path).strip_edges()
		if t.length() >= 32:
			return t
	var crypto := Crypto.new()
	var t := crypto.generate_random_bytes(24).hex_encode()
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(t)
		f.close()
	return t


func start() -> int:
	return _tcp.listen(port, "127.0.0.1")


func stop() -> void:
	for c in _clients:
		c.peer.disconnect_from_host()
	_clients.clear()
	_tcp.stop()


func poll() -> void:
	if not _tcp.is_listening():
		return
	while _tcp.is_connection_available():
		_clients.append({"peer": _tcp.take_connection(), "buf": PackedByteArray(), "born": Time.get_ticks_msec()})
	for i in range(_clients.size() - 1, -1, -1):
		var c: Dictionary = _clients[i]
		var peer: StreamPeerTCP = c.peer
		peer.poll()
		if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			_clients.remove_at(i)
			continue
		var n := peer.get_available_bytes()
		if n > 0:
			var r := peer.get_data(n)
			if r[0] == OK:
				c.buf.append_array(r[1])
		if _try_handle(c):
			peer.disconnect_from_host()
			_clients.remove_at(i)
		elif Time.get_ticks_msec() - c.born > 30000:
			peer.disconnect_from_host()
			_clients.remove_at(i)


## Returns true when the request was answered (connection is then closed).
func _try_handle(c: Dictionary) -> bool:
	var buf: PackedByteArray = c.buf
	var text := buf.get_string_from_utf8()
	var sep := text.find("\r\n\r\n")
	if sep < 0:
		if buf.size() > 65536:
			_respond(c.peer, 431, "text/plain", "headers too large")
			return true
		return false
	var head := text.substr(0, sep)
	var lines := head.split("\r\n")
	var req := lines[0].split(" ")
	var headers := {}
	for j in range(1, lines.size()):
		var k := lines[j].find(":")
		if k > 0:
			headers[lines[j].substr(0, k).strip_edges().to_lower()] = lines[j].substr(k + 1).strip_edges()
	var clen := int(headers.get("content-length", "0"))
	if clen > MAX_BODY:
		_respond(c.peer, 413, "text/plain", "too large")
		return true
	var head_bytes := head.to_utf8_buffer().size() + 4
	if buf.size() < head_bytes + clen:
		return false
	var body := buf.slice(head_bytes, head_bytes + clen).get_string_from_utf8()
	if req.size() < 2 or req[1].split("?")[0] != "/mcp":
		_respond(c.peer, 404, "text/plain", "not found")
		return true
	# DNS-rebinding / browser protection: no Origin header allowed from web pages.
	if headers.has("origin"):
		_respond(c.peer, 403, "text/plain", "origin not allowed")
		return true
	if headers.get("authorization", "") != "Bearer " + _token:
		_respond(c.peer, 401, "text/plain", "unauthorized")
		return true
	if req[0] != "POST":
		_respond(c.peer, 405, "text/plain", "POST only")
		return true
	var parsed = JSON.parse_string(body)
	if parsed == null:
		_respond(c.peer, 400, "application/json", JSON.stringify({"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "parse error"}}))
		return true
	if parsed is Array:
		var outs := []
		for m in parsed:
			var o = handle_message(m)
			if o != null:
				outs.append(o)
		if outs.is_empty():
			_respond(c.peer, 202, "text/plain", "")
		else:
			_respond(c.peer, 200, "application/json", JSON.stringify(outs))
		return true
	var out = handle_message(parsed)
	if out == null:
		_respond(c.peer, 202, "text/plain", "")
	else:
		_respond(c.peer, 200, "application/json", JSON.stringify(out))
	return true


func handle_message(msg) -> Variant:
	if not (msg is Dictionary) or not msg.has("method"):
		return null  # responses from client: ignore
	var id = msg.get("id", null)
	var method: String = msg.method
	if id == null:
		return null  # notification
	var params: Dictionary = msg.get("params", {}) if msg.get("params") is Dictionary else {}
	match method:
		"initialize":
			return _ok(id, {
				"protocolVersion": PROTOCOL,
				"capabilities": {"tools": {"listChanged": false}},
				"serverInfo": {"name": "claude-live-godot", "version": "0.1.0"},
				"instructions": "You are editing the project that is open in the user's Godot editor, live. Prefer write_file/scene tools over any other route; every write is hash-checked, validated and snapshotted.",
			})
		"ping":
			return _ok(id, {})
		"tools/list":
			return _ok(id, {"tools": tools.definitions()})
		"tools/call":
			var name: String = params.get("name", "")
			var args: Dictionary = params.get("arguments", {}) if params.get("arguments") is Dictionary else {}
			return _ok(id, tools.call_tool(name, args))
	return {"jsonrpc": "2.0", "id": id, "error": {"code": -32601, "message": "method not found: " + method}}


func _ok(id, result) -> Dictionary:
	return {"jsonrpc": "2.0", "id": id, "result": result}


func _respond(peer: StreamPeerTCP, code: int, ctype: String, body: String) -> void:
	var reason := {200: "OK", 202: "Accepted", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large", 431: "Header Fields Too Large"}.get(code, "OK")
	var b := body.to_utf8_buffer()
	var h := "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % [code, reason, ctype, b.size()]
	peer.put_data(h.to_utf8_buffer())
	if b.size() > 0:
		peer.put_data(b)
