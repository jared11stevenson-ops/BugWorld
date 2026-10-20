# Game: Expedition 3D. The same deterministic core as the 2D arcade, presented as a real-time 3D scene:
# procedural low-poly meshes, animated figure, emissive hazards, particles, camera shake. Logic is unchanged, so bot tests still apply.
extends "res://ghost/shell.gd"

const A = preload("res://ghost/arcade_core.gd")
const D = preload("res://data/arcade.gd")
const SC := 0.05

var s: Dictionary
var params: Dictionary
var stage := 1
var total := 0
var playing := false
var acc := 0.0
var seed_i := 1
var vp: SubViewport
var world: Node3D
var cam: Camera3D
var hud: Label
var player: Node3D
var limb_l: Node3D
var limb_r: Node3D
var head: MeshInstance3D
var haz_nodes: Array = []
var shard_nodes: Array = []
var zone_nodes: Array = []
var well_nodes: Array = []
var ring: MeshInstance3D
var fire_lo: MeshInstance3D
var fire_hi: MeshInstance3D
var t_anim := 0.0
var shake := 0.0
var last_hp := 3


func start() -> void:
	game_id = "arcade3d"
	playing = false
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	title_screen(U.get("game_title", "Expedition 3D"), "Arrow keys / WASD to move, SPACE to dash.\n" + universe_line() + "\nBest score: %d" % int(save.get("best", 0)), [["Play", intro], ["Controls & rules", help]])


func help() -> void:
	text_screen("Controls & rules", "Move with arrow keys or WASD. SPACE dashes (brief invulnerability, short cooldown). Collect the glowing crystals to clear a stage before time runs out. Three hearts per stage.\nLaw of this universe: %s" % U.get("law_text", ""), "Back", start)


func intro() -> void:
	total = 0
	stage = 1
	text_screen("The law of %s" % U.get("name", "this world"), "\n\n".join(PackedStringArray(U.get("lore", {}).get("prologue", [U.get("law_text", "")]))), "Enter stage 1", begin_stage)


# ---------------------------------------------------------------- 3D construction
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


func mesh_node(m: Mesh, material: Material, parent: Node3D, pos := Vector3.ZERO) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	n.mesh = m
	n.material_override = material
	n.position = pos
	parent.add_child(n)
	return n


func wp(x: float, y: float) -> Vector3:
	return Vector3((x - A.W / 2.0) * SC, 0.0, (y - A.H / 2.0) * SC)


