# Game: Volley. A three-round volleyball tournament on a 3D beach. Deterministic core, tiered AI, procedural low-poly scene.
extends "res://ghost/shell.gd"

const V = preload("res://ghost/volley_core.gd")
const D = preload("res://data/volley.gd")
const SC := 0.02

var s: Dictionary
var params: Dictionary
var round_i := 0
var attempt := 0
var playing := false
var acc := 0.0
var t_anim := 0.0
var vp: SubViewport
var world: Node3D
var cam: Camera3D
var hud: Label
var big: Label
var pnode: Array = []
var limbs: Array = []
var ball: Node3D
var ball_ring: MeshInstance3D
var shadows: Array = []
var ball_shadow: MeshInstance3D
var shake := 0.0
var ai_params: Array = []
var match_log: Array = []
var testing := false
var wins := 0


func start() -> void:
	game_id = "volley"
	playing = false
	params = V.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in ["slick", "points", "ai_lag", "serve_pause", "max_ticks", "ball", "net", "score"]:
		params[k] = int(params[k])
	title_screen(U.get("game_title", "Volley"), "A tournament of three matches.\nMove: A/D or arrows   Jump / spike: W, Up or Space\n" + universe_line(), [["Play", intro], ["How to play", help]])


func help() -> void:
	text_screen("How to play", "First to %d points wins the match (a point every rally). Each side may touch the ball at most 3 times. Stand slightly behind the ball so your hit pushes it toward the net; jump to spike.\nLaw of this universe: %s" % [int(params["points"]), U.get("law_text", "")], "Back", start)


func intro() -> void:
	round_i = 0
	wins = 0
	text_screen("The tournament of %s" % U.get("name", "this world"), "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", []))) + "\n\n" + rival_line(0) + " · " + rival_line(1) + " · " + rival_line(2), "Walk onto the sand", begin_match)


func round_ai(r: int) -> Array:
	var lag := int(params["ai_lag"])
	var err := float(params["ai_err"])
	var ag := float(params["ai_aggr"])
	var m: Dictionary = rival(r)["mod"]
	err = maxf(0.0, err + float(m["err"]))
	ag = clampf(ag + float(m["aggr"]), 0.05, 1.0)
	var out := [lag, err, ag]
	if r == 0:
		out = [lag + 8, err * 1.8, ag * 0.7]
	elif r == 2:
		out = [maxi(2, lag / 2), err * 0.4, minf(1.0, ag * 1.25)]
	out[1] = float("%.4f" % float(out[1]))      # decimal-stable values: the recorded twin (JSON) must replay the exact AI that was played
	out[2] = float("%.4f" % float(out[2]))
	return out


