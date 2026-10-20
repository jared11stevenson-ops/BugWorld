# Deterministic fixed-step core of the arcade game (30 ticks/s). Pure logic: no nodes, so bots can play it headless.
# The universe's physical law (drift / wells / pulse) changes the forces.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const W := 960.0
const H := 600.0
const DT := 1.0 / 30.0
const ACC := 700.0
const MAXV := 290.0


static func defaults() -> Dictionary:
	return {"law": "drift", "law_strength": 1.0, "spawn_every": 14, "spawn_step": 3, "hazard_speed": 150.0, "goal": 4, "stage_secs": 32.0, "max_hazards": 22}


static func fr(s: Dictionary) -> float:
	return float(K.rnd(s, 10000)) / 10000.0


static func new_stage(seed_in: int, p: Dictionary, stage: int) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "t": 0, "px": W / 2, "py": H / 2, "vx": 0.0, "vy": 0.0, "hp": 3, "inv": 0, "dash_cd": 0,
		"shards": [], "hazards": [], "wells": [], "collected": 0, "stage": stage, "done": 0, "won": 0, "p": p, "score": 0,
		"goal": int(p["goal"]) + (stage - 1) * 2, "limit": int(float(p["stage_secs"]) * 30.0), "events": [],
		"spawn_every": maxi(6, int(p["spawn_every"]) - (stage - 1) * int(p["spawn_step"])), "speed": float(p["hazard_speed"]) * (1.0 + 0.2 * (stage - 1)),
		"fx": 0.0, "fy": -1.0, "zones": [], "fire_x": -100.0, "gap_y": H / 2}
	for i in 2 + (stage - 1):
		s["wells"].append([120.0 + fr(s) * (W - 240.0), 100.0 + fr(s) * (H - 200.0)])
	return s