func build_world() -> void:
	world = Node3D.new()
	vp.add_child(world)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = pal[0].darkened(0.3)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = pal[1].lightened(0.5)
	env.ambient_light_energy = 0.9
	env.fog_enabled = true
	env.fog_light_color = pal[0]
	env.fog_density = 0.012
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, 35, 0)
	sun.light_energy = 1.1
	sun.light_color = pal[4]
	world.add_child(sun)
	cam = Camera3D.new()
	cam.position = Vector3(0, 36, 25)
	cam.fov = 45
	world.add_child(cam)
	cam.look_at(Vector3(0, 0, 1.5), Vector3.UP)
	var pm := PlaneMesh.new()
	pm.size = Vector2(A.W * SC + 8.0, A.H * SC + 8.0)
	mesh_node(pm, mat(pal[1].darkened(0.25)), world)
	var rnd := RandomNumberGenerator.new()
	rnd.seed = int(U.get("seed", 1)) + 17
	for i in range(-12, 13, 4):       # grid
		var bx := BoxMesh.new()
		bx.size = Vector3(0.06, 0.02, A.H * SC)
		mesh_node(bx, mat(pal[1].lightened(0.2)), world, Vector3(i * 2.0, 0.02, 0))
	for j in range(-8, 9, 4):
		var bz := BoxMesh.new()
		bz.size = Vector3(A.W * SC, 0.02, 0.06)
		mesh_node(bz, mat(pal[1].lightened(0.2)), world, Vector3(0, 0.02, j * 2.0))
	for i in 46:                      # procedural skyline around the arena
		var h := 1.5 + rnd.randf() * 5.5
		var ang := TAU * i / 46.0
		var rr := 1.0 + rnd.randf() * 0.12
		var bm := BoxMesh.new()
		bm.size = Vector3(1.4 + rnd.randf() * 1.8, h, 1.4 + rnd.randf() * 1.8)
		var px := cos(ang) * (A.W * SC / 2.0 + 4.0) * rr * 1.08
		var pz := sin(ang) * (A.H * SC / 2.0 + 3.5) * rr * 1.2
		var b := mesh_node(bm, mat(pal[1].lightened(0.05 + rnd.randf() * 0.2)), world, Vector3(px, h / 2.0, pz))
		if rnd.randf() < 0.5:
			var roof := PrismMesh.new()
			roof.size = Vector3(bm.size.x, 1.0, bm.size.z)
			mesh_node(roof, mat(pal[2].darkened(0.4)), world, Vector3(px, h + 0.5, pz))
	# player: capsule body, sphere head, swinging limbs, glow
	player = Node3D.new()
	player.scale = Vector3.ONE * 1.6
	world.add_child(player)
	var cap := CapsuleMesh.new()
	cap.radius = 0.35
	cap.height = 1.3
	mesh_node(cap, mat(pal[4]), player, Vector3(0, 0.85, 0))
	var hs := SphereMesh.new()
	hs.radius = 0.3
	hs.height = 0.6
	head = mesh_node(hs, mat(pal[3], 0.4), player, Vector3(0, 1.8, 0))
	limb_l = Node3D.new()
	limb_l.position = Vector3(-0.45, 1.3, 0)
	player.add_child(limb_l)
	limb_r = Node3D.new()
	limb_r.position = Vector3(0.45, 1.3, 0)
	player.add_child(limb_r)
	for L in [limb_l, limb_r]:
		var lb := BoxMesh.new()
		lb.size = Vector3(0.2, 0.7, 0.2)
		mesh_node(lb, mat(pal[4].darkened(0.1)), L, Vector3(0, -0.3, 0))
	var glow := OmniLight3D.new()
	glow.light_color = pal[4]
	glow.light_energy = 1.6
	glow.omni_range = 6.0
	glow.position = Vector3(0, 2.0, 0)
	player.add_child(glow)
	# law visuals
	var law: String = params["law"]
	if law == "pulse":
		var tm := TorusMesh.new()
		tm.inner_radius = 0.9
		tm.outer_radius = 1.0
		ring = mesh_node(tm, mat(pal[3], 2.0), world, Vector3(0, 0.15, 0))
	if law == "purge":
		var fm := BoxMesh.new()
		fm.size = Vector3(0.7, 3.0, 1.0)
		fire_lo = mesh_node(fm, mat(Color(1.0, 0.45, 0.1), 2.5), world)
		fire_hi = mesh_node(fm, mat(Color(1.0, 0.45, 0.1), 2.5), world)
	if law == "wells":
		for w in s["wells"]:
			var n := Node3D.new()
			world.add_child(n)
			n.position = wp(w[0], w[1])
			var sm := SphereMesh.new()
			sm.radius = 0.8
			sm.height = 1.6
			mesh_node(sm, mat(Color(0.02, 0.02, 0.05)), n, Vector3(0, 0.8, 0))
			var tm2 := TorusMesh.new()
			tm2.inner_radius = 1.4
			tm2.outer_radius = 1.7
			mesh_node(tm2, mat(pal[3], 1.5), n, Vector3(0, 0.8, 0))
			well_nodes.append(n)


func begin_stage() -> void:
	seed_i += 1
	s = A.new_stage(int(U.get("seed", 1)) * 100 + stage * 10 + seed_i, params, stage)
	last_hp = 3
	var v := clear()
	var svc := SubViewportContainer.new()
	svc.stretch = true
	svc.custom_minimum_size = Vector2(A.W * 0.9, A.H * 0.9)
	svc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	svc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(svc)
	vp = SubViewport.new()
	vp.size = Vector2i(int(A.W * 0.9), int(A.H * 0.9))
	svc.add_child(vp)
	haz_nodes.clear()
	shard_nodes.clear()
	zone_nodes.clear()
	well_nodes.clear()
	ring = null
	fire_lo = null
	fire_hi = null
	build_world()
	hud = Label.new()
	hud.position = Vector2(12, 8)
	hud.add_theme_font_size_override("font_size", 20)
	svc.add_child(hud)
	sync_view()
	playing = true
	acc = 0.0


func _process(delta: float) -> void:
	if not playing:
		return
	t_anim += delta
	acc += delta
	var ax := Input.get_axis("ui_left", "ui_right") + (float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)))
	var ay := Input.get_axis("ui_up", "ui_down") + (float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W)))
	var dash := Input.is_key_pressed(KEY_SPACE)
	while acc >= A.DT and s["done"] == 0:
		acc -= A.DT
		A.step(s, ax, ay, dash)
		_events()
	sync_view()
	if s["done"] != 0:
		playing = false
		_stage_end()


