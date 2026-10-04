@tool
extends RefCounted
## MCP tool implementations. Every path is confined to res:// (the open project).

const MAX_SNAPSHOTS := 30
const SNAP_DIR := "user://claude_live_snapshots"
const DEDUP_MAX := 256
const Json := preload("res://addons/claude_live/json_util.gd")
const VALIDATE_DIR := "user://claude_live_validate"

var plugin: EditorPlugin
var _dedup := {}
var _dedup_order: Array = []
var _txn_seq := 0
var _snapshots: Array = []  # {id, path, existed, file, sha}
var _stats := {"calls": 0, "writes": 0, "rejected": 0}


func _init(p_plugin: EditorPlugin) -> void:
	plugin = p_plugin
	DirAccess.make_dir_recursive_absolute(SNAP_DIR)


# ---------------------------------------------------------------- definitions
func _t(name: String, desc: String, props: Dictionary, req: Array = []) -> Dictionary:
	return {"name": name, "description": desc, "inputSchema": {"type": "object", "properties": props, "required": req}}


func definitions() -> Array:
	var s := {"type": "string"}
	var rid := {"type": "string", "description": "Optional idempotency key; a repeated key replays the first result."}
	return [
		_t("project_tree", "List files under a res:// directory.", {"dir": s, "depth": {"type": "integer"}}),
		_t("read_file", "Read a project text file. Returns content and sha256 (use as expected_sha when writing).", {"path": s}, ["path"]),
		_t("write_file", "Safely write a project text file: compare-and-swap on expected_sha, validate .gd/.tscn/.tres syntax, snapshot, atomic replace, verify, refresh editor. Omit expected_sha only to create a new file.", {"path": s, "content": s, "expected_sha": s, "allow_invalid": {"type": "boolean"}, "request_id": rid}, ["path", "content"]),
		_t("delete_file", "Delete a project file (snapshotted, reversible with rollback).", {"path": s, "expected_sha": s}, ["path"]),
		_t("validate_script", "Check GDScript syntax by compiling source or an existing file.", {"path": s, "source": s}),
		_t("rollback", "Restore the file state from a transaction id returned by write_file/delete_file.", {"txn": s}, ["txn"]),
		_t("list_transactions", "List recent snapshots available for rollback.", {}),
		_t("scan_filesystem", "Force the editor to rescan/reimport project files.", {}),
		_t("get_scene_tree", "Describe the node tree of the currently edited scene.", {}),
		_t("open_scene", "Open a scene in the editor.", {"path": s}, ["path"]),
		_t("save_scene", "Save the currently edited scene.", {}),
		_t("add_node", "Add a node to the edited scene. properties values accept Godot literals as strings, e.g. \"Vector2(10,20)\".", {"parent": s, "type": s, "name": s, "properties": {"type": "object"}, "request_id": rid}, ["type", "name"]),
		_t("set_property", "Set a property on a node in the edited scene (value as Godot literal string or JSON).", {"node": s, "property": s, "value": {}}, ["node", "property", "value"]),
		_t("remove_node", "Remove a node from the edited scene.", {"node": s}, ["node"]),
		_t("move_node", "Reparent a node.", {"node": s, "new_parent": s}, ["node", "new_parent"]),
		_t("connect_signal", "Connect a signal between nodes in the edited scene.", {"from": s, "signal": s, "to": s, "method": s}, ["from", "signal", "to", "method"]),
		_t("run_project", "Run the project's main scene (or a given scene).", {"scene": s}),
		_t("stop_project", "Stop the running project.", {}),
		_t("screenshot", "Capture the editor's 2D or 3D viewport as PNG.", {"view": {"type": "string", "enum": ["2d", "3d"]}}),
		_t("get_property", "Read a property of a node in the edited scene (value as Godot literal string).", {"node": s, "property": s}, ["node", "property"]),
		_t("get_logs", "Engine log output (editor and running game): errors, warnings, prints. Use since=<next from the previous call> to read only new entries.", {"since": {"type": "integer"}, "limit": {"type": "integer"}, "level": {"type": "string", "enum": ["all", "problems"]}, "source": {"type": "string", "enum": ["all", "editor", "game"]}, "clear": {"type": "boolean"}}),
		_t("game_status", "Is the game (started by run_project) connected? Returns fps, node count, renderer.", {}),
		_t("game_tree", "Inspect the RUNNING game's scene tree with key properties (text, position, visible, size). props adds more property names.", {"depth": {"type": "integer"}, "props": {"type": "array", "items": s}}),
		_t("game_get_property", "Read one property of a node in the RUNNING game, by absolute path e.g. /root/Main/Label.", {"node": s, "property": s}, ["node", "property"]),
		_t("game_screenshot", "Screenshot of the RUNNING game window as PNG (needs a real display; not available headless).", {"max_width": {"type": "integer"}}),
		_t("self_test", "Run write/read/CAS/rollback/refresh checks on a scratch file.", {}),
		_t("status", "Plugin status and counters.", {}),
	]


