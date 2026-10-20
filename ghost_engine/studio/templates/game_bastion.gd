# Game: Bastion. Wave defence in three rounds: fortify build slots beside the invaders' path before they get through. Armor, gravity and the fiction come from the universe.
extends "res://ghost/shell.gd"

const B = preload("res://ghost/bastion_core.gd")
const D = preload("res://data/bastion.gd")
const TYPE_NAMES := ["Cannon", "Mortar", "Chill"]


class Field extends Control:
	var g

	func _gui_input(ev: InputEvent) -> void:
		if ev is InputEventMouseMotion:
			g.hover = g.to_arena(ev.position, size)
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			g.click_at(g.to_arena(ev.position, size))

	func _draw() -> void:
		g.draw_field(self)


var s: Dictionary
var params: Dictionary
var round_i := 0
var attempt := 0
var playing := false
var acc := 0.0
var speed_mul := 1.0
var t_anim := 0.0
var field: Field
var hover := Vector2(-100, -100)
var sel_type := 0
var fx: Array = []
var shake := 0.0
var testing := false
var match_log: Array = []
var wins := 0
var info: Label
var msg := "Build, then press Start wave"


func start() -> void:
	game_id = "bastion"
	playing = false
	load_params()
	title_screen(U.get("game_title", "Bastion"), "Click a build slot to fortify it (click again to upgrade). Keys 1-3 choose the tower, Space starts the wave.\nStop the invaders before they reach the end of the road.\n" + universe_line(), [["Play", intro], ["How to play", help]])


func load_params() -> void:
	params = B.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in B.int_keys():
		params[k] = int(params[k])


func round_params(r: int) -> Dictionary:
	var p := params.duplicate()
	if r == 0:
		p["hp0"] = float(p["hp0"]) * 0.8
		p["money"] = int(float(p["money"]) * 1.2)
	elif r == 2:
		p["hp0"] = float(p["hp0"]) * 1.2
	return p


func help() -> void:
	text_screen("How to play", "%d waves of invaders follow the road; each one that reaches the end costs a life (heavy ones cost two). Cannons hit the leader; %s%sUpgrading a tower costs less than a new one, but every new tower makes the next dearer, so choose slots that see a long stretch of road.%s\nLaw of this universe: %s" % [int(params["waves"]), "mortars lob area shells that take time to land (gravity x%.2f); " % (0.3 / float(params["gravity"])) if int(params["mortar"]) == 1 else "", "chill towers slow what they hit; " if int(params["chill"]) == 1 else "", " Armored invaders take damage divided by %.1f." % float(params["armor"]) if int(params["armored"]) == 1 else "", U.get("law_text", "")], "Back", start)


func intro() -> void:
	round_i = 0
	wins = 0
	text_screen("The bastion of %s" % U.get("name", "this world"), "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", []))) + "\n\n" + rival_line(0) + " · " + rival_line(1) + " · " + rival_line(2), "Man the walls", begin_match)


func begin_match() -> void:
	attempt += 1
	s = B.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, round_params(round_i))
	fx.clear()
	var v := clear()
	field = Field.new()
	field.g = self
	field.size_flags_vertical = Control.SIZE_EXPAND_FILL
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.custom_minimum_size = Vector2(B.W * 0.9, B.H * 0.86)
	v.add_child(field)
	var row := HBoxContainer.new()
	v.add_child(row)
	for t in 3:
		if B.type_allowed(s, t):
			var ti: int = t
			button(row, "%d %s" % [t + 1, TYPE_NAMES[t]], func(): sel_type = ti)
	button(row, "Start wave (Space)", start_wave_now)
	button(row, "Speed x1/x3", func(): speed_mul = 3.0 if speed_mul < 2.0 else 1.0)
	playing = true
	acc = 0.0
	msg = "Build, then press Start wave"


func to_arena(p: Vector2, sz: Vector2) -> Vector2:
	var k := minf(sz.x / B.W, sz.y / B.H)
	var off := (sz - Vector2(B.W, B.H) * k) / 2.0
	return (p - off) / k


func click_at(w: Vector2) -> void:
	if not playing:
		return
	var best := -1
	var bd := 1e9
	for i in B.NS:
		var d := w.distance_to(Vector2(s["slots"][i][0], s["slots"][i][1]))
		if d < 30.0 and d < bd:
			bd = d
			best = i
	if best < 0:
		return
	var type: int = sel_type if int(s["tw"][best]) < 0 else int(s["tw"][best])
	if B.build(s, best, type):
		sfx("pickup")
		msg = "Built" if int(s["lv"][best]) == 0 else "Upgraded"
	else:
		sfx("click")
		msg = "Not enough money (or already maxed)"


func start_wave_now() -> void:
	if playing and int(s["wave_active"]) == 0:
		B.start_wave(s)
		msg = "Wave %d" % (int(s["wave"]) + 1)
		sfx("alarm")


