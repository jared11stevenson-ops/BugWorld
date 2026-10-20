# Game: Splash. A top-down water-balloon fight in three rounds. Arcing balloons, bucket stations to refill, bumpers for cover, friendly fire on.
extends "res://ghost/shell.gd"

const S = preload("res://ghost/splash_core.gd")
const D = preload("res://data/splash.gd")


class Field extends Control:
	var g

	func _gui_input(ev: InputEvent) -> void:
		if ev is InputEventMouse:
			g.mouse = g.to_arena(ev.position, size)
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			g.want_throw = true

	func _draw() -> void:
		g.draw_field(self)


var s: Dictionary
var params: Dictionary
var round_i := 0
var attempt := 0
var playing := false
var acc := 0.0
var t_anim := 0.0
var field: Field
var mouse := Vector2(600, 300)
var want_throw := false
var puddles: Array = []
var rings: Array = []
var drops: Array = []
var shake := 0.0
var testing := false
var match_log: Array = []
var wins := 0


func start() -> void:
	game_id = "splash"
	playing = false
	params = S.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in ["slick", "throw_cd", "refill_ticks", "max_ammo", "team_size", "max_ticks", "ally_level", "barrier", "ret", "win", "king_goal"]:
		params[k] = int(params[k])
	title_screen(U.get("game_title", "Splash"), "Move: WASD / arrows   Aim: mouse   Throw: click\nStand in your bucket to refill. Dodge the rings!\n" + universe_line(), [["Play", intro], ["How to play", help]])


func help() -> void:
	text_screen("How to play", "Each balloon arcs through the air and bursts where it lands, soaking everyone nearby, friends included. Three direct splashes and you are out. Stand in your team's bucket to refill (you carry up to %d). Eliminate the other team, or be the drier team when time runs out.\nLaw of this universe: %s" % [int(params["max_ammo"]), U.get("law_text", "")], "Back", start)


func intro() -> void:
	round_i = 0
	wins = 0
	text_screen("The soak of %s" % U.get("name", "this world"), "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", []))) + "\n\n" + rival_line(0) + " · " + rival_line(1) + " · " + rival_line(2), "Pick up a balloon", begin_match)


func enemy_params(r: int) -> Array:
	var lead := float(params["en_lead"])
	var err := float(params["en_err"])
	var ag := float(params["en_aggr"])
	var dg := float(params["en_dodge"])
	var m: Dictionary = rival(r)["mod"]
	err = maxf(0.0, err + float(m["err"]))
	ag = clampf(ag + float(m["aggr"]), 0.05, 1.0)
	dg = clampf(dg + float(m["dodge"]), 0.0, 1.0)
	if r == 0:
		return [lead + 0.3, err * 1.6, ag * 0.7, dg * 0.5]
	if r == 2:
		return [maxf(0.0, lead - 0.2), err * 0.5, minf(1.0, ag * 1.2), minf(1.0, dg * 1.3)]
	return [lead, err, ag, dg]


func team_in(sx: Dictionary, player_in: Array) -> Array:
	var n: int = int(params["team_size"])
	var ally: Array = S.LEVELS[int(params["ally_level"])]
	var en := enemy_params(round_i)
	var out := []
	for i in sx["agents"].size():
		if i == 0:
			out.append(player_in)
		elif i < n:
			out.append(S.ai_input(sx, i, ally))
		else:
			out.append(S.ai_input(sx, i, en))
	return out


func begin_match() -> void:
	attempt += 1
	s = S.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, params)
	puddles.clear()
	rings.clear()
	drops.clear()
	var v := clear()
	field = Field.new()
	field.g = self
	field.size_flags_vertical = Control.SIZE_EXPAND_FILL
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.custom_minimum_size = Vector2(S.W * 0.9, S.H * 0.9)
	v.add_child(field)
	playing = true
	acc = 0.0


func to_arena(p: Vector2, sz: Vector2) -> Vector2:
	var k := minf(sz.x / S.W, sz.y / S.H)
	var off := (sz - Vector2(S.W, S.H) * k) / 2.0
	return (p - off) / k