# ------------------------------------------------------------------- dispatch
## Coroutine-capable: game_* tools wait for the running game's reply.
func call_tool(name: String, args: Dictionary) -> Dictionary:
	_stats.calls += 1
	var rid: String = str(args.get("request_id", ""))
	if rid != "" and _dedup.has(rid):
		return _dedup[rid]
	var res: Dictionary
	if has_method("t_" + name):
		res = await call("t_" + name, args)
	else:
		res = _err("unknown tool: " + name)
	if rid != "" and not res.get("isError", false):  # only successes are replayed; a failed call may be retried
		_dedup[rid] = res
		_dedup_order.append(rid)
		if _dedup_order.size() > DEDUP_MAX:
			_dedup.erase(_dedup_order.pop_front())
	return res


func _ok(data: Variant) -> Dictionary:
	var text: String = data if data is String else Json.stringify(data, "  ")
	return {"content": [{"type": "text", "text": text}]}


func _err(msg: String) -> Dictionary:
	_stats.rejected += 1
	return {"content": [{"type": "text", "text": msg}], "isError": true}


# ---------------------------------------------------------------- path safety
## Returns a canonical res:// path or "" when the path escapes the project.
func safe_path(p: String) -> String:
	if p == "":
		return ""
	if p.begins_with("res://"):
		p = p.substr(6)
	elif p.begins_with("/") or p.contains(":"):
		return ""
	var out: Array = []
	for part in p.replace("\\", "/").split("/"):
		if part == "" or part == ".":
			continue
		if part == "..":
			return ""
		out.append(part)
	if out.is_empty():
		return "res://"
	if out[0] == ".git" or out[0] == ".godot":
		return ""
	# Symlinks can point outside the project; refuse any path that crosses one.
	var d := DirAccess.open("res://")
	var walked := ""
	for part in out:
		walked = part if walked == "" else walked + "/" + part
		if d != null and d.is_link(walked):
			return ""
	return "res://" + "/".join(out)


func _sha(text: String) -> String:
	return text.sha256_text()


# ------------------------------------------------------------------ read tools
func t_project_tree(a: Dictionary) -> Dictionary:
	var dir := safe_path(str(a.get("dir", "res://")))
	if dir == "":
		return _err("path outside project")
	var out: Array = []
	_walk(dir, int(a.get("depth", 4)), out)
	return _ok(out)


func _walk(dir: String, depth: int, out: Array) -> void:
	if depth < 0 or out.size() > 2000:
		return
	var d := DirAccess.open(dir)
	if d == null:
		return
	for sub in d.get_directories():
		if sub.begins_with(".") :
			continue
		out.append(dir.path_join(sub) + "/")
		_walk(dir.path_join(sub), depth - 1, out)
	for f in d.get_files():
		out.append(dir.path_join(f))


func t_read_file(a: Dictionary) -> Dictionary:
	var p := safe_path(str(a.get("path", "")))
	if p == "":
		return _err("path outside project")
	if not FileAccess.file_exists(p):
		return _err("not found: " + p)
	var text := FileAccess.get_file_as_string(p)
	return _ok({"path": p, "sha256": _sha(text), "content": text})


