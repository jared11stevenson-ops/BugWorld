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
	var err: String = bridge.import_connection(path)
	_status.text = err if err != "" else "Connection loaded."
	_refresh_soon()


func _refresh_soon() -> void:
	await get_tree().create_timer(0.5).timeout
	_refresh()


func _refresh() -> void:
	match bridge.state:
		"disabled": _status.text = "Not connected: tap Load connection and pick your connection file."
		"connected": _status.text = "Connected. Prompt Claude, then watch this editor."
		"connecting": _status.text = "Connecting..."
		_: _status.text = "Connection interrupted; reconnecting."