func _process(delta: float) -> void:
	t_anim += delta
	if not playing:
		return
	acc += minf(delta, 0.1)
	var ax := Input.get_axis("ui_left", "ui_right") + (float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)))
	var ay := Input.get_axis("ui_up", "ui_down") + (float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W)))
	while acc >= 1.0 / 60.0 and s["over"] == 0:
		acc -= 1.0 / 60.0
		var pin := [ax, ay, want_throw, mouse.x, mouse.y, false]
		if want_throw and int(params["ret"]) == 1:
			for b in s["balloons"]:
				if b[6] != 0 and S.balloon_pos(s, b).distance_to(Vector2(s["agents"][0]["x"], s["agents"][0]["y"])) < 62.0:
					pin[5] = true           # clicking next to an incoming balloon bats it back
					pin[2] = false
		want_throw = false
		S.step(s, team_in(s, pin))
		_events()
	_fx(delta)
	field.queue_redraw()
	if s["over"] != 0:
		playing = false
		_match_end()


func _events() -> void:
	for e in s["events"]:
		match e:
			"throw":
				sfx("step")
			"splash":
				sfx("hit")
			"hit":
				shake = 0.5
			"refill":
				sfx("cure")


func _fx(delta: float) -> void:
	for b in s["balloons"]:
		if int(s["t"]) - int(b[4]) >= int(b[5]) - 1:       # about to land: spawn splash visuals once
			pass
	for r in rings:
		r[2] += delta * 2.0
	rings = rings.filter(func(r): return r[2] < 1.0)
	for d in drops:
		d[0] += d[2] * delta
		d[1] += d[3] * delta
		d[3] += 700.0 * delta
		d[4] -= delta
	drops = drops.filter(func(d): return d[4] > 0.0)
	shake = maxf(0.0, shake - delta * 2.0)


func note_splash(x: float, y: float) -> void:
	puddles.append([x, y, float(params["splash_r"]) * 0.8, 0])
	rings.append([x, y, 0.0])
	for i in 12:
		var a := TAU * i / 12.0
		drops.append([x, y, cos(a) * (120.0 + 80.0 * float(i % 3)), sin(a) * (120.0 + 80.0 * float(i % 3)) - 200.0, 0.6])
	if puddles.size() > 40:
		puddles.pop_front()