# ------------------------------------------------------------------ validation
## Returns "" when OK, else an error description.
func validate_text(path: String, text: String) -> String:
	var ext := path.get_extension()
	if ext == "gd":
		var s := GDScript.new()
		s.source_code = text
		var e := s.reload()
		if e != OK:
			return "GDScript compile failed (error %d: %s)" % [e, error_string(e)]
	elif ext == "tscn" or ext == "tres":
		if not (text.begins_with("[gd_scene") or text.begins_with("[gd_resource")):
			return "not a valid %s header" % ext
		# Real parse: load from a scratch copy so a broken scene never reaches the project.
		var tmp := VALIDATE_DIR.path_join("probe." + ext)
		DirAccess.make_dir_recursive_absolute(VALIDATE_DIR)
		var f := FileAccess.open(tmp, FileAccess.WRITE)
		if f:
			f.store_string(text)
			f.close()
			var res = ResourceLoader.load(tmp, "", ResourceLoader.CACHE_MODE_IGNORE)
			DirAccess.remove_absolute(tmp)
			if res == null:
				return "%s failed to load (parse error)" % ext
	elif ext == "json":
		if JSON.parse_string(text) == null and text.strip_edges() != "null":
			return "invalid JSON"
	return ""


func t_validate_script(a: Dictionary) -> Dictionary:
	var src := ""
	var path := "x.gd"
	if a.has("source"):
		src = str(a.source)
	else:
		path = safe_path(str(a.get("path", "")))
		if path == "" or not FileAccess.file_exists(path):
			return _err("bad path")
		src = FileAccess.get_file_as_string(path)
	var e := validate_text(path, src)
	return _ok({"valid": e == "", "error": e})


# ---------------------------------------------------------------- write path
func _snapshot(path: String) -> String:
	_txn_seq += 1
	var id := "t%d_%d" % [Time.get_unix_time_from_system(), _txn_seq]
	var snap := {"id": id, "path": path, "existed": FileAccess.file_exists(path), "file": "", "sha": ""}
	if snap.existed:
		var txt := FileAccess.get_file_as_string(path)
		snap.sha = _sha(txt)
		snap.file = SNAP_DIR.path_join(id + ".bak")
		var f := FileAccess.open(snap.file, FileAccess.WRITE)
		if f == null:
			return ""
		f.store_string(txt)
		f.close()
	_snapshots.append(snap)
	while _snapshots.size() > MAX_SNAPSHOTS:
		var old: Dictionary = _snapshots.pop_front()
		if old.file != "":
			DirAccess.remove_absolute(old.file)
	return id


func _atomic_write(path: String, text: String) -> bool:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var tmp := path + ".cl_tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(text)
	f.close()
	var d := DirAccess.open(path.get_base_dir())
	if d == null:
		return false
	if FileAccess.file_exists(path):
		# rename_absolute overwrites on POSIX; keep tmp cleanup on failure.
		pass
	var e := DirAccess.rename_absolute(tmp, path)
	if e != OK:
		DirAccess.remove_absolute(tmp)
		return false
	return true


func t_write_file(a: Dictionary) -> Dictionary:
	var p := safe_path(str(a.get("path", "")))
	if p == "" or p == "res://" or p.ends_with("/"):
		return _err("path outside project or not a file")
	if p.ends_with(".cl_tmp"):
		return _err("reserved extension")
	var content := str(a.get("content", ""))
	var exists := FileAccess.file_exists(p)
	if exists:
		var cur := FileAccess.get_file_as_string(p)
		if not a.has("expected_sha"):
			return _err("file exists; read_file it first and pass expected_sha")
		if str(a.expected_sha) != _sha(cur):
			return _err("CONFLICT: %s changed since you read it (now sha256 %s). Re-read, re-apply your change, retry." % [p, _sha(cur)])
	elif a.has("expected_sha") and str(a.expected_sha) != "":
		return _err("CONFLICT: %s no longer exists." % p)
	if not bool(a.get("allow_invalid", false)):
		var ve := validate_text(p, content)
		if ve != "":
			return _err("REJECTED, file not written: " + ve)
	var txn := _snapshot(p)
	if txn == "":
		return _err("could not create snapshot; refusing to write")
	if not _atomic_write(p, content):
		return _err("write failed (txn %s untouched)" % txn)
	var back := FileAccess.get_file_as_string(p)
	if _sha(back) != _sha(content):
		t_rollback({"txn": txn})
		return _err("verification failed; rolled back")
	_stats.writes += 1
	_refresh(p, content)
	return _ok({"path": p, "txn": txn, "sha256": _sha(content), "created": not exists})