func _events() -> void:
	for e in s["events"]:
		sfx({"hit": "hit", "pickup": "pickup", "win": "win", "lose": "lose", "pulse": "pulse", "dash": "step"}[e])
		if e == "hit":
			shake = 0.6
		if e == "pickup":
			burst(wp(s["px"], s["py"]), pal[3])
		if e == "dash":
			burst(wp(s["px"], s["py"]), pal[4])


func burst(pos: Vector3, c: Color) -> void:
	var p := CPUParticles3D.new()
	p.position = pos + Vector3(0, 0.8, 0)
	p.amount = 18
	p.one_shot = true
	p.explosiveness = 1.0
	p.lifetime = 0.6
	p.direction = Vector3.UP
	p.spread = 80.0
	p.initial_velocity_min = 3.0
	p.initial_velocity_max = 6.0
	p.gravity = Vector3(0, -9, 0)
	var sm := SphereMesh.new()
	sm.radius = 0.08
	sm.height = 0.16
	p.mesh = sm
	p.material_override = mat(c, 2.0)
	world.add_child(p)
	p.emitting = true
	get_tree().create_timer(1.0).timeout.connect(func(): if is_instance_valid(p): p.queue_free())


func _pool(arr: Array, count: int, maker: Callable) -> void:
	while arr.size() < count:
		arr.append(maker.call())
	while arr.size() > count:
		var n = arr.pop_back()
		n.queue_free()


func sync_view() -> void:
	if world == null or s.is_empty():
		return
	var law: String = params["law"]
	var spd := sqrt(s["vx"] * s["vx"] + s["vy"] * s["vy"])
	player.position = wp(s["px"], s["py"]) + Vector3(0, absf(sin(t_anim * 12.0)) * 0.12 * clampf(spd / 200.0, 0.0, 1.0), 0)
	player.rotation.y = atan2(float(s["fx"]), float(s["fy"]))
	var swing := sin(t_anim * 12.0) * clampf(spd / 200.0, 0.0, 1.0) * 0.9
	limb_l.rotation.x = swing
	limb_r.rotation.x = -swing
	player.visible = s["inv"] == 0 or int(s["t"]) % 4 < 2
	head.scale = Vector3.ONE * (1.0 + 0.1 * sin(t_anim * 3.0))
	_pool(haz_nodes, s["hazards"].size(), func():
		var n := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 1.0
		sm.height = 2.0
		n.mesh = sm
		n.material_override = mat(pal[2].darkened(0.25), 0.55)
		world.add_child(n)
		return n)
	for i in s["hazards"].size():
		var h: Array = s["hazards"][i]
		haz_nodes[i].position = wp(h[0], h[1]) + Vector3(0, 0.7, 0)
		haz_nodes[i].scale = Vector3.ONE * float(h[4]) * SC * 2.2 * (1.0 + 0.12 * sin(t_anim * 8.0 + i))
	_pool(shard_nodes, s["shards"].size(), func():
		var n := Node3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.7, 0.7, 0.7)
		var m1 := mesh_node(bm, mat(pal[3], 2.0), n)
		m1.rotation_degrees = Vector3(45, 0, 45)
		var l := OmniLight3D.new()
		l.light_color = pal[3]
		l.light_energy = 1.2
		l.omni_range = 4.0
		n.add_child(l)
		world.add_child(n)
		return n)
	for i in s["shards"].size():
		var sh: Array = s["shards"][i]
		shard_nodes[i].position = wp(sh[0], sh[1]) + Vector3(0, 1.0 + 0.25 * sin(t_anim * 3.0 + i), 0)
		shard_nodes[i].rotation.y = t_anim * 1.8 + i
	if law == "contagion":
		_pool(zone_nodes, s["zones"].size(), func():
			var cm := CylinderMesh.new()
			cm.top_radius = 1.0
			cm.bottom_radius = 1.0
			cm.height = 0.25
			var n := mesh_node(cm, mat(pal[2], 1.4, 0.55), world)
			return n)
		for i in s["zones"].size():
			var z: Array = s["zones"][i]
			zone_nodes[i].position = wp(z[0], z[1]) + Vector3(0, 0.15, 0)
			zone_nodes[i].scale = Vector3(float(z[2]) * SC, 1.0 + 0.3 * sin(t_anim * 4.0 + i), float(z[2]) * SC)
	if law == "pulse" and ring != null:
		var r := float(int(s["t"]) % int(110.0 / maxf(0.3, float(params["law_strength"])))) / (110.0 / maxf(0.3, float(params["law_strength"]))) * 720.0 * SC
		ring.scale = Vector3(r, 1.0, r)
	if law == "purge" and fire_lo != null:
		var gx: float = (float(s["fire_x"]) - A.W / 2.0) * SC
		var gy: float = (float(s["gap_y"]) - A.H / 2.0) * SC
		var half := A.H * SC / 2.0
		var gap_half := 70.0 * SC
		var lo_len := maxf(0.1, (gy - gap_half) - (-half))
		var hi_len := maxf(0.1, half - (gy + gap_half))
		fire_lo.scale = Vector3(1.0, 1.0 + 0.2 * sin(t_anim * 9.0), lo_len)
		fire_lo.position = Vector3(gx, 1.5, -half + lo_len / 2.0)
		fire_hi.scale = Vector3(1.0, 1.0 + 0.2 * sin(t_anim * 9.0 + 2.0), hi_len)
		fire_hi.position = Vector3(gx, 1.5, half - hi_len / 2.0)
	for i in well_nodes.size():
		well_nodes[i].rotation.y = t_anim * (1.0 + 0.3 * i)
	shake = maxf(0.0, shake - 0.03)
	cam.position = Vector3(sin(t_anim * 70.0) * shake, 36 + cos(t_anim * 63.0) * shake, 25)
	hud.text = "Stage %d   Crystals %d/%d   Hearts %d   Time %d   Score %d" % [s["stage"], s["collected"], s["goal"], s["hp"], maxi(0, (s["limit"] - s["t"]) / 30), total + s["score"]]
	hud.add_theme_color_override("font_color", pal[4])


