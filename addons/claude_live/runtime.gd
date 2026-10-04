extends Node
## Claude Live runtime probe. Registered as an autoload by the plugin; does nothing unless the game
## was started from the editor (debugger attached). Read-only: screenshot, scene tree, property
## reads, stats, and log forwarding. It never executes code sent by the editor.

const Compat := preload("res://addons/claude_live/compat.gd")
const MAX_NODES := 400

var _mutex := Mutex.new()
var _outbox: Array = []
var _logger  # Logger (4.5+), optional


func _ready() -> void:
	if not EngineDebugger.is_active():
		set_process(false)
		return
	EngineDebugger.register_message_capture("claude_live", _on_message)
	_logger = Compat.make_logger("game", _enqueue_log)
	EngineDebugger.send_message("claude_live:hello", [Engine.get_version_info().string])


func _exit_tree() -> void:
	Compat.remove_logger(_logger)


func _enqueue_log(_source: String, kind: String, msg: String, where: String) -> void:
	_mutex.lock()
	if _outbox.size() < 200:
		_outbox.append([kind, msg, where])
	_mutex.unlock()


func _process(_delta: float) -> void:
	_mutex.lock()
	var batch := _outbox
	_outbox = []
	_mutex.unlock()
	for e in batch:
		EngineDebugger.send_message("claude_live:log", e)


func _on_message(message: String, data: Array) -> bool:
	if not message.ends_with("cmd"):
		return false
	var id: int = int(data[0])
	var op: String = str(data[1])
	var args: Dictionary = data[2] if data.size() > 2 and data[2] is Dictionary else {}
	var result: Variant
	match op:
		"screenshot": result = _screenshot(args)
		"tree": result = _tree(args)
		"get": result = _get_prop(args)
		"stats": result = _stats()
		_: result = {"error": "unknown op " + op}
	EngineDebugger.send_message("claude_live:reply", [id, result])
	return true


func _screenshot(args: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless":
		return {"error": "the game is running headless (no renderer), so there is nothing to capture"}
	var img: Image = get_viewport().get_texture().get_image()
	if img == null or img.is_empty():
		return {"error": "no image available yet"}
	var max_w := int(args.get("max_width", 960))
	if max_w > 0 and img.get_width() > max_w:
		img.resize(max_w, int(img.get_height() * float(max_w) / img.get_width()), Image.INTERPOLATE_BILINEAR)
	return {"png": img.save_png_to_buffer(), "width": img.get_width(), "height": img.get_height()}


func _props_for(n: Node, extra: Array) -> Dictionary:
	var d := {}
	var wanted: Array = ["text", "position", "visible", "size", "modulate"] + extra
	for p in wanted:
		if p in n:
			d[p] = var_to_str(n.get(p))
	return d


func _tree(args: Dictionary) -> Dictionary:
	var out: Array = []
	var depth := int(args.get("depth", 6))
	var extra: Array = args.get("props", []) if args.get("props") is Array else []
	_walk(get_tree().root, "/root", depth, out, extra)
	var cur := get_tree().current_scene
	return {"scene": cur.scene_file_path if cur else "", "nodes": out, "truncated": out.size() >= MAX_NODES}


func _walk(n: Node, path: String, depth: int, out: Array, extra: Array) -> void:
	if out.size() >= MAX_NODES:
		return
	if n == self:
		return
	out.append({"path": path, "type": n.get_class(), "script": n.get_script().resource_path if n.get_script() else "", "props": _props_for(n, extra)})
	if depth > 0:
		for c in n.get_children():
			_walk(c, path + "/" + str(c.name), depth - 1, out, extra)


func _get_prop(args: Dictionary) -> Dictionary:
	var n := get_node_or_null(NodePath(str(args.get("node", ""))))
	if n == null:
		return {"error": "node not found"}
	var prop := str(args.get("property", ""))
	if not (prop in n):
		return {"error": "no such property"}
	return {"value": var_to_str(n.get(prop))}


func _stats() -> Dictionary:
	return {
		"fps": Performance.get_monitor(Performance.TIME_FPS),
		"process_ms": Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		"objects": Performance.get_monitor(Performance.OBJECT_COUNT),
		"static_memory_mb": Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0,
		"frames": Engine.get_frames_drawn(),
		"scene": get_tree().current_scene.scene_file_path if get_tree().current_scene else "",
		"window": str(DisplayServer.window_get_size()),
		"renderer": DisplayServer.get_name(),
	}