func _unhandled_key_input(ev: InputEvent) -> void:
	if ev is InputEventKey and ev.pressed and s.size() > 0:
		if ev.keycode == KEY_SPACE:
			start_wave_now()
		elif ev.keycode >= KEY_1 and ev.keycode <= KEY_3 and B.type_allowed(s, int(ev.keycode) - KEY_1):
			sel_type = int(ev.keycode) - KEY_1


func _process(delta: float) -> void:
	t_anim += delta
	if not playing or testing:
		return
	acc += minf(delta, 0.1) * speed_mul
	while acc >= 1.0 / 60.0 and s["over"] == 0:
		acc -= 1.0 / 60.0
		B.step(s)
		_events()
	for f in fx:
		f[4] -= 1
	fx = fx.filter(func(f): return f[4] > 0)
	shake = maxf(0.0, shake - delta * 2.0)
	field.queue_redraw()
	if s["over"] != 0:
		playing = false
		_match_end()


func _events() -> void:
	for b in s["beams"]:
		fx.append([b[0], b[1], b[2].x, b[2].y, 6])
	for e in s["events"]:
		match e:
			"kill":
				sfx("hit")
			"leak":
				sfx("alarm")
				shake = 0.6
			"boom":
				sfx("burn")
			"wave":
				sfx("cure")
				msg = "Wave cleared. Build, then press Start wave"


func draw_field(c: Control) -> void:
	if s.is_empty():
		return
	var sz := c.size
	var k := minf(sz.x / B.W, sz.y / B.H)
	var off := (sz - Vector2(B.W, B.H) * k) / 2.0 + Vector2(sin(t_anim * 90.0), cos(t_anim * 77.0)) * shake * 4.0
	var P := func(x: float, y: float) -> Vector2: return off + Vector2(x, y) * k
	c.draw_rect(Rect2(off, Vector2(B.W, B.H) * k), pal[1].darkened(0.1))
	for i in 7:
		c.draw_circle(P.call(80.0 + 150.0 * float(i), 80.0 + 230.0 * float((i * 5) % 3)), 60.0 * k, Color(1, 1, 1, 0.04))
	var pts := PackedVector2Array()
	for q in s["path"]:
		pts.append(P.call(q[0], q[1]))
	c.draw_polyline(pts, pal[4].darkened(0.55), 44.0 * k, true)
	c.draw_polyline(pts, pal[0].lightened(0.28), 36.0 * k, true)
	for i in B.NS:
		var sp: Array = s["slots"][i]
		var ty: int = s["tw"][i]
		var pos: Vector2 = P.call(sp[0], sp[1])
		if ty < 0:
			c.draw_arc(pos, 22.0 * k, 0, TAU, 20, Color(1, 1, 1, 0.5), 2.0)
			c.draw_circle(pos, 5.0 * k, Color(1, 1, 1, 0.3))
			if hover.distance_to(Vector2(sp[0], sp[1])) < 30.0:
				c.draw_arc(pos, B.tower_range(s, sel_type, 0) * k, 0, TAU, 40, Color(1, 1, 1, 0.25), 2.0)
			continue
		var lvl: int = s["lv"][i]
		var col: Color = pal[3].lightened(0.1 * float(lvl))
		c.draw_circle(pos + Vector2(2, 4) * k, 20.0 * k, Color(0, 0, 0, 0.35))
		if ty == 0:
			c.draw_circle(pos, 18.0 * k, col)
			c.draw_line(pos, pos + Vector2(0, -26) * k, col.darkened(0.5), 7.0 * k)
		elif ty == 1:
			c.draw_rect(Rect2(pos - Vector2(18, 18) * k, Vector2(36, 36) * k), col)
			c.draw_circle(pos, 9.0 * k, col.darkened(0.55))
		else:
			c.draw_colored_polygon(PackedVector2Array([pos + Vector2(0, -22) * k, pos + Vector2(17, 0) * k, pos + Vector2(0, 22) * k, pos + Vector2(-17, 0) * k]), col)
		for m in lvl + 1:
			c.draw_circle(pos + Vector2(-8.0 + 8.0 * float(m), 28.0) * k, 3.0 * k, Color(1, 1, 0.7))
		if hover.distance_to(Vector2(sp[0], sp[1])) < 30.0:
			c.draw_arc(pos, B.tower_range(s, ty, lvl) * k, 0, TAU, 40, Color(1, 1, 1, 0.3), 2.0)
	for f in fx:
		c.draw_line(P.call(f[0], f[1]), P.call(f[2], f[3]), Color(1, 0.95, 0.6, float(f[4]) / 6.0), 3.0 * k)
	for sh in s["shells"]:
		c.draw_arc(P.call(sh[0], sh[1]), float(params["mortar_r"]) * k, 0, TAU, 24, Color(1, 0.6, 0.3, 0.45), 2.0)
	for e in s["enemies"]:
		var pos: Vector2 = P.call(float(e["px"]), float(e["py"]))
		var heavy: bool = int(e["armored"]) == 1
		var rr := (17.0 if heavy else 11.0) * k
		c.draw_circle(pos + Vector2(2, 3) * k, rr, Color(0, 0, 0, 0.35))
		c.draw_circle(pos, rr, pal[2].lerp(Color(0.5, 0.7, 1.0), 0.5 if int(e["slow"]) > 0 else 0.0))
		if heavy:
			c.draw_arc(pos, rr * 0.6, PI, TAU, 10, pal[2].darkened(0.5), 3.0 * k)
		c.draw_rect(Rect2(pos + Vector2(-12, -rr / k - 8.0) * k, Vector2(24.0 * clampf(float(e["hp"]) / float(e["max"]), 0.0, 1.0), 4) * k), Color(0.4, 1.0, 0.5))
	c.draw_string(ThemeDB.fallback_font, off + Vector2(12, 24), "Round %d/3   Wave %d/%d   Money %d   Lives %d   Tower: %s   %s" % [round_i + 1, mini(int(s["wave"]) + 1, int(s["p"]["waves"])), int(s["p"]["waves"]), int(s["money"]), int(s["lives"]), TYPE_NAMES[sel_type], msg], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, pal[4])