# ---------------------------------------------------------------- 3D scene
func mat(c: Color, emit := 0.0, alpha := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(c.r, c.g, c.b, alpha)
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emit
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m


func mnode(m: Mesh, material: Material, parent: Node3D, pos := Vector3.ZERO) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	n.mesh = m
	n.material_override = material
	n.position = pos
	parent.add_child(n)
	return n


func wpos(x: float, y: float) -> Vector3:
	return Vector3((x - 500.0) * SC, (V.GROUND - y) * SC, 0.0)


func build_scene() -> void:
	world = Node3D.new()
	vp.add_child(world)
	var sand := Color(0.82, 0.70, 0.46).lerp(pal[2], 0.12)             # sand stays sand-coloured; palette only tints it
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = pal[0].lerp(Color(0.55, 0.78, 0.95), 0.55)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 0.5
	env.fog_enabled = true
	env.fog_light_color = env.background_color
	env.fog_density = 0.01
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -25, 0)
	sun.light_energy = 0.85
	world.add_child(sun)
	cam = Camera3D.new()
	cam.position = Vector3(0, 4.2, 17)
	cam.fov = 48
	world.add_child(cam)
	cam.look_at(Vector3(0, 3.0, 0), Vector3.UP)
	var pm := PlaneMesh.new()
	pm.size = Vector2(60, 40)
	mnode(pm, mat(sand), world, Vector3(0, 0, 0))
	var sea := PlaneMesh.new()
	sea.size = Vector2(120, 40)
	mnode(sea, mat(pal[3].darkened(0.1).lerp(Color(0.1, 0.4, 0.7), 0.5), 0.3, 0.9), world, Vector3(0, -0.05, -26))
	for x in [-10.0, 0.0, 10.0]:     # court lines
		var lb := BoxMesh.new()
		lb.size = Vector3(0.08, 0.02, 6.0)
		mnode(lb, mat(Color.WHITE), world, Vector3(x, 0.02, 0))
	for z in [-3.0, 3.0]:
		var lb2 := BoxMesh.new()
		lb2.size = Vector3(20.0, 0.02, 0.08)
		mnode(lb2, mat(Color.WHITE), world, Vector3(0, 0.02, z))
	var net_h := (V.GROUND - V.NET_TOP) * SC
	for z in [-3.0, 3.0]:
		var post := CylinderMesh.new()
		post.top_radius = 0.07
		post.bottom_radius = 0.07
		post.height = net_h + 0.3
		mnode(post, mat(pal[4].darkened(0.3)), world, Vector3(0, (net_h + 0.3) / 2.0, z))
	var netm := BoxMesh.new()
	netm.size = Vector3(0.04, net_h, 6.0)
	mnode(netm, mat(Color(1, 1, 1), 0.3, 0.6), world, Vector3(0, net_h / 2.0, 0))
	var topb := BoxMesh.new()
	topb.size = Vector3(0.08, 0.08, 6.0)
	mnode(topb, mat(Color.WHITE), world, Vector3(0, net_h, 0))
	var rnd := RandomNumberGenerator.new()
	rnd.seed = int(U.get("seed", 1)) + 5
	for i in 18:                      # beach props: palms (trunk + fronds), umbrellas, dunes
		var x := -24.0 + rnd.randf() * 48.0
		var z := -9.0 - rnd.randf() * 8.0
		if rnd.randf() < 0.5:
			var tr := CylinderMesh.new()
			tr.top_radius = 0.12
			tr.bottom_radius = 0.2
			tr.height = 3.0 + rnd.randf() * 2.0
			var tn := mnode(tr, mat(Color(0.45, 0.3, 0.18)), world, Vector3(x, tr.height / 2.0, z))
			tn.rotation.z = (rnd.randf() - 0.5) * 0.3
			for k in 5:
				var fr := PrismMesh.new()
				fr.size = Vector3(0.3, 1.6, 0.05)
				var fn := mnode(fr, mat(pal[3].darkened(0.2)), world, Vector3(x, tr.height + 0.1, z))
				fn.rotation = Vector3(1.2, k * TAU / 5.0, 0)
		else:
			var um := CylinderMesh.new()
			um.top_radius = 0.01
			um.bottom_radius = 1.2
			um.height = 0.6
			mnode(um, mat(pal[2 + (i % 2)]), world, Vector3(x, 2.0, z))
			var up := CylinderMesh.new()
			up.top_radius = 0.03
			up.bottom_radius = 0.03
			up.height = 2.0
			mnode(up, mat(Color(0.9, 0.9, 0.9)), world, Vector3(x, 1.0, z))
	for i in 2:                       # players
		var n := Node3D.new()
		world.add_child(n)
		var body := CapsuleMesh.new()
		body.radius = 0.45
		body.height = 1.5
		mnode(body, mat(pal[3] if i == 0 else pal[2]), n, Vector3(0, 0.75, 0))
		var hd := SphereMesh.new()
		hd.radius = 0.32
		hd.height = 0.64
		mnode(hd, mat(Color(0.95, 0.8, 0.65)), n, Vector3(0, 1.75, 0))
		var arms := []
		for sx in [-0.55, 0.55]:
			var pivot := Node3D.new()
			pivot.position = Vector3(sx, 1.35, 0)
			n.add_child(pivot)
			var ab := BoxMesh.new()
			ab.size = Vector3(0.2, 0.75, 0.2)
			mnode(ab, mat(Color(0.95, 0.8, 0.65)), pivot, Vector3(0, -0.3, 0))
			arms.append(pivot)
		limbs.append(arms)
		pnode.append(n)
		var sh := CylinderMesh.new()
		sh.top_radius = 0.7
		sh.bottom_radius = 0.7
		sh.height = 0.02
		shadows.append(mnode(sh, mat(Color(0, 0, 0), 0.0, 0.35), world, Vector3(0, 0.03, 0)))
	ball = Node3D.new()
	world.add_child(ball)
	var bs := SphereMesh.new()
	bs.radius = V.BR * SC * 1.5
	bs.height = V.BR * SC * 3.0
	mnode(bs, mat(pal[4], 0.5), ball)
	var rg := TorusMesh.new()
	rg.inner_radius = V.BR * SC * 1.5
	rg.outer_radius = V.BR * SC * 1.62
	ball_ring = mnode(rg, mat(pal[2], 1.0), ball)
	var bsh := CylinderMesh.new()
	bsh.top_radius = 0.35
	bsh.bottom_radius = 0.35
	bsh.height = 0.02
	ball_shadow = mnode(bsh, mat(Color(0, 0, 0), 0.0, 0.4), world, Vector3(0, 0.03, 0))


