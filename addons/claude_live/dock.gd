@tool
extends VBoxContainer
## "Claude Live" dock: status + Load connection (imports {"url","token"} JSON into user://, outside the project).

var bridge
var _status := Label.new()
var _dialog := FileDialog.new()


func setup(p_bridge) -> void:
	bridge = p_bridge
	name = "Claude Live"
	add_child(_status)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var b := Button.new()
	b.text = "Load connection"
	b.pressed.connect(func(): _dialog.popup_centered_ratio(0.8))
	add_child(b)
	_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_dialog.use_native_dialog = true  # system picker (Android SAF) where supported
	_dialog.filters = PackedStringArray(["*.json ; Connection file"])
	_dialog.file_selected.connect(_on_file)
	add_child(_dialog)
	var t := Timer.new()
	t.wait_time = 1.0
	t.autostart = true
	t.timeout.connect(_refresh)
	add_child(t)
	_refresh()


func _on_file(path: String) -> void:
	var cfg = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not (cfg is Dictionary) or str(cfg.get("url", "")) == "" or str(cfg.get("token", "")).length() < 32:
		_status.text = "That file is not a valid connection (needs url and token)."
		return
	var f := FileAccess.open(bridge.CFG, FileAccess.WRITE)
	if f == null:
		_status.text = "Could not store the connection."
		return
	f.store_string(JSON.stringify({"url": cfg.url, "token": cfg.token}))
	f.close()
	bridge.reload_config()
	_refresh()


func _refresh() -> void:
	match bridge.state:
		"disabled": _status.text = "Not connected: tap Load connection and pick your connection file."
		"connected": _status.text = "Connected. Prompt Claude, then watch this editor."
		"connecting": _status.text = "Connecting..."
		_: _status.text = "Connection interrupted; reconnecting."