func t_delete_file(a: Dictionary) -> Dictionary:
	var p := safe_path(str(a.get("path", "")))
	if p == "" or not FileAccess.file_exists(p):
		return _err("bad path")
	if a.has("expected_sha") and str(a.expected_sha) != _sha(FileAccess.get_file_as_string(p)):
		return _err("CONFLICT: file changed")
	var txn := _snapshot(p)
	DirAccess.remove_absolute(p)
	_refresh(p, "")
	return _ok({"path": p, "txn": txn})


func t_rollback(a: Dictionary) -> Dictionary:
	for i in range(_snapshots.size() - 1, -1, -1):
		var s: Dictionary = _snapshots[i]
		if s.id == str(a.get("txn", "")):
			if s.existed:
				var txt := FileAccess.get_file_as_string(s.file)
				_atomic_write(s.path, txt)
				_refresh(s.path, txt)
			else:
				DirAccess.remove_absolute(s.path)
				_refresh(s.path, "")
			return _ok({"restored": s.path})
	return _err("unknown or expired txn")


func t_list_transactions(_a: Dictionary) -> Dictionary:
	var out: Array = []
	for s in _snapshots:
		out.append({"txn": s.id, "path": s.path, "existed": s.existed})
	return _ok(out)


# -------------------------------------------------------------------- refresh
## Make the open editor show the new content without user action.
func _refresh(path: String, content: String) -> void:
	var ei := EditorInterface
	var fs := ei.get_resource_filesystem()
	if fs:
		if FileAccess.file_exists(path):
			fs.update_file(path)
		fs.scan()
	var ext := path.get_extension()
	if ext == "gd":
		_refresh_open_script(path, content)
	elif ext == "tscn":
		if path in ei.get_open_scenes():
			ei.reload_scene_from_path(path)
	elif ext == "tres" or ext == "res":
		ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE)


func _refresh_open_script(path: String, content: String) -> void:
	var se := EditorInterface.get_script_editor()
	for ed in se.get_open_script_editors():
		var res: Resource = ed.get_edited_resource()
		if res and res.resource_path == path:
			var base = ed.get_base_editor()
			if base is CodeEdit and FileAccess.file_exists(path):
				var line: int = base.get_caret_line()
				var col: int = base.get_caret_column()
				base.text = content
				base.set_caret_line(min(line, base.get_line_count() - 1))
				base.set_caret_column(col)
				base.tag_saved_version()
	if FileAccess.file_exists(path):
		var sc = ResourceLoader.load(path, "GDScript", ResourceLoader.CACHE_MODE_REPLACE)
		if sc is GDScript:
			sc.reload(true)


func t_scan_filesystem(_a: Dictionary) -> Dictionary:
	EditorInterface.get_resource_filesystem().scan()
	return _ok("scan requested")


# ---------------------------------------------------------------- scene tools
func _root() -> Node:
	return EditorInterface.get_edited_scene_root()


func _find(path: String) -> Node:
	var r := _root()
	if r == null:
		return null
	if path == "" or path == "." or path == r.name:
		return r
	return r.get_node_or_null(NodePath(path))


func _describe(n: Node, root: Node, out: Array, depth: int) -> void:
	out.append({"path": str(root.get_path_to(n)), "type": n.get_class(), "script": (n.get_script().resource_path if n.get_script() else "")})
	if depth > 0:
		for c in n.get_children():
			_describe(c, root, out, depth - 1)


func t_get_scene_tree(_a: Dictionary) -> Dictionary:
	var r := _root()
	if r == null:
		return _err("no scene is open")
	var out: Array = []
	_describe(r, r, out, 12)
	return _ok({"scene": r.scene_file_path, "nodes": out})


func t_open_scene(a: Dictionary) -> Dictionary:
	var p := safe_path(str(a.get("path", "")))
	if p == "" or not FileAccess.file_exists(p):
		return _err("bad path")
	EditorInterface.open_scene_from_path(p)
	return _ok("opened " + p)


func t_save_scene(_a: Dictionary) -> Dictionary:
	if _root() == null:
		return _err("no scene is open")
	var e := EditorInterface.save_scene()
	return _ok("saved" if e == OK else "save error %d" % e)


func _val(v: Variant) -> Variant:
	if v is String:
		var parsed = str_to_var(v)
		if parsed != null or v == "null":
			return parsed
	return v


