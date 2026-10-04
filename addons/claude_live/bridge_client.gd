@tool
extends RefCounted
## Outbound WebSocket to the relay. Config: user://claude_live_relay.json {"url":"wss://host","token":"..."}
## Reconnects forever with bounded exponential backoff (1s..30s) and a heartbeat.

const CFG := "user://claude_live_relay.json"
const HB_MS := 15000
const DEAD_MS := 45000

var server  # mcp_server.gd instance (handle_message)
var state := "disabled"  # disabled | connecting | connected | backoff
var _ws := WebSocketPeer.new()
var _url := ""
var _token := ""
var _backoff := 1.0
var _retry_at := 0
var _last_rx := 0
var _last_hb := 0
var _seen := {}  # relay ids already answered: duplicate protection
var _seen_order: Array = []


func _init(p_server) -> void:
	server = p_server
	if not FileAccess.file_exists(CFG):
		return
	var cfg = JSON.parse_string(FileAccess.get_file_as_string(CFG))
	if cfg is Dictionary and str(cfg.get("url", "")) != "" and str(cfg.get("token", "")).length() >= 32:
		_url = str(cfg.url).rstrip("/") + "/plugin"
		_token = str(cfg.token)
		_ws.handshake_headers = PackedStringArray(["Authorization: Bearer " + _token])
		state = "backoff"


func _connect() -> void:
	_ws = WebSocketPeer.new()
	_ws.handshake_headers = PackedStringArray(["Authorization: Bearer " + _token])
	_ws.inbound_buffer_size = 16 * 1024 * 1024
	_ws.outbound_buffer_size = 16 * 1024 * 1024
	if _ws.connect_to_url(_url) == OK:
		state = "connecting"
		_last_rx = Time.get_ticks_msec()
	else:
		_schedule_retry()


func _schedule_retry() -> void:
	state = "backoff"
	_retry_at = Time.get_ticks_msec() + int(_backoff * 1000.0)
	_backoff = min(_backoff * 2.0, 30.0)


func poll() -> void:
	if state == "disabled":
		return
	var now := Time.get_ticks_msec()
	if state == "backoff":
		if now >= _retry_at:
			_connect()
		return
	_ws.poll()
	match _ws.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if state != "connected":
				state = "connected"
				_backoff = 1.0
				print("[claude_live] relay connected")
			while _ws.get_available_packet_count() > 0:
				_last_rx = now
				_on_text(_ws.get_packet().get_string_from_utf8())
			if now - _last_hb > HB_MS:
				_last_hb = now
				_ws.send_text('{"type":"hb"}')
			if now - _last_rx > DEAD_MS:
				_ws.close(4001, "dead")
		WebSocketPeer.STATE_CLOSED:
			print("[claude_live] relay lost (code %d); retrying" % _ws.get_close_code())
			_schedule_retry()
		WebSocketPeer.STATE_CONNECTING:
			if now - _last_rx > 20000:
				_ws.close()


func _on_text(text: String) -> void:
	var m = JSON.parse_string(text)
	if not (m is Dictionary):
		return
	if m.get("type", "") == "hb":
		return
	var id = m.get("id", null)
	var key := str(id)
	if id != null and _seen.has(key):
		_ws.send_text(_seen[key])  # duplicate delivery: replay, never re-execute
		return
	var out = server.handle_message(m)
	if out == null:
		return
	var s := JSON.stringify(out)
	_seen[key] = s
	_seen_order.append(key)
	if _seen_order.size() > 128:
		_seen.erase(_seen_order.pop_front())
	_ws.send_text(s)


func stop() -> void:
	if state != "disabled":
		_ws.close(1000, "bye")