func begin_match() -> void:
	attempt += 1
	ai_params = round_ai(round_i)
	s = V.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, params)
	var v := clear()
	var svc := SubViewportContainer.new()
	svc.stretch = true
	svc.custom_minimum_size = Vector2(900, 520)
	svc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	svc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(svc)
	vp = SubViewport.new()
	vp.size = Vector2i(900, 520)
	svc.add_child(vp)
	pnode.clear()
	limbs.clear()
	shadows.clear()
	build_scene()
	hud = Label.new()
	hud.position = Vector2(14, 10)
	hud.add_theme_font_size_override("font_size", 22)
	hud.add_theme_color_override("font_color", Color.WHITE)
	hud.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	hud.add_theme_constant_override("outline_size", 6)
	svc.add_child(hud)
	big = Label.new()
	big.position = Vector2(330, 200)
	big.add_theme_font_size_override("font_size", 56)
	big.add_theme_color_override("font_color", Color.WHITE)
	big.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	big.add_theme_constant_override("outline_size", 10)
	svc.add_child(big)
	sync_view()
	playing = true
	acc = 0.0


func _process(delta: float) -> void:
	if not playing:
		return
	t_anim += delta
	acc += minf(delta, 0.1)
	var dir := int(Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT)) - int(Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT))
	var jump := Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_SPACE)
	while acc >= 1.0 / 60.0 and s["over"] == 0:
		acc -= 1.0 / 60.0
		V.step(s, [dir, jump], V.ai_input(s, 1, ai_params))
		_events()
	sync_view()
	if s["over"] != 0:
		playing = false
		_match_end()


func _events() -> void:
	for e in s["events"]:
		match e:
			"hit":
				sfx("hit")
				burst(wpos(s["bx"], s["by"]), pal[4])
			"jump":
				sfx("step")
			"point":
				sfx("cure")
				shake = 0.5
				burst(wpos(s["bx"], V.GROUND - 10.0), pal[3])


func burst(pos: Vector3, c: Color) -> void:
	var p := CPUParticles3D.new()
	p.position = pos
	p.amount = 14
	p.one_shot = true
	p.explosiveness = 1.0
	p.lifetime = 0.5
	p.direction = Vector3.UP
	p.spread = 70.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 5.0
	p.gravity = Vector3(0, -9, 0)
	var sm := SphereMesh.new()
	sm.radius = 0.07
	sm.height = 0.14
	p.mesh = sm
	p.material_override = mat(c, 1.5)
	world.add_child(p)
	p.emitting = true
	get_tree().create_timer(0.9).timeout.connect(func(): if is_instance_valid(p): p.queue_free())


func sync_view() -> void:
	if world == null or s.is_empty():
		return
	for i in 2:
		var jumping: bool = s["py"][i] < V.GROUND - 1.0
		pnode[i].position = Vector3((s["px"][i] - 500.0) * SC, (V.GROUND - s["py"][i]) * SC, (-0.6 if i == 0 else 0.6))
		pnode[i].rotation.y = 0.0 if i == 0 else PI
		var st: float = 1.0 + clampf(-s["pvy"][i] * 0.025, -0.15, 0.25) if jumping else 1.0 + 0.04 * sin(t_anim * 6.0)
		pnode[i].scale = Vector3(1.0 / sqrt(st), st, 1.0 / sqrt(st))
		var swing := (2.6 if jumping else 0.3 * sin(t_anim * 8.0 + i)) * (-1.0 if i == 0 else -1.0)
		limbs[i][0].rotation.x = swing
		limbs[i][1].rotation.x = swing
		shadows[i].position = Vector3((s["px"][i] - 500.0) * SC, 0.03, (-0.6 if i == 0 else 0.6))
		shadows[i].scale = Vector3.ONE * (1.0 - clampf((V.GROUND - s["py"][i]) * 0.002, 0.0, 0.5))
	ball.position = Vector3((s["bx"] - 500.0) * SC, (V.GROUND - s["by"]) * SC, 0.0)
	ball.rotation.z -= float(s["bvx"]) * 0.03
	ball_shadow.position = Vector3((s["bx"] - 500.0) * SC, 0.04, 0.0)
	ball_shadow.scale = Vector3.ONE * (1.0 - clampf((V.GROUND - s["by"]) * 0.0015, 0.0, 0.6))
	shake = maxf(0.0, shake - 0.03)
	cam.position = Vector3(sin(t_anim * 60.0) * shake * 0.3, 4.2 + cos(t_anim * 50.0) * shake * 0.2, 17)
	hud.text = "Round %d/3      You %d  -  %d  Rival      touches %d/3" % [round_i + 1, s["score"][0], s["score"][1], s["touches"] if s["last_side"] == 0 else 0]
	big.text = "SERVE" if s["pause"] > 20 else ""