func t_add_node(a: Dictionary) -> Dictionary:
	var r := _root()
	if r == null:
		return _err("no scene is open")
	var type := str(a.get("type", ""))
	if not ClassDB.class_exists(type) or not ClassDB.can_instantiate(type):
		return _err("cannot instantiate " + type)
	var parent := _find(str(a.get("parent", "")))
	if parent == null:
		return _err("parent not found")
	var n: Node = ClassDB.instantiate(type)
	n.name = str(a.name)
	var props = a.get("properties", {})
	if props is Dictionary:
		for k in props:
			n.set(k, _val(props[k]))
	parent.add_child(n, true)
	n.owner = r
	EditorInterface.mark_scene_as_unsaved()
	return _ok({"path": str(r.get_path_to(n))})


func t_set_property(a: Dictionary) -> Dictionary:
	var n := _find(str(a.get("node", "")))
	if n == null:
		return _err("node not found")
	n.set(str(a.property), _val(a.value))
	EditorInterface.mark_scene_as_unsaved()
	return _ok({"value": var_to_str(n.get(str(a.property)))})


func t_get_property(a: Dictionary) -> Dictionary:
	var n := _find(str(a.get("node", "")))
	if n == null:
		return _err("node not found")
	return _ok({"value": var_to_str(n.get(str(a.get("property", ""))))})


func t_remove_node(a: Dictionary) -> Dictionary:
	var n := _find(str(a.get("node", "")))
	if n == null or n == _root():
		return _err("node not found or is root")
	n.get_parent().remove_child(n)
	n.queue_free()
	EditorInterface.mark_scene_as_unsaved()
	return _ok("removed")


func t_move_node(a: Dictionary) -> Dictionary:
	var n := _find(str(a.get("node", "")))
	var np := _find(str(a.get("new_parent", "")))
	if n == null or np == null or n == _root():
		return _err("node not found")
	var r := _root()
	n.reparent(np, true)
	n.owner = r
	EditorInterface.mark_scene_as_unsaved()
	return _ok({"path": str(r.get_path_to(n))})


func t_connect_signal(a: Dictionary) -> Dictionary:
	var f := _find(str(a.get("from", "")))
	var t := _find(str(a.get("to", "")))
	if f == null or t == null:
		return _err("node not found")
	var e := f.connect(str(a.signal), Callable(t, str(a.method)), Object.CONNECT_PERSIST)
	EditorInterface.mark_scene_as_unsaved()
	return _ok("connected" if e == OK else "error %d" % e)


# ------------------------------------------------------------- run / observe
func t_run_project(a: Dictionary) -> Dictionary:
	if a.has("scene"):
		var p := safe_path(str(a.scene))
		if p == "":
			return _err("bad scene path")
		EditorInterface.play_custom_scene(p)
	else:
		EditorInterface.play_main_scene()
	return _ok("running")


func t_stop_project(_a: Dictionary) -> Dictionary:
	EditorInterface.stop_playing_scene()
	return _ok("stopped")


