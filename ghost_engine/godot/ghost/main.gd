# Ghost Engine - playable viewer for the living twin: the same kernel the lab simulates, running in Godot.
# Step time, rewind, branch timelines, inject interventions, read NPC histories, duel an NPC with the compiled rules.
extends Control

const K = preload("res://ghost/kernel.gd")
const TL = preload("res://ghost/timeline.gd")
const RS = preload("res://generated/rulesets.gd")
const DuelArena = preload("res://ghost/duel_arena.gd")

var timelines: Array = []
var cur := 0
var rules_name := "v1_evolved"
var seed_box: SpinBox
var rules_opt: OptionButton
var status: Label
var log_view: RichTextLabel
var npc_list: ItemList
var duel: Control
var overlay: Control
var shown_events := 0


func _ready() -> void:
	_build_ui()
	new_world(1, rules_name)


func _btn(text: String, cb: Callable, parent: Node) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(cb)
	parent.add_child(b)
	return b


func _build_ui() -> void:
	var root := VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(root)
	var top := HBoxContainer.new()
	root.add_child(top)
	var l := Label.new()
	l.text = "GHOST ENGINE   seed"
	top.add_child(l)
	seed_box = SpinBox.new()
	seed_box.min_value = 1
	seed_box.max_value = 999999
	seed_box.value = 1
	top.add_child(seed_box)
	rules_opt = OptionButton.new()
	rules_opt.add_item("v1_evolved")
	rules_opt.add_item("v0_baseline")
	top.add_child(rules_opt)
	_btn("New world", func(): new_world(int(seed_box.value), rules_opt.get_item_text(rules_opt.selected)), top)
	status = Label.new()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.custom_minimum_size = Vector2(0, 40)
	status.add_theme_color_override("font_color", Color(0.7, 0.9, 1.0))
	root.add_child(status)
	var mid := HSplitContainer.new()
	mid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(mid)
	npc_list = ItemList.new()
	npc_list.custom_minimum_size = Vector2(300, 0)
	npc_list.item_selected.connect(func(_i): _show_history())
	mid.add_child(npc_list)
	log_view = RichTextLabel.new()
	log_view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	log_view.scroll_following = true
	log_view.bbcode_enabled = true
	mid.add_child(log_view)
	var bar := HFlowContainer.new()
	root.add_child(bar)
	for n in [1, 10, 50]:
		_btn("Step %d" % n, func(): step(n), bar)
	_btn("Rewind 25", func(): rewind(25), bar)
	_btn("Fork timeline", fork, bar)
	_btn("Next timeline", func(): switch_timeline((cur + 1) % timelines.size()), bar)
	_btn("Kill deadliest", func(): intervene_deadliest(), bar)
	_btn("Windfall (richest +500g)", func(): intervene("give_gold"), bar)
	_btn("Force Crown-Guild war", func(): intervene("set_rel"), bar)
	_btn("Duel selected NPC", start_duel, bar)


func new_world(seed_in: int, rname: String) -> void:
	rules_name = rname
	timelines = [TL.new(K.new_world(seed_in, RS.get_rules(rname)))]
	cur = 0
	log_view.clear()
	_say("[b]New world[/b] seed=%d rules=%s" % [seed_in, rname])
	shown_events = 0
	_refresh()


func T():
	return timelines[cur]


func _say(text: String) -> void:
	log_view.append_text(text + "\n")


func step(n: int) -> void:
	T().step(n)
	_flush_events()
	_refresh()


func rewind(n: int) -> void:
	var t := maxi(0, T().tick() - n)
	T().rewind(t)
	shown_events = T().s["events"].size()
	_say("[color=yellow]-- rewound to tick %d (history after this point is replayed deterministically on step) --[/color]" % t)
	_refresh()


func fork() -> void:
	var b = T().fork()
	timelines.append(b)
	switch_timeline(timelines.size() - 1)
	_say("[color=cyan]-- branched timeline %s at tick %d --[/color]" % [b.tid, b.tick()])


