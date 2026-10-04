@tool
extends RefCounted
## Version-dependent pieces, kept out of the normal parse path so Godot 4.4 still loads the plugin.

const LOG_CAPTURE_SRC := "res://addons/claude_live/log_capture.gd.txt"


## Returns a Logger subclass instance (Godot 4.5+) with .source and .sink set, or null on older engines.
static func make_logger(source: String, sink: Callable):
	if not (ClassDB.class_exists("Logger") and OS.has_method("add_logger")):
		return null
	var s := GDScript.new()
	s.source_code = FileAccess.get_file_as_string(LOG_CAPTURE_SRC)
	if s.reload() != OK:
		return null
	var l = s.new()
	l.source = source
	l.sink = sink
	OS.call("add_logger", l)
	return l


static func remove_logger(l) -> void:
	if l != null and OS.has_method("remove_logger"):
		OS.call("remove_logger", l)