func _match_end() -> void:
	var won: bool = s["winner"] == 0
	sfx("win" if won else "lose")
	match_log.append({"seed": int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, "won": won, "score": [s["score"][0], s["score"][1]], "ticks": s["t"]})
	if testing:
		return
	if won:
		wins += 1
		round_i += 1
		save["best"] = maxi(int(save.get("best", 0)), round_i)
		write_save()
		if round_i >= 3:
			end_screen("Champion of %s" % U.get("name", "the beach"), "%d - %d in the final.\n\n%s" % [s["score"][0], s["score"][1], U.get("lore", {}).get("epilogue_win", "")], {"won": true, "rounds": 3, "attempts": attempt}, "Back to title", start)
		else:
			text_screen("Match won", "%d - %d. The next rival plays %s." % [s["score"][0], s["score"][1], "faster and sharper" if round_i == 2 else "like a local"], "Next match", begin_match)
	else:
		text_screen("Match lost", "%d - %d. Watch where the ball will land and stand a little behind it." % [s["score"][0], s["score"][1]], "Rematch", begin_match)


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	testing = true
	params = V.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	for k in ["slick", "points", "ai_lag", "serve_pause", "max_ticks", "ball", "net", "score"]:
		params[k] = int(params[k])
	var res := {"ok": false}
	# 1) an expert bot plays the whole tournament through the game's own match setup and 3D view
	round_i = 0
	var view_ok := true
	var guard := 0
	var twin := {}
	while round_i < 3 and guard < 30:
		guard += 1
		begin_match()
		await get_tree().process_frame
		playing = false
		s = V.new_match(int(U.get("seed", 1)) * 100 + round_i * 10 + attempt, params)      # the frame above may have stepped the live match: replay from a clean state
		var n := 0
		var ai := ai_params
		while s["over"] == 0:
			V.step(s, V.ai_input(s, 0, V.level_params(2)), V.ai_input(s, 1, ai))
			n += 1
			if n % 40 == 0:
				t_anim += 0.2
				sync_view()
		_match_end()
		if s["winner"] == 0:
			if round_i == 1 and twin.is_empty():
				twin = {"seed": int(U.get("seed", 1)) * 100 + 1 * 10 + attempt, "left_level": 2, "right": ai, "digest": V.digest(s), "ticks": s["t"], "score": [s["score"][0], s["score"][1]]}
			round_i += 1
	res["tournament_completed"] = round_i >= 3
	res["matches_played"] = match_log.size()
	res["twin"] = twin
	# 2) a novice must not beat the tuned AI
	var nov := 0
	for i in 10:
		nov += 1 if V.play(9000 + i, params, 0, round_ai(1))["winner"] == 0 else 0
	res["novice_wins_of_10"] = nov
	# 3) performance budget
	var t0 := Time.get_ticks_usec()
	var s2 := V.new_match(5, params)
	for i in 1200:
		V.step(s2, V.ai_input(s2, 0, V.level_params(1)), V.ai_input(s2, 1, V.level_params(1)))
		if s2["over"] != 0:
			s2 = V.new_match(6 + i, params)
	res["perf_step_us"] = float(Time.get_ticks_usec() - t0) / 1200.0
	res["audio_loaded"] = sfx_players["hit"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["tournament_completed"] and nov <= 2 and res["audio_loaded"] and res["save_written"] and res["feedback_written"] and not twin.is_empty()
	return res


func shot_prepare() -> void:
	begin_match()
	for i in 150:
		V.step(s, V.ai_input(s, 0, V.level_params(1)), V.ai_input(s, 1, ai_params))
		if i % 10 == 0:
			t_anim += 0.15
	sync_view()