static func step(s: Dictionary, ax: float, ay: float, dash: bool) -> void:
	if s["done"] != 0:
		return
	s["events"] = []
	var p: Dictionary = s["p"]
	var law: String = p["law"]
	var st: float = float(p["law_strength"])
	s["t"] += 1
	var t: int = s["t"]
	var len2 := ax * ax + ay * ay
	if len2 > 0.0001:
		var l := sqrt(len2)
		ax /= l
		ay /= l
		s["fx"] = ax
		s["fy"] = ay
	else:
		ax = 0.0
		ay = 0.0
	s["vx"] += ax * ACC * DT
	s["vy"] += ay * ACC * DT
	if dash and s["dash_cd"] == 0:
		s["vx"] += s["fx"] * 430.0
		s["vy"] += s["fy"] * 430.0
		s["inv"] = maxi(s["inv"], 9)
		s["dash_cd"] = 40
		s["events"].append("dash")
	var wind := Vector2.ZERO
	if law == "drift":
		wind = Vector2(cos(t * 0.021), sin(t * 0.017)) * 150.0 * st
	s["vx"] += wind.x * DT
	s["vy"] += wind.y * DT
	if law == "wells":
		for w in s["wells"]:
			var dx: float = w[0] - s["px"]
			var dy: float = w[1] - s["py"]
			var d2 := dx * dx + dy * dy + 900.0
			var f := 2600000.0 * st / d2
			s["vx"] += dx / sqrt(d2) * f * DT * 0.35
			s["vy"] += dy / sqrt(d2) * f * DT * 0.35
			if d2 < 1500.0 and s["inv"] == 0:
				_hit(s)
	s["vx"] *= 0.93
	s["vy"] *= 0.93
	var sp := sqrt(s["vx"] * s["vx"] + s["vy"] * s["vy"])
	if sp > MAXV and s["dash_cd"] < 30:
		s["vx"] *= MAXV / sp
		s["vy"] *= MAXV / sp
	s["px"] += s["vx"] * DT
	s["py"] += s["vy"] * DT
	if s["px"] < 12.0 or s["px"] > W - 12.0:
		s["vx"] = -s["vx"] * 0.5
		s["px"] = clampf(s["px"], 12.0, W - 12.0)
	if s["py"] < 12.0 or s["py"] > H - 12.0:
		s["vy"] = -s["vy"] * 0.5
		s["py"] = clampf(s["py"], 12.0, H - 12.0)
	if law == "pulse":
		var period := int(110.0 / maxf(0.3, st))
		var r := float(t % period) / float(period) * 720.0
		var d := sqrt(pow(s["px"] - W / 2, 2) + pow(s["py"] - H / 2, 2))
		if absf(d - r) < 15.0 and s["inv"] == 0:
			_hit(s)
		if t % period == 0:
			s["events"].append("pulse")
	if law == "contagion":
		var every := int(150.0 / maxf(0.3, st))
		if t % every == 0 and s["zones"].size() < 8:
			var zx := 60.0 + fr(s) * (W - 120.0)
			var zy := 60.0 + fr(s) * (H - 120.0)
			if (zx - s["px"]) * (zx - s["px"]) + (zy - s["py"]) * (zy - s["py"]) > 19600.0:
				s["zones"].append([zx, zy, 8.0, 0])
				s["events"].append("pulse")
		var kz := []
		for z in s["zones"]:
			z[3] += 1
			z[2] = minf(z[2] + 0.35, 64.0) if z[3] < 240 else z[2] - 0.5
			var dzx: float = z[0] - s["px"]
			var dzy: float = z[1] - s["py"]
			if dzx * dzx + dzy * dzy < (z[2] + 8.0) * (z[2] + 8.0) and s["inv"] == 0:
				_hit(s)
			if z[2] > 6.0:
				kz.append(z)
		s["zones"] = kz
	if law == "purge":
		var period2 := int(200.0 / maxf(0.3, st))
		s["fire_x"] = float(t % period2) / float(period2) * (W + 160.0) - 80.0
		s["gap_y"] = H / 2 + sin(t * 0.03) * (H * 0.3)
		if absf(s["px"] - s["fire_x"]) < 14.0 and absf(s["py"] - s["gap_y"]) > 70.0 and s["inv"] == 0:
			_hit(s)
		if t % period2 == 0:
			s["events"].append("pulse")
	# hazards
	var keep := []
	for h in s["hazards"]:
		h[0] += h[2] * DT
		h[1] += h[3] * DT
		if law == "drift":
			h[2] += wind.x * DT * 0.4
			h[3] += wind.y * DT * 0.4
		var dxh: float = h[0] - s["px"]
		var dyh: float = h[1] - s["py"]
		if dxh * dxh + dyh * dyh < (h[4] + 9.0) * (h[4] + 9.0):
			if s["inv"] == 0:
				_hit(s)
			continue
		if h[0] < -60.0 or h[0] > W + 60.0 or h[1] < -60.0 or h[1] > H + 60.0:
			continue
		keep.append(h)
	s["hazards"] = keep
	if t % s["spawn_every"] == 0 and s["hazards"].size() < int(p["max_hazards"]):
		var side := K.rnd(s, 4)
		var x := 0.0
		var y := 0.0
		if side == 0:
			x = fr(s) * W; y = -30.0
		elif side == 1:
			x = fr(s) * W; y = H + 30.0
		elif side == 2:
			x = -30.0; y = fr(s) * H
		else:
			x = W + 30.0; y = fr(s) * H
		var tx: float = s["px"] + (fr(s) - 0.5) * 220.0
		var ty: float = s["py"] + (fr(s) - 0.5) * 220.0
		var dir := Vector2(tx - x, ty - y).normalized()
		var spd: float = s["speed"] * (0.7 + 0.6 * fr(s))
		s["hazards"].append([x, y, dir.x * spd, dir.y * spd, 9.0 + fr(s) * 8.0])
	# shards
	while s["shards"].size() < 3:
		var sx := 40.0 + fr(s) * (W - 80.0)
		var sy := 40.0 + fr(s) * (H - 80.0)
		if (sx - s["px"]) * (sx - s["px"]) + (sy - s["py"]) * (sy - s["py"]) > 14400.0:
			s["shards"].append([sx, sy])
	var ks := []
	for sh in s["shards"]:
		if (sh[0] - s["px"]) * (sh[0] - s["px"]) + (sh[1] - s["py"]) * (sh[1] - s["py"]) < 484.0:
			s["collected"] += 1
			s["score"] += 100
			s["events"].append("pickup")
			if law == "contagion":          # a cure: every infection zone shrinks
				for z in s["zones"]:
					z[2] *= 0.6
		else:
			ks.append(sh)
	s["shards"] = ks
	if s["inv"] > 0:
		s["inv"] -= 1
	if s["dash_cd"] > 0:
		s["dash_cd"] -= 1
	if s["collected"] >= s["goal"]:
		s["done"] = 1
		s["won"] = 1
		s["score"] += maxi(0, s["limit"] - t) + s["hp"] * 150
		s["events"].append("win")
	elif s["hp"] <= 0 or t >= s["limit"]:
		s["done"] = 1
		s["events"].append("lose")


static func _hit(s: Dictionary) -> void:
	s["hp"] -= 1
	s["inv"] = 30
	s["events"].append("hit")


# ---------------------------------------------------------------- bots
static func _nearest_shard(s: Dictionary) -> Vector2:
	var best := Vector2(W / 2, H / 2)
	var bd := 1e18
	for sh in s["shards"]:
		var d: float = (sh[0] - s["px"]) * (sh[0] - s["px"]) + (sh[1] - s["py"]) * (sh[1] - s["py"])
		if d < bd:
			bd = d
			best = Vector2(sh[0], sh[1])
	return best