func _match_end() -> void:
	var won: bool = s["winner"] == 0
	sfx("win" if won else "lose")
	match_log.append({"seed": int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, "won": won, "ticks": s["t"], "lives": s["lives"]})
	if testing:
		return
	if won:
		wins += 1
		round_i += 1
		save["best"] = maxi(int(save.get("best", 0)), round_i)
		write_save()
		if round_i >= 3:
			end_screen("The line held", "Three sieges broken.\n\n%s" % U.get("lore", {}).get("epilogue_win", ""), {"won": true, "attempts": attempt}, "Back to title", start)
		else:
			text_screen("Siege broken", "The next assault is %s." % ("heavier. Expect more per wave" if round_i == 2 else "harder, and on new ground"), "Next siege", begin_match)
	else:
		text_screen("Breached", "The road fell. Put towers where they see the longest stretch of road, upgrade before you over-build, and spend as soon as you can.", "Try again", begin_match)


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	testing = true
	load_params()
	var res := {"ok": false}
	round_i = 0
	var guard := 0
	while round_i < 3 and guard < 40:
		guard += 1
		begin_match()
		await get_tree().process_frame
		var n := 0
		while s["over"] == 0:
			if int(s["wave_active"]) == 0:
				B.bot_act(s, B.LEVELS[2])
				B.start_wave(s)
			elif int(s["t"]) % 40 == 0:
				B.bot_act(s, B.LEVELS[2])
			B.step(s)
			_events()
			n += 1
			if n % 400 == 0:
				for f in fx:
					f[4] -= 1
				field.queue_redraw()
		if n >= 400:
			await get_tree().process_frame           # exercise the real _draw path
		_match_end()
		if s["winner"] == 0:
			round_i += 1
	res["tournament_completed"] = round_i >= 3
	res["matches_played"] = match_log.size()
	var nov := 0
	for i in 12:
		nov += 1 if B.play(9000 + i, round_params(1), 0)["winner"] == 0 else 0
	res["novice_wins_of_12"] = nov
	var d1 := B.play(4242, params, 2)
	var d2 := B.play(4242, params, 2)
	res["det_digest"] = B.digest(d1)
	res["deterministic"] = B.digest(d1) == B.digest(d2)
	var t0 := Time.get_ticks_usec()
	var s2 := B.new_match(7, params)
	B.bot_act(s2, B.LEVELS[2])
	B.start_wave(s2)
	for i in 1500:
		B.step(s2)
		if s2["over"] != 0:
			s2 = B.new_match(8 + i, params)
			B.bot_act(s2, B.LEVELS[2])
			B.start_wave(s2)
	res["perf_step_us"] = float(Time.get_ticks_usec() - t0) / 1500.0
	res["audio_loaded"] = sfx_players["hit"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["tournament_completed"] and nov <= 6 and res["deterministic"] and res["audio_loaded"] and res["save_written"] and res["feedback_written"]
	return res


func shot_prepare() -> void:
	testing = false
	begin_match()
	B.bot_act(s, B.LEVELS[2])
	B.start_wave(s)
	for i in 520:
		if int(s["t"]) % 40 == 0:
			B.bot_act(s, B.LEVELS[2])
		B.step(s)
		_events()
	playing = false
	hover = Vector2(s["slots"][0][0], s["slots"][0][1])
	field.queue_redraw()
