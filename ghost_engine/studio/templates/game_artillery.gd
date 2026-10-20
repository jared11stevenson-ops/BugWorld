# Game: Artillery. A turn-based ballistic duel in three rounds. Wind, gravity and armor come from the universe's shared physics; the terrain may crater.
extends "res://ghost/shell.gd"

const A = preload("res://ghost/artillery_core.gd")
const D = preload("res://data/artillery.gd")


class Field extends Control:
	var g

	func _gui_input(ev: InputEvent) -> void:
		if ev is InputEventMouseMotion:
			g.mouse_aim(ev.position, size)
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			g.mouse_aim(ev.position, size)
			g.want_fire = true

	func _draw() -> void:
		g.draw_field(self)


var s: Dictionary
var params: Dictionary
var round_i := 0
var attempt := 0
var phase := "aim"
var field: Field
var t_anim := 0.0
var want_fire := false
var aim_ang := 45.0
var aim_pow := 12.0
var wait := 0.0
var shot: Dictionary = {}
var shot_who := 0
var shot_ang := 0.0
var shot_pow := 0.0
var shot_i := 0.0
var rings: Array = []
var shake := 0.0
var testing := false
var match_log: Array = []
var wins := 0
var ai_params: Array = []
var msg := ""


func start() -> void:
	game_id = "artillery"
	phase = "idle"
	load_params()
	title_screen(U.get("game_title", "Siege"), "A duel of arcs. Mouse: aim, click to fire. Keys: A/D angle, W/S power, Space fire.\nWind pushes every shell; read the flag before you fire.\n" + universe_line(), [["Play", intro], ["How to play", help]])


func load_params() -> void:
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in A.int_keys():
		params[k] = int(params[k])


func help() -> void:
	text_screen("How to play", "Take turns firing one shell each. The angle and power you choose set the arc; wind (%s) bends it, and armor divides damage by x%.1f. A blast hurts everyone near it, you included. Reduce the rival to zero, or be healthier after %d turns.%s%s%s\nLaw of this universe: %s" % ["gusting" if int(params["gust"]) == 1 else "steady", float(params["armor"]), int(params["max_turns"]), "\nThe ground craters where shells land." if int(params["terrain"]) == 1 else "", "\nShells bounce once off the ground." if int(params["ricochet"]) == 1 else "", "", U.get("law_text", "")], "Back", start)


func intro() -> void:
	round_i = 0
	wins = 0
	text_screen("The duel of %s" % U.get("name", "this world"), "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", []))) + "\n\n" + rival_line(0) + " · " + rival_line(1) + " · " + rival_line(2), "Take position", begin_match)


func round_ai(r: int) -> Array:
	var err := float(params["ai_err"])
	var pe := float(params["ai_pow"])
	var m: Dictionary = rival(r)["mod"]
	err = maxf(0.2, err + float(m["err"]) * 0.1)
	var out := [err, pe, int(params["ai_wind"])]
	if r == 0:
		out = [err * 1.8, pe * 1.8, int(params["ai_wind"])]
	elif r == 2:
		out = [err * 0.4, pe * 0.5, int(params["ai_wind"])]
	out[0] = float("%.4f" % float(out[0]))
	out[1] = float("%.4f" % float(out[1]))
	return out


func begin_match() -> void:
	attempt += 1
	ai_params = round_ai(round_i)
	s = A.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, params)
	var v := clear()
	field = Field.new()
	field.g = self
	field.size_flags_vertical = Control.SIZE_EXPAND_FILL
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.custom_minimum_size = Vector2(A.W * 0.9, A.H * 0.9)
	v.add_child(field)
	rings.clear()
	phase = "aim"
	wait = 0.0
	want_fire = false
	msg = "Your turn" if s["turn"] == 0 else "Rival's turn"
	aim_ang = 45.0
	aim_pow = float(params["pmax"]) * 0.65
	if s["turn"] == 1:
		phase = "wait"
		wait = 0.9


func scale_of(sz: Vector2) -> float:
	return minf(sz.x / A.W, sz.y / A.H)


