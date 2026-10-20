# Game 3: real-time arcade. Collect shards through three stages while the universe's physical law pushes you around.
extends "res://ghost/shell.gd"

const A = preload("res://ghost/arcade_core.gd")
const D = preload("res://data/arcade.gd")

class Field extends Control:
	var g

	func _draw() -> void:
		g.draw_field(self)


var field: Field
var s: Dictionary
var stage := 1
var total := 0
var playing := false
var acc := 0.0
var seed_i := 1
var params: Dictionary


func start() -> void:
	game_id = "arcade"
	playing = false
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	title_screen(U.get("game_title", "Arcade"), "Arrow keys / WASD to move, SPACE to dash.\n" + universe_line() + "\nBest score: %d" % int(save.get("best", 0)),
		[["Play", intro], ["Controls & rules", help]])


func help() -> void:
	text_screen("Controls & rules", "Move with arrow keys or WASD. SPACE dashes (brief invulnerability, short cooldown). Collect the glowing shards to clear a stage before time runs out. You have 3 hearts per stage; touching hazards costs one.\nLaw of this universe: %s" % U.get("law_text", ""), "Back", start)


func intro() -> void:
	total = 0
	stage = 1
	text_screen("The law of %s" % U.get("name", "this world"), U.get("law_text", "") + "\n\n" + "\n".join(PackedStringArray(U.get("fact_lines", []))), "Enter stage 1", begin_stage)


func begin_stage() -> void:
	seed_i += 1
	s = A.new_stage(int(U.get("seed", 1)) * 100 + stage * 10 + seed_i, params, stage)
	var v := clear()
	field = Field.new()
	field.g = self
	field.size_flags_vertical = Control.SIZE_EXPAND_FILL
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.custom_minimum_size = Vector2(A.W * 0.9, A.H * 0.9)
	v.add_child(field)
	playing = true
	acc = 0.0


func _process(delta: float) -> void:
	if not playing:
		return
	acc += delta
	var ax := Input.get_axis("ui_left", "ui_right") + (float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)))
	var ay := Input.get_axis("ui_up", "ui_down") + (float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W)))
	var dash := Input.is_key_pressed(KEY_SPACE)
	while acc >= A.DT and s["done"] == 0:
		acc -= A.DT
		A.step(s, ax, ay, dash)
		_events()
	field.queue_redraw()
	if s["done"] != 0:
		playing = false
		_stage_end()


func _events() -> void:
	for e in s["events"]:
		sfx({"hit": "hit", "pickup": "pickup", "win": "win", "lose": "lose", "pulse": "pulse", "dash": "click"}[e])


func _stage_end() -> void:
	total += s["score"]
	if s["won"] != 0:
		if stage >= 3:
			save["best"] = maxi(int(save.get("best", 0)), total)
			write_save()
			text_screen("The expedition is complete", "You crossed all three stages of %s.\nScore: %d\n\n%s" % [U.get("name", "?"), total, "Inspired by: " + ", ".join(PackedStringArray(U.get("inspirations", [])))], "Back to title", start)
		else:
			text_screen("Stage %d cleared" % stage, "Score so far: %d. The next stage is harder and the law grows stranger." % total, "Next stage", func(): stage += 1; begin_stage())
	else:
		text_screen("Stage %d failed" % stage, "You collected %d of %d shards. Score so far: %d." % [s["collected"], s["goal"], total], "Retry stage", func(): total -= s["score"]; begin_stage())


func draw_field(c: Control) -> void:
	var sz := c.size
	var k := minf(sz.x / A.W, sz.y / A.H)
	var off := (sz - Vector2(A.W, A.H) * k) / 2.0
	var P := func(x: float, y: float) -> Vector2: return off + Vector2(x, y) * k
	c.draw_rect(Rect2(off, Vector2(A.W, A.H) * k), pal[0].lightened(0.05))
	for i in range(0, 960, 80):
		c.draw_line(P.call(i, 0), P.call(i, A.H), pal[1], 1.0)
	for j in range(0, 600, 80):
		c.draw_line(P.call(0, j), P.call(A.W, j), pal[1], 1.0)
	var law: String = params["law"]
	if law == "wells":
		for w in s["wells"]:
			for r in [26.0, 18.0, 10.0]:
				c.draw_arc(P.call(w[0], w[1]), r * k, 0, TAU, 24, pal[1].lightened(0.4), 2.0)
	if law == "pulse":
		var period := int(110.0 / maxf(0.3, float(params["law_strength"])))
		c.draw_arc(P.call(A.W / 2, A.H / 2), float(s["t"] % period) / float(period) * 720.0 * k, 0, TAU, 64, pal[3], 3.0)
	if law == "drift":
		var wv := Vector2(cos(s["t"] * 0.021), sin(s["t"] * 0.017)) * 40.0
		c.draw_line(P.call(60, 60), P.call(60, 60) + wv, pal[3], 3.0)
	for sh in s["shards"]:
		var q: Vector2 = P.call(sh[0], sh[1])
		c.draw_colored_polygon(PackedVector2Array([q + Vector2(0, -12) * k, q + Vector2(9, 0) * k, q + Vector2(0, 12) * k, q + Vector2(-9, 0) * k]), pal[3])
	for h in s["hazards"]:
		c.draw_circle(P.call(h[0], h[1]), h[4] * k, pal[2])
	var pp: Vector2 = P.call(s["px"], s["py"])
	var dirv := Vector2(s["fx"], s["fy"])
	var col: Color = pal[4] if (s["inv"] == 0 or s["t"] % 4 < 2) else pal[1]
	c.draw_colored_polygon(PackedVector2Array([pp + dirv * 14 * k, pp + dirv.rotated(2.5) * 10 * k, pp + dirv.rotated(-2.5) * 10 * k]), col)
	c.draw_string(ThemeDB.fallback_font, off + Vector2(10, 22), "Stage %d   Shards %d/%d   Hearts %d   Time %d   Score %d" % [s["stage"], s["collected"], s["goal"], s["hp"], maxi(0, (s["limit"] - s["t"]) / 30), total + s["score"]], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, pal[4])


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	var res := {"ok": false}
	# a skilled bot plays the real game flow (stage objects, scoring) to the end, retrying failed stages like a player
	total = 0
	stage = 1
	var retries := 0
	var guard := 0
	while stage <= 3 and guard < 40:
		guard += 1
		begin_stage()
		await get_tree().process_frame
		playing = false
		while s["done"] == 0:
			var a := A.bot(s, 1)
			A.step(s, a[0], a[1], a[2])
		if guard == 1:
			field.queue_redraw()
			await get_tree().process_frame     # exercises the real _draw path
		if s["won"] != 0:
			total += s["score"]
			stage += 1
		else:
			retries += 1
	res["bot_completed_game"] = stage > 3
	res["retries"] = retries
	res["score"] = total
	var nov_clears := 0
	for i in 8:
		nov_clears += 1 if A.play_full(9000 + i, params, 0)["cleared"] == 3 else 0
	res["novice_full_clears_of_8"] = nov_clears
	res["audio_loaded"] = sfx_players["hit"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	save["best"] = maxi(int(save.get("best", 0)), total)
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	res["ok"] = res["bot_completed_game"] and nov_clears <= 3 and res["audio_loaded"] and res["save_written"]
	return res


func shot_prepare() -> void:
	begin_stage()
	for i in 90:
		var a := A.bot(s, 1)
		A.step(s, a[0], a[1], a[2])
	field.queue_redraw()