func switch_timeline(i: int) -> void:
	cur = i
	log_view.clear()
	_say("[b]timeline %s[/b] (%d/%d) tick %d" % [T().tid, cur + 1, timelines.size(), T().tick()])
	shown_events = maxi(0, T().s["events"].size() - 25)
	_flush_events()
	_refresh()


func _deadliest() -> int:
	var best := -1
	for n in T().s["npcs"]:
		if n["alive"] and (best < 0 or n["kills"] > T().s["npcs"][best]["kills"]):
			best = n["id"]
	return best


func intervene_deadliest() -> void:
	intervene("kill")


func intervene(kind: String) -> void:
	var s: Dictionary = T().s
	match kind:
		"kill":
			var d := _deadliest()
			if d >= 0:
				T().intervene("kill", [d])
		"give_gold":
			var rich := -1
			for n in s["npcs"]:
				if n["alive"] and (rich < 0 or n["gold"] < s["npcs"][rich]["gold"]):
					rich = n["id"]
			if rich >= 0:
				T().intervene("give_gold", [rich, 500])
		"set_rel":
			T().intervene("set_rel", [0, 1, -90])
	_flush_events()
	_refresh()


func _flush_events() -> void:
	var s: Dictionary = T().s
	var evs: Array = s["events"]
	var start := maxi(shown_events, evs.size() - 40)
	for i in range(start, evs.size()):
		var ev: Array = evs[i]
		if ev[2] in [K.EV_FIGHT, K.EV_KILL, K.EV_WAR, K.EV_PEACE, K.EV_SPAWN, K.EV_INTERVENE]:
			var line: String = K.describe(s, ev)
			if ev[2] == K.EV_KILL or ev[2] == K.EV_WAR:
				line = "[color=salmon]%s[/color]" % line
			_say(line)
	shown_events = evs.size()


func _refresh() -> void:
	var s: Dictionary = T().s
	var alive := 0
	var sel := npc_list.get_selected_items()
	npc_list.clear()
	for n in s["npcs"]:
		if n["alive"]:
			alive += 1
			npc_list.add_item("#%d %s [%s] %s hp%d/%d %dg" % [n["id"], K.npc_name(n), K.FACTION_NAMES[n["faction"]], K.TOWN_NAMES[n["loc"]], n["hp"], n["maxhp"], n["gold"]])
			npc_list.set_item_metadata(npc_list.item_count - 1, n["id"])
	if sel.size() > 0 and sel[0] < npc_list.item_count:
		npc_list.select(sel[0])
	status.text = "timeline %s | tick %d | alive %d | events %d | digest %s | gold ledger err %d" % [T().tid, s["tick"], alive, s["events"].size(), K.digest_hex(s), K.conservation_error(s)]


func _selected_npc() -> int:
	var sel := npc_list.get_selected_items()
	if sel.is_empty():
		return -1
	return int(npc_list.get_item_metadata(sel[0]))


func _show_history() -> void:
	var id := _selected_npc()
	if id < 0:
		return
	var s: Dictionary = T().s
	var h: Array = K.history(s, id)
	_say("[b]History of %s#%d[/b] (%d events, last 12):" % [K.npc_name(s["npcs"][id]), id, h.size()])
	for ev in h.slice(maxi(0, h.size() - 12)):
		_say("  " + K.describe(s, ev))
	for ev in h:
		if ev[2] == K.EV_KILL and ev[4] == id:
			var ch: Array = K.consequences(s, ev[0])
			_say("  [color=salmon]its death caused %d later events[/color]" % ch.size())


func start_duel() -> void:
	var id := _selected_npc()
	if id < 0:
		_say("Select an NPC first.")
		return
	if overlay != null:
		overlay.queue_free()
	overlay = CenterContainer.new()
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(overlay)
	duel = DuelArena.new()
	overlay.add_child(duel)
	duel.setup(T().s, id, rules_name)
	duel.finished.connect(func(): overlay.queue_free(); overlay = null; duel = null)