func mouse_aim(pos: Vector2, sz: Vector2) -> void:
	if s.is_empty() or phase != "aim" or s["turn"] != 0:
		return
	var k := scale_of(sz)
	var off := (sz - Vector2(A.W, A.H) * k) / 2.0
	var w := (pos - off) / k
	var me := Vector2(float(s["x"][0]), A.tank_y(s, 0) - 12.0)
	var d := w - me
	aim_ang = clampf(rad_to_deg(atan2(-d.y, maxf(1.0, d.x))), 3.0, 87.0)
	aim_pow = clampf(d.length() / 380.0 * float(params["pmax"]), float(params["pmax"]) * 0.2, float(params["pmax"]))


func start_fly(who: int, ang: float, pw: float) -> void:
	shot_who = who
	shot_ang = ang
	shot_pow = pw
	shot = A.sim_shot(s, who, ang, pw, float(s["wind"]), true)
	shot_i = 0.0
	phase = "fly"
	sfx("step")


func _process(delta: float) -> void:
	t_anim += delta
	if s.is_empty() or field == null or testing:
		return
	shake = maxf(0.0, shake - delta * 2.0)
	for r in rings:
		r[2] += delta * 1.6
	rings = rings.filter(func(r): return r[2] < 1.0)
	if phase == "aim" and s["turn"] == 0:
		aim_ang = clampf(aim_ang + (float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))) * delta * 40.0, 3.0, 87.0)
		aim_pow = clampf(aim_pow + (float(Input.is_key_pressed(KEY_W)) - float(Input.is_key_pressed(KEY_S))) * delta * 6.0, float(params["pmax"]) * 0.2, float(params["pmax"]))
		if want_fire or Input.is_key_pressed(KEY_SPACE):
			want_fire = false
			start_fly(0, aim_ang, aim_pow)
	elif phase == "wait":
		wait -= delta
		if wait <= 0.0:
			var a := A.ai_choose(s, 1, ai_params)
			start_fly(1, a[0], a[1])
	elif phase == "fly":
		shot_i += delta * 70.0
		if int(shot_i) >= shot["path"].size():
			land()
	field.queue_redraw()


func land() -> void:
	var r := A.fire(s, shot_who, shot_ang, shot_pow)
	for e in s["events"]:
		if e == "blast":
			rings.append([float(r["x"]), float(r["y"]), 0.0])
			sfx("hit")
			shake = 0.6
		if e == "hit":
			sfx("burn")
	phase = "aim"
	if s["over"] != 0:
		phase = "done"
		_match_end()
		return
	if s["turn"] == 1:
		phase = "wait"
		wait = 0.7
		msg = "Rival's turn"
	else:
		msg = "Your turn"


