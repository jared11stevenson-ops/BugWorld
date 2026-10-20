# Interactive duel against an NPC using the COMPILED combat rules (the same kernel.fight_round the lab evolved).
# Records human feedback (rating 1-5) to user://human_feedback.jsonl so future experiments can use real player data.
extends PanelContainer

const K = preload("res://ghost/kernel.gd")
const ActionBar = preload("res://generated/action_bar.tscn")

signal finished

var s: Dictionary
var c: Dictionary
var rules_name: String
var npc_id: int
var player: Dictionary
var foe: Dictionary
var rng_state: Dictionary
var foe_hist: Dictionary
var rounds := 0
var info: RichTextLabel
var bar: Control
var rate_box: HBoxContainer
var result := ""


func setup(world: Dictionary, id: int, rname: String) -> void:
	s = world
	c = world["rules"]["combat"]
	npc_id = id
	rules_name = rname
	foe = world["npcs"][id].duplicate()
	player = {"maxhp": 100, "hp": 100, "atk": 20, "def": 5, "potions": c["start_potions"]}
	K.reset_fighter(player)
	K.reset_fighter(foe)
	foe["hp"] = foe["maxhp"]
	rng_state = {"rng": K.seed_state(int(world["seed"]) * 31 + id)}
	foe_hist = K.new_hist()
	custom_minimum_size = Vector2(640, 380)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.09, 0.12, 0.97)
	sb.border_color = Color(0.5, 0.7, 1.0)
	sb.set_border_width_all(2)
	sb.set_content_margin_all(12)
	add_theme_stylebox_override("panel", sb)
	var v := VBoxContainer.new()
	add_child(v)
	info = RichTextLabel.new()
	info.size_flags_vertical = Control.SIZE_EXPAND_FILL
	info.scroll_following = true
	info.bbcode_enabled = true
	v.add_child(info)
	bar = ActionBar.instantiate()
	bar.action_selected.connect(_on_action)
	v.add_child(bar)
	rate_box = HBoxContainer.new()
	rate_box.visible = false
	var l := Label.new()
	l.text = "How fun was that fight? "
	rate_box.add_child(l)
	for r in range(1, 6):
		var b := Button.new()
		b.text = str(r)
		b.pressed.connect(func(): _rate(r))
		rate_box.add_child(b)
	v.add_child(rate_box)
	info.append_text("[b]Duel vs %s#%d[/b] (policy: %s, atk %d, def %d, hp %d)\nYou: hp 100 atk 20 def 5, %d potions. Hover buttons for the rules.\n" % [K.npc_name(foe), id, K.POLICY_NAMES[foe["policy"]], foe["atk"], foe["def"], foe["maxhp"], player["potions"]])
	_status()


func _status() -> void:
	info.append_text("\n[color=lightgreen]You %d/%d hp[/color]  [color=salmon]Foe %d/%d hp[/color]  potions %d\n" % [player["hp"], player["maxhp"], foe["hp"], foe["maxhp"], player["potions"]])
	bar.set_enabled(true, player["potions"] > 0)


func _on_action(act: int) -> void:
	var fa := K.choose(foe["policy"], foe, player, foe_hist, c, rng_state)
	var r := K.fight_round(c, player, foe, act, fa, rng_state)
	K.observe(foe_hist, r[0])
	rounds += 1
	info.append_text("Round %d: you [b]%s[/b], foe [b]%s[/b]\n" % [rounds, K.ACTION_NAMES[r[0]], K.ACTION_NAMES[r[1]]])
	var pd: bool = player["hp"] <= 0
	var fd: bool = foe["hp"] <= 0
	if pd or fd or rounds >= c["round_cap"]:
		result = "draw" if (pd and fd) or (not pd and not fd) else ("win" if fd else "loss")
		info.append_text("\n[b]Result: %s after %d rounds[/b]\n" % [result, rounds])
		bar.set_enabled(false)
		rate_box.visible = true
	else:
		_status()


func _rate(r: int) -> void:
	var rec := {"ruleset": rules_name, "seed": s["seed"], "tick": s["tick"], "npc_policy": K.POLICY_NAMES[foe["policy"]],
		"result": result, "rounds": rounds, "rating": r, "rules_digest": K.fnv_str(JSON.stringify(c, "", true))}
	var path := "user://human_feedback.jsonl"
	var f := FileAccess.open(path, FileAccess.READ_WRITE) if FileAccess.file_exists(path) else FileAccess.open(path, FileAccess.WRITE)
	f.seek_end()
	f.store_line(JSON.stringify(rec))
	f.close()
	finished.emit()
