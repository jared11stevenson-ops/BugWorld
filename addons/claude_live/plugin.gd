@tool
extends EditorPlugin
## Claude Live: hosts an MCP (Streamable HTTP) server inside the editor.

const McpServer := preload("res://addons/claude_live/mcp_server.gd")
const Tools := preload("res://addons/claude_live/tools.gd")

var server
var tools


func _enter_tree() -> void:
	tools = Tools.new(self)
	server = McpServer.new(tools)
	var err: int = server.start()
	if err != OK:
		push_error("[claude_live] could not listen on 127.0.0.1:%d (error %d)" % [server.port, err])
	else:
		print("[claude_live] MCP ready at http://127.0.0.1:%d/mcp  token file: %s" % [server.port, server.token_path()])
	set_process(true)


func _exit_tree() -> void:
	if server:
		server.stop()


func _process(_delta: float) -> void:
	if server:
		server.poll()