func draw_field(c: Control) -> void:
	if s.is_empty():
		return
	var sz := c.size
	var k := scale_of(sz)
	var off := (sz - Vector2(A.W, A.H) * k) / 2.0 + Vector2(sin(t_anim * 90.0), cos(t_anim * 77.0)) * shake * 4.0
	var P := func(x: float, y: float) -> Vector2: return off + Vector2(x, y) * k
	for band in 8:
		c.draw_rect(Rect2(P.call(0.0, A.H * float(band) / 8.0), Vector2(A.W, A.H / 8.0 + 1.0) * k), pal[0].lerp(pal[1].lightened(0.35), 0.1 + 0.6 * float(band) / 8.0))
	for i in 5:
		c.draw_circle(P.call(120.0 + 190.0 * float(i) + 18.0 * sin(t_anim * 0.3 + float(i)), 90.0 + 30.0 * float(i % 2)), 40.0 * k, Color(1, 1, 1, 0.12))
	var pts := PackedVector2Array()
	pts.append(P.call(0.0, A.H))
	for i in A.COLS:
		pts.append(P.call((float(i) + 0.5) * A.CW, float(s["ter"][i])))
	pts.append(P.call(A.W, A.H))
	c.draw_colored_polygon(pts, pal[2].darkened(0.5))
	for i in A.COLS - 1:
		c.draw_line(P.call((float(i) + 0.5) * A.CW, float(s["ter"][i])), P.call((float(i) + 1.5) * A.CW, float(s["ter"][i + 1])), pal[4].darkened(0.25), 3.0)
	for r in rings:
		c.draw_arc(P.call(r[0], r[1]), float(params["blast_r"]) * r[2] * k, 0, TAU, 28, Color(1, 0.9, 0.6, 1.0 - r[2]), 4.0)
		c.draw_circle(P.call(r[0], r[1]), float(params["blast_r"]) * (1.0 - r[2]) * 0.5 * k, Color(1, 0.7, 0.3, 0.5 * (1.0 - r[2])))
	for i in 2:
		draw_tank(c, P, k, i)
	if phase == "fly":
		var path: Array = shot["path"]
		var upto := mini(int(shot_i), path.size())
		for j in range(maxi(0, upto - 12), upto):
			c.draw_circle(P.call(path[j][0], path[j][1]), (2.0 + float(j - (upto - 12)) * 0.25) * k, Color(1, 0.85, 0.5, 0.8))
		if upto > 0:
			c.draw_circle(P.call(path[upto - 1][0], path[upto - 1][1]), 6.0 * k, Color(1, 0.95, 0.8))
	if phase == "aim" and s["turn"] == 0:
		var me := Vector2(float(s["x"][0]), A.tank_y(s, 0) - 12.0)
		var a := deg_to_rad(aim_ang)
		var ln := aim_pow / float(params["pmax"]) * 380.0
		c.draw_line(P.call(me.x, me.y), P.call(me.x + cos(a) * ln, me.y - sin(a) * ln), Color(1, 1, 1, 0.55), 2.0)
		c.draw_circle(P.call(me.x + cos(a) * ln, me.y - sin(a) * ln), 5.0 * k, Color(1, 1, 1, 0.7))
	# wind flag
	var wv := float(s["wind"])
	var wmax := maxf(0.001, absf(float(s["wind0"])) * 1.6)
	var wl := clampf(wv / wmax, -1.0, 1.0) * 60.0
	c.draw_string(ThemeDB.fallback_font, off + Vector2(A.W * 0.5 - 40.0, 26.0) * k, "WIND", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, pal[4])
	c.draw_line(P.call(A.W * 0.5, 42.0), P.call(A.W * 0.5 + wl, 42.0), pal[4], 4.0)
	c.draw_circle(P.call(A.W * 0.5 + wl, 42.0), 6.0 * k, pal[3])
	for i in 2:
		var hp := clampf(float(s["hp"][i]) / float(params["hp"]), 0.0, 1.0)
		var bx := 24.0 if i == 0 else A.W - 224.0
		c.draw_rect(Rect2(P.call(bx, 20.0), Vector2(200, 14) * k), Color(0, 0, 0, 0.4))
		c.draw_rect(Rect2(P.call(bx, 20.0), Vector2(200.0 * hp, 14) * k), pal[3] if i == 0 else pal[2])
	c.draw_string(ThemeDB.fallback_font, off + Vector2(24.0, 58.0) * k, "Round %d/3   %s   angle %d   power %d   turn %d/%d" % [round_i + 1, msg, int(aim_ang), int(aim_pow / float(params["pmax"]) * 100.0), int(s["t"]) + 1, int(params["max_turns"])], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, pal[4])


func draw_tank(c: Control, P: Callable, k: float, i: int) -> void:
	var col: Color = pal[3] if i == 0 else pal[2]
	var x: float = float(s["x"][i])
	var y: float = A.tank_y(s, i)
	var dir := 1.0 if i == 0 else -1.0
	var alive: bool = float(s["hp"][i]) > 0.0
	var ts := 1.35
	# the barrel points along the current aim (player) or the last shot (rival)
	var ang := aim_ang if i == 0 else (shot_ang if shot_who == 1 and not shot.is_empty() else 45.0)
	var a := deg_to_rad(ang)
	var base: Vector2 = P.call(x, y - 4.0 * ts)
	c.draw_line(base, base + Vector2(cos(a) * dir, -sin(a)) * 34.0 * ts * k, col.darkened(0.45), 8.0 * ts * k)
	# a domed shell on treads: the universe's armored creature
	var dome := PackedVector2Array()
	for j in 13:
		var th := PI * float(j) / 12.0
		dome.append(P.call(x - cos(th) * 17.0 * ts, y - 2.0 * ts - sin(th) * 14.0 * ts))
	c.draw_colored_polygon(dome, col if alive else col.darkened(0.6))
	for j in 3:
		c.draw_arc(P.call(x, y - 2.0 * ts), (5.0 + 4.5 * float(j)) * ts * k, PI, TAU, 10, col.darkened(0.4), 2.0)
	c.draw_rect(Rect2(P.call(x - 19.0 * ts, y - 2.0 * ts), Vector2(38, 9) * ts * k), Color(0.08, 0.08, 0.1))
	for j in 4:
		c.draw_circle(P.call(x - 13.5 * ts + 9.0 * ts * float(j), y + 2.5 * ts), 3.4 * ts * k, Color(0.55, 0.55, 0.6))
	if i == 0:
		c.draw_arc(P.call(x, y - 8.0), 28.0 * k, 0, TAU, 20, Color.WHITE, 2.0)


