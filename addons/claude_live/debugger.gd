@tool
extends EditorDebuggerPlugin
## Editor side of the runtime probe: forwards game logs into get_logs and answers game_* requests.

var tools
var _seq := 0
var _replies := {}
var _sessions := {}  # session id -> EditorDebuggerSession
var _hello := {}  # session id -> game version string (set when the game's probe says hello)


func _has_capture(prefix: String) -> bool:
	return prefix == "claude_live"


func _capture(message: String, data: Array, session_id: int) -> bool:
	if message.ends_with("hello"):
		_hello[session_id] = str(data[0]) if data.size() > 0 else "?"
		return true
	if message.ends_with("log"):
		if tools:
			tools.add_log("game", str(data[0]), str(data[1]), str(data[2]))
		return true
	if message.ends_with("reply"):
		_replies[int(data[0])] = data[1]
		return true
	return false


func _setup_session(session_id: int) -> void:
	var s := get_session(session_id)
	_sessions[session_id] = s
	# Godot reuses the same session object for every run, so keep it; only forget the hello.
	s.stopped.connect(func(): _hello.erase(session_id))


## The newest active session whose probe has said hello.
func active_session() -> EditorDebuggerSession:
	var ids := _sessions.keys()
	ids.sort()
	ids.reverse()
	for id in ids:
		var s: EditorDebuggerSession = _sessions[id]
		if s and s.is_active() and _hello.has(id):
			return s
	return null


func is_game_connected() -> bool:
	return active_session() != null


## Coroutine: returns the game's reply Dictionary, or {"error": ...}.
func request(op: String, args: Dictionary = {}, timeout_s: float = 10.0) -> Dictionary:
	var s := active_session()
	if s == null:
		return {"error": "the game is not running (or has not connected yet). Call run_project first."}
	_seq += 1
	var id := _seq
	s.send_message("claude_live:cmd", [id, op, args])
	var t0 := Time.get_ticks_msec()
	var loop := Engine.get_main_loop() as SceneTree
	while not _replies.has(id) and Time.get_ticks_msec() - t0 < int(timeout_s * 1000.0):
		await loop.process_frame
	if not _replies.has(id):
		return {"error": "the game did not answer within %.0fs" % timeout_s}
	var r = _replies[id]
	_replies.erase(id)
	return r if r is Dictionary else {"error": "bad reply"}