func draw_field(c: Control) -> void:
	if s.is_empty():
		return
	var sz := c.size
	var k := minf(sz.x / S.W, sz.y / S.H)
	var off := (sz - Vector2(S.W, S.H) * k) / 2.0 + Vector2(sin(t_anim * 90.0), cos(t_anim * 77.0)) * shake * 4.0
	var P := func(x: float, y: float) -> Vector2: return off + Vector2(x, y) * k
	for ix in 12:
		for iy in 8:
			var col: Color = pal[1].darkened(0.25) if (ix + iy) % 2 == 0 else pal[1].darkened(0.15)
			c.draw_rect(Rect2(P.call(ix * 80.0, iy * 75.0), Vector2(80, 75) * k), col)
	c.draw_rect(Rect2(P.call(0, 0), Vector2(150, S.H) * k), Color(pal[3].r, pal[3].g, pal[3].b, 0.18))
	c.draw_rect(Rect2(P.call(S.W - 150, 0), Vector2(150, S.H) * k), Color(pal[2].r, pal[2].g, pal[2].b, 0.18))
	if int(params.get("barrier", 0)) == 1:        # the net across the arena (bodies cannot cross, balloons arc over)
		var nx: float = S.W / 2.0
		c.draw_rect(Rect2(P.call(nx - 3.0, 0), Vector2(6, S.H) * k), Color(1, 1, 1, 0.55))
		for iy in 15:
			c.draw_line(P.call(nx - 14.0, iy * 40.0 + 10.0), P.call(nx + 14.0, iy * 40.0 + 10.0), Color(1, 1, 1, 0.35), 2.0)
	for p in puddles:
		p[3] += 1
	puddles = puddles.filter(func(p): return p[3] < 700)
	for p in puddles:
		c.draw_circle(P.call(p[0], p[1]), p[2] * k, Color(0.3, 0.6, 1.0, 0.22 * (1.0 - float(p[3]) / 700.0)))
	for team in 2:
		var st := S.station(team)
		c.draw_circle(P.call(st.x, st.y), 42.0 * k, Color(0.15, 0.4, 0.8, 0.9))
		c.draw_arc(P.call(st.x, st.y), (30.0 + 4.0 * sin(t_anim * 3.0)) * k, 0, TAU, 24, Color(0.7, 0.9, 1.0), 2.0)
	for o in s["obst"]:
		var bump := Color(0.55, 0.55, 0.6)                       # neutral grey: never confusable with either team colour
		c.draw_circle(P.call(o[0] + 3, o[1] + 5), o[2] * k, Color(0, 0, 0, 0.3))
		c.draw_circle(P.call(o[0], o[1]), o[2] * k, bump)
		c.draw_arc(P.call(o[0], o[1]), o[2] * k, 0, TAU, 24, Color(0.85, 0.85, 0.9), 3.0)
		c.draw_arc(P.call(o[0] - 4, o[1] - 4), o[2] * 0.6 * k, 3.4, 4.9, 12, Color(1, 1, 1, 0.6), 3.0)
	for b in s["balloons"]:
		var u: float = float(int(s["t"]) - int(b[4])) / float(b[5])
		var pos := Vector2(lerpf(b[0], b[2], u), lerpf(b[1], b[3], u))
		var h := 70.0 * 4.0 * u * (1.0 - u)
		c.draw_arc(P.call(b[2], b[3]), float(params["splash_r"]) * k, 0, TAU, 28, Color(1, 1, 1, 0.25), 2.0)
		c.draw_circle(P.call(pos.x, pos.y) + Vector2(2, 4), 6.0 * k, Color(0, 0, 0, 0.3))
		var bc: Color = pal[3] if b[6] == 0 else pal[2]
		c.draw_circle(P.call(pos.x, pos.y - h), 9.0 * k, bc.lightened(0.3))
		c.draw_circle(P.call(pos.x - 3, pos.y - h - 3), 3.0 * k, Color(1, 1, 1, 0.8))
		if int(s["t"]) - int(b[4]) >= int(b[5]) - 1:
			note_splash(b[2], b[3])
	for r in rings:
		c.draw_arc(P.call(r[0], r[1]), float(params["splash_r"]) * r[2] * k, 0, TAU, 28, Color(0.8, 0.95, 1.0, 1.0 - r[2]), 3.0)
	for d in drops:
		c.draw_circle(P.call(d[0], d[1]), 3.0 * k, Color(0.7, 0.9, 1.0, clampf(d[4] * 2.0, 0.0, 1.0)))
	for i in s["agents"].size():
		var a: Dictionary = s["agents"][i]
		var team_col: Color = pal[3] if a["team"] == 0 else pal[2]
		var pos: Vector2 = P.call(a["x"], a["y"])
		if a["alive"] == 0:
			c.draw_arc(pos, 14.0 * k, 0, TAU, 14, Color(0.7, 0.8, 1.0, 0.5), 2.0)
			continue
		c.draw_circle(pos + Vector2(2, 4) * k, 16.0 * k, Color(0, 0, 0, 0.3))
		c.draw_circle(pos, 16.0 * k, team_col)
		c.draw_circle(pos, 16.0 * k * clampf(a["wet"] / 100.0, 0.0, 1.0), Color(0.2, 0.45, 0.95, 0.55))
		if i == 0:
			c.draw_arc(pos, 20.0 * k, 0, TAU, 20, Color.WHITE, 2.0)
		var f := Vector2(a["vx"], a["vy"])
		c.draw_line(pos, pos + (f.normalized() if f.length() > 0.2 else Vector2(1, 0)) * 14.0 * k, Color(1, 1, 1, 0.9), 3.0)
		for m in a["ammo"]:
			c.draw_circle(pos + Vector2(-8.0 + 8.0 * m, -26.0) * k, 3.0 * k, Color(0.8, 0.95, 1.0))
		c.draw_rect(Rect2(pos + Vector2(-14, 20) * k, Vector2(28.0 * (1.0 - clampf(a["wet"] / 100.0, 0.0, 1.0)), 4) * k), Color(0.4, 1.0, 0.5))
	if playing and s["agents"][0]["alive"] != 0:
		var me: Dictionary = s["agents"][0]
		var tp := Vector2(mouse.x, mouse.y)
		var d := tp - Vector2(me["x"], me["y"])
		if d.length() > float(params["range"]):
			tp = Vector2(me["x"], me["y"]) + d.normalized() * float(params["range"])
		c.draw_arc(P.call(tp.x, tp.y), float(params["splash_r"]) * k, 0, TAU, 28, Color(1, 1, 1, 0.5), 2.0)
		c.draw_line(P.call(me["x"], me["y"]), P.call(tp.x, tp.y), Color(1, 1, 1, 0.25), 1.0)
	var wet := [0.0, 0.0]
	for a in s["agents"]:
		wet[a["team"]] += minf(100.0, a["wet"])
	var n: int = int(params["team_size"])
	c.draw_string(ThemeDB.fallback_font, off + Vector2(12, 24), "Round %d/3   Your team dryness %d%%   Rivals %d%%   Time %d   Ammo %d" % [round_i + 1, 100 - int(wet[0] / n), 100 - int(wet[1] / n), maxi(0, (int(params["max_ticks"]) - int(s["t"])) / 60), s["agents"][0]["ammo"]], HORIZONTAL_ALIGNMENT_LEFT, -1, 20, pal[4])