func _match_end() -> void:
	var won: bool = s["winner"] == 0
	sfx("win" if won else "lose")
	match_log.append({"seed": int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, "won": won, "turns": s["t"]})
	if testing:
		return
	if won:
		wins += 1
		round_i += 1
		save["best"] = maxi(int(save.get("best", 0)), round_i)
		write_save()
		if round_i >= 3:
			end_screen("Victor of %s" % U.get("name", "the duel"), "Three duels won.\n\n%s" % U.get("lore", {}).get("epilogue_win", ""), {"won": true, "attempts": attempt}, "Back to title", start)
		else:
			text_screen("Duel won", "Next rival: %s. %s" % [rival(round_i)["faction"], "Their aim is sharper." if round_i == 2 else "They compensate for wind."], "Next duel", begin_match)
	else:
		text_screen("Struck down", "You lost this duel. Watch the wind flag, correct from where your last shell landed, and keep out of your own blast.", "Rematch", begin_match)


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
		s = A.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, params)
		var n := 0
		while s["over"] == 0:
			var who: int = s["turn"]
			var a := A.ai_choose(s, who, A.LEVELS[2] if who == 0 else ai_params)
			shot_who = who
			shot_ang = a[0]
			shot_pow = a[1]
			shot = A.sim_shot(s, who, a[0], a[1], float(s["wind"]), true)
			A.fire(s, who, a[0], a[1])
			rings.append([float(shot["x"]), float(shot["y"]), 0.3])
			n += 1
			field.queue_redraw()
		if n >= 2:
			await get_tree().process_frame           # exercise the real _draw path
		_match_end()
		if s["winner"] == 0:
			round_i += 1
	res["tournament_completed"] = round_i >= 3
	res["matches_played"] = match_log.size()
	var nov := 0
	round_i = 1
	for i in 12:
		var sx := A.new_match(9000 + i, params)
		while sx["over"] == 0:
			var who: int = sx["turn"]
			var a := A.ai_choose(sx, who, A.LEVELS[0] if who == 0 else round_ai(1))
			A.fire(sx, who, a[0], a[1])
		nov += 1 if sx["winner"] == 0 else 0
	res["novice_wins_of_12"] = nov
	var d1 := A.play(4242, params, 2)
	var d2 := A.play(4242, params, 2)
	res["det_digest"] = A.digest(d1)
	res["deterministic"] = A.digest(d1) == A.digest(d2)
	var t0 := Time.get_ticks_usec()
	var steps := 0
	var s2 := A.new_match(7, params)
	for i in 40:
		steps += int(A.sim_shot(s2, i % 2, 20.0 + float(i % 6) * 10.0, float(params["pmax"]) * (0.4 + 0.1 * float(i % 5)), float(s2["wind"]))["steps"])
	res["perf_step_us"] = float(Time.get_ticks_usec() - t0) / float(maxi(1, steps))
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
	for i in 5:
		var who: int = s["turn"]
		var a := A.ai_choose(s, who, A.LEVELS[1])
		shot_who = who
		shot_ang = a[0]
		shot_pow = a[1]
		shot = A.sim_shot(s, who, a[0], a[1], float(s["wind"]), true)
		A.fire(s, who, a[0], a[1])
		if s["over"] != 0:
			break
	if s["over"] != 0:
		s = A.new_match(11, params)
	phase = "aim"
	msg = "Your turn"
	s["turn"] = 0
	aim_ang = 52.0
	aim_pow = float(params["pmax"]) * 0.7
	field.queue_redraw()
