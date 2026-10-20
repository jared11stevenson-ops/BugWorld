# Generic playable arena for ANY compiled concept: buttons, tooltips, state and opponent all come from the spec data.
# Records a replayable human session (seed + actions) so the Python twin can re-simulate it and verify the outcome.
extends PanelContainer

const C = preload("res://ghost/concept.gd")
signal finished

var concept: Dictionary
var spec: Dictionary
var m: Dictionary
var h_opp: Dictionary
var opp_pid := 8
var match_seed := 1
var human_actions: Array = []
var buttons: Array = []
var state_label: RichTextLabel
var log_view: RichTextLabel
var rate_box: HBoxContainer
var last_record: Dictionary = {}


func setup(c: Dictionary, seed_in: int, opp := 8) -> void:
	concept = c
	spec = c["spec"]
	match_seed = seed_in
	opp_pid = opp
	m = C.new_match(spec, seed_in)
	h_opp = C.new_hist(spec["actions"].size())
	custom_minimum_size = Vector2(760, 480)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.09, 0.12, 0.97)
	sb.border_color = Color(0.5, 0.7, 1.0)
	sb.set_border_width_all(2)
	sb.set_content_margin_all(12)
	add_theme_stylebox_override("panel", sb)
	var v := VBoxContainer.new()
	add_child(v)
	var title := Label.new()
	var ev: Dictionary = c.get("evidence", {})
	title.text = "%s    [%s]" % [spec["name"], ev.get("summary", "no evidence attached")]
	title.add_theme_color_override("font_color", Color(0.7, 0.9, 1.0))
	v.add_child(title)
	var rules := RichTextLabel.new()
	rules.custom_minimum_size = Vector2(0, 110)
	rules.bbcode_enabled = true
	rules.text = c["text"]
	v.add_child(rules)
	state_label = RichTextLabel.new()
	state_label.custom_minimum_size = Vector2(0, 44)
	state_label.bbcode_enabled = true
	v.add_child(state_label)
	var bar := HFlowContainer.new()
	v.add_child(bar)
	for i in spec["actions"].size():
		var b := Button.new()
		b.text = spec["actions"][i]["name"]
		b.tooltip_text = C.action_tooltip(spec, i)
		b.pressed.connect(func(): _play(i))
		bar.add_child(b)
		buttons.append(b)
	log_view = RichTextLabel.new()
	log_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	log_view.scroll_following = true
	log_view.bbcode_enabled = true
	v.add_child(log_view)
	rate_box = HBoxContainer.new()
	rate_box.visible = false
	var l := Label.new()
	l.text = "How fun was that match? "
	rate_box.add_child(l)
	for r in range(1, 6):
		var rb := Button.new()
		rb.text = str(r)
		rb.pressed.connect(func(): rate(r))
		rate_box.add_child(rb)
	v.add_child(rate_box)
	_refresh()


func _vars_line(who: int) -> String:
	var parts := []
	for vd in spec["vars"]:
		parts.append("%s %d" % [vd[0], m["p"][who][vd[0]]])
	return ", ".join(parts)


func _refresh() -> void:
	state_label.text = "[color=lightgreen]You: %s[/color]\n[color=salmon]Opponent (%s): %s[/color]   round %d" % [_vars_line(0), _opp_name(), _vars_line(1), m["round"]]
	for i in buttons.size():
		buttons[i].disabled = m["done"] != 0 or not C.is_legal(spec, m, 0, i)


func _opp_name() -> String:
	return {8: "adaptive", 7: "random", 6: "cycle", 9: "counter", 10: "mirror", 11: "greedy"}.get(opp_pid, "agent")


func _play(i: int) -> void:
	if m["done"] != 0:
		return
	var a1 := C.choose(spec, opp_pid, m, 1, h_opp)
	var s := C.step(spec, m, i, a1)
	C.observe(h_opp, s[0])
	human_actions.append(s[0])
	log_view.append_text("Round %d: you [b]%s[/b], opponent [b]%s[/b]\n" % [m["round"], spec["actions"][s[0]]["name"], spec["actions"][s[1]]["name"]])
	if m["done"] != 0:
		var res := "draw" if m["winner"] == -1 else ("[color=lightgreen]YOU WIN[/color]" if m["winner"] == 0 else "[color=salmon]YOU LOSE[/color]")
		log_view.append_text("\n[b]%s[/b] after %d rounds%s\n" % [res, m["round"], " (time limit)" if m["timeout"] != 0 else ""])
		rate_box.visible = true
		last_record = {"kind": "concept", "concept": spec["id"], "seed": match_seed, "opp": opp_pid, "actions": human_actions.duplicate(),
			"winner": m["winner"], "rounds": m["round"], "digest": C.match_digest(spec, m)}
	_refresh()


func rate(r: int) -> void:
	last_record["rating"] = r
	var path := "user://human_feedback.jsonl"
	var f := FileAccess.open(path, FileAccess.READ_WRITE) if FileAccess.file_exists(path) else FileAccess.open(path, FileAccess.WRITE)
	f.seek_end()
	f.store_line(JSON.stringify(last_record))
	f.close()
	finished.emit()