func _stage_end() -> void:
	total += s["score"]
	if s["won"] != 0:
		if stage >= 3:
			save["best"] = maxi(int(save.get("best", 0)), total)
			write_save()
			end_screen("The expedition is complete", "You crossed all three stages of %s.\nScore: %d\n\n%s" % [U.get("name", "?"), total, U.get("lore", {}).get("epilogue_win", "")], {"score": total, "stages": 3}, "Back to title", start)
		else:
			text_screen("Stage %d cleared" % stage, "Score so far: %d. The next stage is harder and the law grows stranger." % total, "Next stage", func(): stage += 1; begin_stage())
	else:
		text_screen("Stage %d failed" % stage, "You collected %d of %d crystals. Score so far: %d." % [s["collected"], s["goal"], total], "Retry stage", func(): total -= s["score"]; begin_stage())


# ---------------------------------------------------------------- headless verification
func selftest() -> Dictionary:
	params = A.defaults()
	for k in D.DATA["params"]:
		params[k] = D.DATA["params"][k]
	var res := {"ok": false}
	total = 0
	stage = 1
	var retries := 0
	var guard := 0
	var view_ok := true
	while stage <= 3 and guard < 40:
		guard += 1
		begin_stage()
		await get_tree().process_frame
		playing = false
		var n := 0
		while s["done"] == 0:
			var a := A.bot(s, 1)
			A.step(s, a[0], a[1], a[2])
			n += 1
			if n % 7 == 0:
				t_anim += 0.2
				sync_view()
				view_ok = view_ok and haz_nodes.size() == s["hazards"].size() and shard_nodes.size() == s["shards"].size() and (params["law"] != "contagion" or zone_nodes.size() == s["zones"].size())
		if s["won"] != 0:
			total += s["score"]
			stage += 1
		else:
			retries += 1
	res["bot_completed_game"] = stage > 3
	res["retries"] = retries
	res["score"] = total
	res["view_matches_state"] = view_ok
	var nov := 0
	for i in 8:
		nov += 1 if A.play_full(9000 + i, params, 0)["cleared"] == 3 else 0
	res["novice_full_clears_of_8"] = nov
	res["audio_loaded"] = sfx_players["hit"].stream.data.size() > 500 and music_player.stream.data.size() > 10000
	write_save()
	res["save_written"] = FileAccess.file_exists(SAVE_PATH)
	rate_run(4, {"selftest": true})
	res["feedback_written"] = FileAccess.file_exists(FEEDBACK_PATH)
	res["ok"] = res["bot_completed_game"] and view_ok and nov <= 3 and res["audio_loaded"] and res["save_written"] and res["feedback_written"]
	return res


func shot_prepare() -> void:
	begin_stage()
	for i in 80:
		var a := A.bot(s, 1)
		A.step(s, a[0], a[1], a[2])
		t_anim += 0.05
	sync_view()
