# Studio shell shared by every produced game: universe theme, procedural emblem, audio, save data, screens, self-test hook.
extends Control

var U: Dictionary = {}            # universe data (res://data/universe.json)
var pal: Array = []
var content: Control
var sfx_players: Dictionary = {}
var music_player: AudioStreamPlayer
var ambient_player: AudioStreamPlayer
var save: Dictionary = {"volume": 0.8, "best": 0}
var game_id := "game"
const SAVE_PATH := "user://save.json"
const FEEDBACK_PATH := "user://feedback.jsonl"
const SFX_NAMES := ["click", "hit", "pickup", "win", "lose", "pulse", "alarm", "burn", "cure", "infect", "step", "ui_open"]


class Emblem extends Control:
	var seed_v := 1
	var colors: Array = []

	func _draw() -> void:
		var c := size / 2.0
		var r := minf(size.x, size.y) * 0.45
		var rnd := RandomNumberGenerator.new()
		rnd.seed = seed_v
		var petals := 5 + rnd.randi() % 5
		for ring in 3:
			var pts := PackedVector2Array()
			var rr := r * (1.0 - ring * 0.28)
			for i in petals * 2:
				var a := TAU * i / (petals * 2)
				var k := rr if i % 2 == 0 else rr * (0.45 + 0.1 * ring)
				pts.append(c + Vector2(cos(a), sin(a)) * k)
			draw_colored_polygon(pts, colors[(ring + 1) % colors.size()].darkened(0.1 * ring))
		draw_circle(c, r * 0.18, colors[4 % colors.size()])


func _ready() -> void:
	var f := FileAccess.open("res://data/universe.json", FileAccess.READ)
	if f:
		U = JSON.parse_string(f.get_as_text())
	for h in U.get("palette", ["#101820", "#203040", "#e0c060", "#60c0e0", "#f0f0f0"]):
		pal.append(Color(h))
	_load_save()
	var bg := ColorRect.new()
	bg.color = pal[0]
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	content = MarginContainer.new()
	content.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		content.add_theme_constant_override("margin_" + side, 24)
	add_child(content)
	theme = _make_theme()
	for n in SFX_NAMES:
		var p := AudioStreamPlayer.new()
		p.stream = load_wav("res://audio/%s.wav" % n)
		add_child(p)
		sfx_players[n] = p
	music_player = AudioStreamPlayer.new()
	music_player.stream = load_wav("res://audio/music.wav", true)
	add_child(music_player)
	ambient_player = AudioStreamPlayer.new()
	if FileAccess.file_exists("res://audio/ambient.wav"):
		ambient_player.stream = load_wav("res://audio/ambient.wav", true)
	add_child(ambient_player)
	_apply_volume()
	if not "--headless" in OS.get_cmdline_args() and DisplayServer.get_name() != "headless":
		music_player.play()
		ambient_player.play()
	start()


func start() -> void:
	pass


func _make_theme() -> Theme:
	var t := Theme.new()
	t.set_color("font_color", "Label", pal[4])
	t.set_color("font_color", "Button", pal[4])
	t.set_color("font_hover_color", "Button", pal[3])
	t.set_color("font_color", "RichTextLabel", pal[4])
	t.set_color("default_color", "RichTextLabel", pal[4])
	for state in ["normal", "hover", "pressed", "disabled"]:
		var sb := StyleBoxFlat.new()
		sb.bg_color = pal[1].lightened({"normal": 0.0, "hover": 0.15, "pressed": 0.3, "disabled": -0.3}[state])
		sb.border_color = pal[2]
		sb.set_border_width_all(2 if state != "disabled" else 1)
		sb.set_corner_radius_all(6)
		sb.set_content_margin_all(8)
		t.set_stylebox(state, "Button", sb)
	t.set_font_size("font_size", "Label", 18)
	t.set_font_size("font_size", "Button", 18)
	t.set_font_size("normal_font_size", "RichTextLabel", 18)
	return t


static func load_wav(path: String, loop := false) -> AudioStreamWAV:
	# Reads the PCM data directly so no editor import step is needed.
	var b := FileAccess.get_file_as_bytes(path)
	var s := AudioStreamWAV.new()
	if b.size() < 44:
		return s
	var pos := 12
	while pos + 8 < b.size():
		var id := b.slice(pos, pos + 4).get_string_from_ascii()
		var sz := b.decode_u32(pos + 4)
		if id == "data":
			s.data = b.slice(pos + 8, pos + 8 + sz)
			break
		pos += 8 + sz
	s.format = AudioStreamWAV.FORMAT_16_BITS
	s.mix_rate = 22050
	s.stereo = false
	if loop:
		s.loop_mode = AudioStreamWAV.LOOP_FORWARD
		s.loop_end = s.data.size() / 2
	return s