# returns [ax, ay, dash]. skill 1 = avoids hazards (predictive), wells and pulse; skill 0 = walks at shards, noisy, ignores danger.
static func bot(s: Dictionary, skill_in: int) -> Array:
	var skill := skill_in
	if skill_in == 2:       # average human: attentive ~75% of 0.2 s windows, otherwise reacts like a novice
		var window: int = int(s["t"]) / 6
		skill = 1 if (window * 2654435761 + int(s["stage"]) * 97) % 100 < 75 else 0
	var pos := Vector2(s["px"], s["py"])
	var tgt := _nearest_shard(s)
	var want := (tgt - pos).normalized()
	if skill == 0:
		var ang := sin(float(s["t"]) * 0.13) * 0.8
		return [want.rotated(ang).x, want.rotated(ang).y, false]
	var steer := want * (1.0 + 1.5 * clampf(1.0 - pos.distance_to(tgt) / 300.0, 0.0, 1.0))
	var dash := false
	var pv := Vector2(s["vx"], s["vy"])
	for h in s["hazards"]:
		# closest-approach prediction: will this hazard hit me within ~1.2 s? if so, step away from the predicted contact point
		var rp := Vector2(h[0] - s["px"], h[1] - s["py"])
		var rv := Vector2(h[2], h[3]) - pv
		var vv := rv.length_squared()
		var tca := 0.0 if vv < 1.0 else clampf(-rp.dot(rv) / vv, 0.0, 1.2)
		var closest := rp + rv * tca
		var dmin := closest.length()
		var danger: float = float(h[4]) + 34.0
		if dmin < danger:
			var away := -closest.normalized() if dmin > 0.5 else -rp.normalized().orthogonal()
			steer += away * (1.6 + (1.2 - tca) * 2.2) * (danger - dmin) / danger * 2.0
			if tca < 0.14 and dmin < float(h[4]) + 14.0 and s["inv"] == 0 and s["dash_cd"] == 0:
				dash = true
	var law: String = s["p"]["law"]
	if law == "wells":
		for w in s["wells"]:
			var away2 := pos - Vector2(w[0], w[1])
			if away2.length() < 90.0:
				steer += away2.normalized() * (90.0 - away2.length()) / 15.0
	if law == "pulse":
		var c := Vector2(W / 2, H / 2)
		var period := int(110.0 / maxf(0.3, float(s["p"]["law_strength"])))
		var r := float(s["t"] % period) / float(period) * 720.0
		var d3 := pos.distance_to(c)
		if absf(d3 - r) < 70.0:
			var radial := (pos - c).normalized()
			steer += (radial * (1.0 if d3 > r else -1.0)) * 2.5
			if absf(d3 - r) < 30.0 and s["inv"] == 0 and s["dash_cd"] == 0:
				dash = true
	if law == "contagion":
		for z in s["zones"]:
			var awz := pos - Vector2(z[0], z[1])
			var lim: float = z[2] + 55.0
			if awz.length() < lim:
				steer += awz.normalized() * (lim - awz.length()) / 14.0
	if law == "purge":
		var dxf: float = float(s["fire_x"]) - pos.x
		if absf(dxf) < 130.0:
			steer.y += clampf((float(s["gap_y"]) - pos.y) / 25.0, -4.0, 4.0)
			if absf(dxf) < 40.0 and absf(pos.y - float(s["gap_y"])) < 60.0:
				steer.x += 0.0
			else:
				steer.x += -signf(dxf) * (130.0 - absf(dxf)) / 40.0
			if absf(dxf) < 22.0 and s["inv"] == 0 and s["dash_cd"] == 0:
				dash = true
	if pos.x < 70.0: steer.x += 1.5
	if pos.x > W - 70.0: steer.x -= 1.5
	if pos.y < 70.0: steer.y += 1.5
	if pos.y > H - 70.0: steer.y -= 1.5
	steer = steer.normalized()
	return [steer.x, steer.y, dash]


static func play_full(seed_in: int, p: Dictionary, skill: int) -> Dictionary:
	"""Play all 3 stages (hp resets each stage). Returns stages cleared and total score."""
	var cleared := 0
	var score := 0
	for stage in range(1, 4):
		var s := new_stage(seed_in * 10 + stage, p, stage)
		while s["done"] == 0:
			var a := bot(s, skill)
			step(s, a[0], a[1], a[2])
		score += s["score"]
		if s["won"] == 0:
			break
		cleared += 1
	return {"cleared": cleared, "score": score}
