@tool
extends EditorPlugin
## Claude Live: hosts an MCP (Streamable HTTP) server inside the editor.

const McpServer := preload("res://addons/claude_live/mcp_server.gd")
const Tools := preload("res://addons/claude_live/tools.gd")
const Dock := preload("res://addons/claude_live/dock.gd")
const Bridge := preload("res://addons/claude_live/bridge_client.gd")
const DebuggerPlug := preload("res://addons/claude_live/debugger.gd")
const Compat := preload("res://addons/claude_live/compat.gd")
const AUTOLOAD := "ClaudeLiveRuntime"

var server
var tools
var bridge
var dock
var debugger
var logger


func _enter_tree() -> void:
	tools = Tools.new(self)
	# Engine log capture needs the Logger class (Godot 4.5+); compat.gd returns null on older engines.
	logger = Compat.make_logger("editor", tools.add_log)
	tools.logger_active = logger != null
	debugger = DebuggerPlug.new()
	debugger.tools = tools
	add_debugger_plugin(debugger)
	server = McpServer.new(tools)
	var err: int = server.start()
	if err != OK:
		push_error("[claude_live] could not listen on 127.0.0.1:%d (error %d)" % [server.port, err])
	else:
		print("[claude_live] MCP ready at http://127.0.0.1:%d/mcp  token file: %s" % [server.port, server.token_path()])
	bridge = Bridge.new(server)
	# Automation hook (headless / Termux scripts): same import the dock's "Load connection" uses.
	var imp := OS.get_environment("CLAUDE_LIVE_IMPORT")
	if imp != "":
		var ierr: String = bridge.import_connection(imp)
		if ierr != "":
			push_warning("[claude_live] CLAUDE_LIVE_IMPORT: " + ierr)
	dock = Dock.new()
	dock.setup(bridge)
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, dock)
	set_process(true)


## Called only when the user enables/disables the plugin (not on every editor start).
func _enable_plugin() -> void:
	add_autoload_singleton(AUTOLOAD, "res://addons/claude_live/runtime.gd")


func _disable_plugin() -> void:
	remove_autoload_singleton(AUTOLOAD)


func _exit_tree() -> void:
	if debugger:
		remove_debugger_plugin(debugger)
	Compat.remove_logger(logger)
	if dock:
		remove_control_from_docks(dock)
		dock.queue_free()
	if bridge:
		bridge.stop()
	if server:
		server.stop()


func _process(_delta: float) -> void:
	if server:
		server.poll()
	if bridge:
		bridge.poll()