func sfx(name: String) -> void:
	if sfx_players.has(name):
		sfx_players[name].play()


func _apply_volume() -> void:
	var db := linear_to_db(maxf(0.001, float(save["volume"])))
	for p in sfx_players.values():
		p.volume_db = db
	music_player.volume_db = db - 8.0
	ambient_player.volume_db = db - 14.0


func _load_save() -> void:
	if FileAccess.file_exists(SAVE_PATH):
		var d = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
		if d is Dictionary:
			for k in d:
				save[k] = d[k]


func write_save() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(save))
	f.close()


# ------------------------------------------------------------ screens
func clear() -> VBoxContainer:
	for c in content.get_children():
		c.queue_free()
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	content.add_child(v)
	v.modulate.a = 0.0
	create_tween().tween_property(v, "modulate:a", 1.0, 0.25)     # fade-in transition
	return v


func label(parent: Node, text: String, size := 18, col := -1, wrap := false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	if col >= 0:
		l.add_theme_color_override("font_color", pal[col])
	if wrap:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(700, 0)
	parent.add_child(l)
	return l


func button(parent: Node, text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(func(): sfx("click"); cb.call())
	parent.add_child(b)
	return b


func emblem(parent: Node, sz := 160) -> void:
	var e := Emblem.new()
	e.seed_v = int(U.get("seed", 1)) * 31 + game_id.hash() % 1000
	e.colors = pal
	e.custom_minimum_size = Vector2(sz, sz)
	e.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	e.pivot_offset = Vector2(sz, sz) / 2.0
	parent.add_child(e)
	var tw := e.create_tween().set_loops()                         # breathing emblem
	tw.tween_property(e, "scale", Vector2(1.06, 1.06), 1.6).set_trans(Tween.TRANS_SINE)
	tw.tween_property(e, "scale", Vector2(1.0, 1.0), 1.6).set_trans(Tween.TRANS_SINE)


func title_screen(title: String, subtitle: String, entries: Array) -> VBoxContainer:
	var v := clear()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	emblem(v)
	var t := label(v, title, 44, 2)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var s := label(v, subtitle, 20, 3, true)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	for e in entries:
		button(v, e[0], e[1])
	button(v, "Volume: %d%%" % int(float(save["volume"]) * 100), func():
		save["volume"] = 0.2 if float(save["volume"]) > 0.9 else float(save["volume"]) + 0.2
		_apply_volume()
		write_save()
		start())
	return v


func text_screen(title: String, body: String, next_label: String, next: Callable) -> void:
	var v := clear()
	label(v, title, 32, 2)
	label(v, body, 20, 4, true)
	button(v, next_label, next)


# Ending screen with human feedback: rating buttons write a record that studio.feedback imports into the knowledge store.
func end_screen(title: String, body: String, ctx: Dictionary, next_label: String, next: Callable) -> void:
	var v := clear()
	label(v, title, 34, 2)
	label(v, body, 20, 4, true)
	label(v, "How was that run?  (your rating teaches the studio)", 16, 3)
	var row := HBoxContainer.new()
	v.add_child(row)
	for r in range(1, 6):
		button(row, str(r) + " ★", func(): rate_run(r, ctx); sfx("pickup"); next.call())
	button(v, next_label, next)


func rate_run(r: int, ctx: Dictionary) -> void:
	var rec := {"game": game_id, "universe": U.get("id", ""), "rating": r, "ctx": ctx}
	var f := FileAccess.open(FEEDBACK_PATH, FileAccess.READ_WRITE) if FileAccess.file_exists(FEEDBACK_PATH) else FileAccess.open(FEEDBACK_PATH, FileAccess.WRITE)
	f.seek_end()
	f.store_line(JSON.stringify(rec))
	f.close()


func universe_line() -> String:
	return "%s  ·  %s" % [U.get("name", "?"), ", ".join(U.get("inspirations", []))]


# self-test contract: games override selftest() and return {"ok": bool, ...}; run by tests/selftest.gd
func selftest() -> Dictionary:
	return {"ok": false, "reason": "not implemented"}