func t_screenshot(a: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless":
		return _err("no renderer: the editor is running headless, so there is nothing to capture")
	var vp: SubViewport = EditorInterface.get_editor_viewport_3d(0) if a.get("view", "2d") == "3d" else EditorInterface.get_editor_viewport_2d()
	var img := vp.get_texture().get_image()
	if img == null:
		return _err("no image")
	var b64 := Marshalls.raw_to_base64(img.save_png_to_buffer())
	return {"content": [{"type": "image", "data": b64, "mimeType": "image/png"}]}


# ----------------------------------------------------------------------- logs
const LOG_MAX := 1000
var _log_mutex := Mutex.new()
var _logs: Array = []  # {seq, t, source, kind, msg, where}
var _log_seq := 0
var logger_active := false  # true when the engine Logger (4.5+) is feeding add_log


## Thread-safe: the engine Logger may call this from any thread.
func add_log(source: String, kind: String, msg: String, where: String = "") -> void:
	_log_mutex.lock()
	_log_seq += 1
	_logs.append({"seq": _log_seq, "t": Time.get_unix_time_from_system(), "source": source, "kind": kind, "msg": msg.left(2000), "where": where})
	if _logs.size() > LOG_MAX:
		_logs.pop_front()
	_log_mutex.unlock()


func push_log(kind: String, msg: String) -> void:  # kept for callers on Godot < 4.5
	add_log("editor", kind, msg)


func t_get_logs(a: Dictionary) -> Dictionary:
	var since := int(a.get("since", 0))
	var limit := clampi(int(a.get("limit", 100)), 1, 500)
	var level := str(a.get("level", "all"))  # all | problems
	var source := str(a.get("source", "all"))  # all | editor | game
	var out: Array = []
	_log_mutex.lock()
	for e in _logs:
		if e.seq <= since:
			continue
		if source != "all" and e.source != source:
			continue
		if level == "problems" and e.kind == "info":
			continue
		out.append(e)
	var last := _log_seq
	if bool(a.get("clear", false)):
		_logs.clear()
	_log_mutex.unlock()
	if out.size() > limit:
		out = out.slice(out.size() - limit)
	return _ok({
		"capture": "engine Logger" if logger_active else "unavailable (needs Godot 4.5+; only game output forwarded by the runtime probe is captured)",
		"next": last,
		"entries": out,
	})


# ----------------------------------------------------------- running game (probe)
func t_game_status(_a: Dictionary) -> Dictionary:
	var dbg = plugin.get("debugger")
	var running: bool = dbg != null and dbg.is_game_connected()
	var out := {"running": running, "playing_in_editor": EditorInterface.is_playing_scene()}
	if running:
		out["stats"] = await dbg.request("stats")
	return _ok(out)


func t_game_tree(a: Dictionary) -> Dictionary:
	var dbg = plugin.get("debugger")
	if dbg == null:
		return _err("runtime probe unavailable")
	var r: Dictionary = await dbg.request("tree", {"depth": int(a.get("depth", 6)), "props": a.get("props", [])})
	return _err(r.error) if r.has("error") else _ok(r)


func t_game_get_property(a: Dictionary) -> Dictionary:
	var dbg = plugin.get("debugger")
	if dbg == null:
		return _err("runtime probe unavailable")
	var r: Dictionary = await dbg.request("get", {"node": str(a.get("node", "")), "property": str(a.get("property", ""))})
	return _err(r.error) if r.has("error") else _ok(r)


func t_game_screenshot(a: Dictionary) -> Dictionary:
	var dbg = plugin.get("debugger")
	if dbg == null:
		return _err("runtime probe unavailable")
	var r: Dictionary = await dbg.request("screenshot", {"max_width": int(a.get("max_width", 960))}, 15.0)
	if r.has("error"):
		return _err(r.error)
	return {"content": [{"type": "image", "data": Marshalls.raw_to_base64(r.png), "mimeType": "image/png"}]}


# ------------------------------------------------------------------ self test
func t_self_test(_a: Dictionary) -> Dictionary:
	var rep: Array = []
	var p := "res://.claude_live_selftest.txt"
	var w1 = t_write_file({"path": p, "content": "one"})
	rep.append({"create": not w1.get("isError", false)})
	var sha := _sha("one")
	var w2 = t_write_file({"path": p, "content": "two", "expected_sha": sha})
	rep.append({"cas_update": not w2.get("isError", false)})
	var w3 = t_write_file({"path": p, "content": "three", "expected_sha": sha})
	rep.append({"stale_write_rejected": w3.get("isError", false)})
	var bad = t_write_file({"path": "res://.claude_live_bad.gd", "content": "func ((("})
	rep.append({"invalid_gd_rejected": bad.get("isError", false)})
	var esc = t_write_file({"path": "res://../evil.txt", "content": "x"})
	rep.append({"path_traversal_blocked": esc.get("isError", false)})
	var txn: String = JSON.parse_string(w2.content[0].text).txn if not w2.get("isError", false) else ""
	t_rollback({"txn": txn})
	rep.append({"rollback_restored": FileAccess.get_file_as_string(p) == "one"})
	t_delete_file({"path": p})
	rep.append({"cleanup": not FileAccess.file_exists(p)})
	var ok := true
	for r in rep:
		for k in r:
			ok = ok and r[k]
	return _ok({"all_passed": ok, "checks": rep, "godot": Engine.get_version_info().string})


func t_status(_a: Dictionary) -> Dictionary:
	return _ok({"godot": Engine.get_version_info().string, "platform": OS.get_name(), "project": ProjectSettings.globalize_path("res://"), "stats": _stats, "logger": logger_active, "relay": (plugin.bridge.state if plugin.get("bridge") else "none"), "snapshots": _snapshots.size(), "scene": (_root().scene_file_path if _root() else "")})