func _match_end() -> void:
	var won: bool = s["winner"] == 0
	sfx("win" if won else "lose")
	match_log.append({"seed": int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, "won": won, "ticks": s["t"]})
	if testing:
		return
	if won:
		wins += 1
		round_i += 1
		save["best"] = maxi(int(save.get("best", 0)), round_i)
		write_save()
		if round_i >= 3:
			end_screen("Soak champion", "You survived every round.\n\n%s" % U.get("lore", {}).get("epilogue_win", ""), {"won": true, "attempts": attempt}, "Back to title", start)
		else:
			text_screen("Round won", "Dry enough! The next rivals throw %s." % ("with more sting" if round_i == 2 else "straighter"), "Next round", begin_match)
	else:
		text_screen("Soaked!", "You lost this round. Aim straight at the rival instead of guessing where they will be, and dodge the rings when they are close.", "Rematch", begin_match)


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	testing = true
	params = S.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in ["slick", "throw_cd", "refill_ticks", "max_ammo", "team_size", "max_ticks", "ally_level", "barrier", "ret", "win", "king_goal"]:
		params[k] = int(params[k])
	var res := {"ok": false}
	round_i = 0
	var guard := 0
	while round_i < 3 and guard < 40:
		guard += 1
		begin_match()
		await get_tree().process_frame
		playing = false
		var n := 0
		while s["over"] == 0:
			S.step(s, team_in(s, S.ai_input(s, 0, S.LEVELS[2])))
			n += 1
			if n % 60 == 0:
				t_anim += 0.2
				_fx(0.2)
				field.queue_redraw()
		if n >= 60:
			await get_tree().process_frame           # exercise the real _draw path
		_match_end()
		if s["winner"] == 0:
			round_i += 1
	res["tournament_completed"] = round_i >= 3
	res["matches_played"] = match_log.size()
	var nov := 0
	round_i = 1
	for i in 12:
		var sx := S.new_match(9000 + i, params)
		while sx["over"] == 0:
			S.step(sx, team_in(sx, S.ai_input(sx, 0, S.LEVELS[0])))
		nov += 1 if sx["winner"] == 0 else 0
	res["novice_wins_of_12"] = nov
	var d1 := S.play(4242, params, 2)
	var d2 := S.play(4242, params, 2)
	res["det_digest"] = S.digest(d1)
	res["deterministic"] = S.digest(d1) == S.digest(d2)
	var t0 := Time.get_ticks_usec()
	var s2 := S.new_match(7, params)
	for i in 1500:
		S.step(s2, S.team_inputs(s2, 1))
		if s2["over"] != 0:
			s2 = S.new_match(8 + i, params)
	res["perf_step_us"] = float(Time.get_ticks_usec() - t0) / 1500.0
	res["audio_loaded"] = sfx_players["hit"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["tournament_completed"] and nov <= 6 and res["deterministic"] and res["audio_loaded"] and res["save_written"] and res["feedback_written"]
	return res


func shot_prepare() -> void:
	begin_match()
	for i in 200:
		S.step(s, team_in(s, S.ai_input(s, 0, S.LEVELS[2])))
		t_anim += 0.02
		field.queue_redraw()
	mouse = Vector2(s["agents"][int(params["team_size"])]["x"], s["agents"][int(params["team_size"])]["y"])
