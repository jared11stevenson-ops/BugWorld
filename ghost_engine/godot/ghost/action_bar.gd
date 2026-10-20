extends HBoxContainer
# Script for the compiler-generated generated/action_bar.tscn: one button per combat action.
signal action_selected(action: int)


func _ready() -> void:
	for ch in get_children():
		if ch is Button:
			var b: Button = ch
			b.pressed.connect(func(): action_selected.emit(int(b.get_meta("action"))))


func set_enabled(on: bool, can_heal := true) -> void:
	for ch in get_children():
		if ch is Button:
			ch.disabled = not on
	if has_node("Heal"):
		get_node("Heal").disabled = (not on) or (not can_heal)
