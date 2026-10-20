# Artillery core: deterministic turn-based duel between two emplacements on deformable terrain. A shot is a ballistic arc under the universe's gravity and
# wind; blasts hurt everything nearby (self included) and the universe's armor factor divides damage. Modules: terrain (static / craters), ricochet (shells
# bounce once), gust (wind changes every turn). Bots search the real simulation, so every module is playable by every tier. Float ops: + - * / sqrt, cos, sin.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const W := 1000.0
const H := 600.0
const COLS := 100
const CW := 10.0
const TANK_R := 20.0
const LEVELS := {0: [12.0, 0.25, 0], 1: [4.0, 0.08, 1], 2: [0.6, 0.02, 1]}     # novice, average, expert: [angle error deg, power error fraction, wind aware]


static func defaults() -> Dictionary:
	return {"gravity": 0.3, "wind": 0.0, "armor": 1.0, "hp": 100.0, "blast_r": 44.0, "blast_dmg": 60.0, "pmax": 18.0, "max_turns": 24,
		"ai_err": 5.0, "ai_pow": 0.08, "ai_wind": 1, "terrain": 0, "ricochet": 0, "gust": 0}


static func int_keys() -> Array:
	return ["max_turns", "ai_wind", "terrain", "ricochet", "gust"]


static func new_match(seed_in: int, p: Dictionary) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "p": p, "t": 0, "ter": [], "x": [0.0, 0.0], "hp": [float(p["hp"]), float(p["hp"])], "turn": 0, "wind": 0.0, "wind0": 0.0,
		"over": 0, "winner": -1, "events": [], "hits": [0, 0], "shots": [0, 0], "craters": 0}
	var v := 400.0
	var raw := []
	for i in COLS:
		v = clampf(v + float(K.rnd(s, 31)) - 15.0, 300.0, 480.0)
		raw.append(v)
	for pass_i in 3:
		var sm := []
		for i in COLS:
			sm.append((raw[maxi(0, i - 1)] + raw[i] + raw[mini(COLS - 1, i + 1)]) / 3.0)
		raw = sm
	s["ter"] = raw
	s["x"][0] = 70.0 + float(K.rnd(s, 160))
	s["x"][1] = W - 70.0 - float(K.rnd(s, 160))
	s["wind0"] = float(p["wind"]) * (1.0 if K.rnd(s, 2) == 0 else -1.0)
	s["wind"] = s["wind0"]
	s["turn"] = K.rnd(s, 2)
	return s


static func ground_y(s: Dictionary, x: float) -> float:
	return float(s["ter"][clampi(int(x / CW), 0, COLS - 1)])


static func tank_y(s: Dictionary, i: int) -> float:
	return ground_y(s, float(s["x"][i])) - 8.0


# Pure ballistic simulation of one shot (no state change). Returns the impact point and what it hit.
static func sim_shot(s: Dictionary, who: int, ang: float, pw: float, wind: float, rec := false) -> Dictionary:
	var p: Dictionary = s["p"]
	var dir := 1.0 if who == 0 else -1.0
	var a := ang * 0.017453292519943295
	var x: float = float(s["x"][who])
	var y: float = tank_y(s, who) - 12.0
	var vx := dir * pw * cos(a)
	var vy := -pw * sin(a)
	var g := float(p["gravity"])
	var bounced := 0
	var steps := 0
	var path := []
	var res := {"x": x, "y": y, "tank": -1, "out": false, "steps": 0, "path": path}
	while steps < 700:
		vx += wind
		vy += g
		x += vx
		y += vy
		steps += 1
		if rec and steps % 2 == 0:
			path.append([x, y])
		if x < 0.0 or x > W or y > H:
			res["out"] = true
			break
		var hit := -1
		for t in 2:
			if steps > 8 or t != who:
				var dx: float = x - float(s["x"][t])
				var dy: float = y - tank_y(s, t)
				if dx * dx + dy * dy < TANK_R * TANK_R:
					hit = t
		if hit >= 0:
			res["tank"] = hit
			break
		var gy := ground_y(s, x)
		if y >= gy:
			if int(p["ricochet"]) == 1 and bounced == 0:
				bounced = 1
				y = gy - 1.0
				vy = -vy * 0.55
				vx *= 0.75
				continue
			y = gy
			break
	res["x"] = x
	res["y"] = y
	res["steps"] = steps
	return res


static func fire(s: Dictionary, who: int, ang: float, pw: float) -> Dictionary:
	var p: Dictionary = s["p"]
	s["events"] = ["shot"]
	var r := sim_shot(s, who, ang, pw, float(s["wind"]))
	s["shots"][who] += 1
	if not r["out"]:
		var R := float(p["blast_r"])
		for t in 2:
			var dx: float = float(r["x"]) - float(s["x"][t])
			var dy: float = float(r["y"]) - tank_y(s, t)
			var d := sqrt(dx * dx + dy * dy)
			var dmg := 0.0
			if r["tank"] == t:
				dmg = float(p["blast_dmg"])
			elif d < R:
				dmg = float(p["blast_dmg"]) * (1.0 - d / R)
			if dmg > 0.0:
				s["hp"][t] = float(s["hp"][t]) - dmg / float(p["armor"])
				if t != who:
					s["hits"][who] += 1
				s["events"].append("hit")
		if int(p["terrain"]) == 1:
			for c in COLS:
				var cx := (float(c) + 0.5) * CW
				var ddx := cx - float(r["x"])
				if absf(ddx) < R:
					var depth := sqrt(R * R - ddx * ddx) * 0.7
					s["ter"][c] = minf(H - 40.0, maxf(float(s["ter"][c]), float(r["y"]) + depth))
			s["craters"] += 1
		s["events"].append("blast")
	s["t"] += 1
	s["turn"] = 1 - who
	if int(p["gust"]) == 1:
		s["wind"] = float(s["wind0"]) * float(K.rnd(s, 201) - 100) / 100.0 * 1.6
	if float(s["hp"][who]) <= 0.0:
		s["over"] = 1
		s["winner"] = 1 - who
	elif float(s["hp"][1 - who]) <= 0.0:
		s["over"] = 1
		s["winner"] = who
	elif s["t"] >= int(p["max_turns"]):
		s["over"] = 1
		s["winner"] = 0 if float(s["hp"][0]) > float(s["hp"][1]) else 1
	return r


# Bot: searches the real simulation for the shot that lands on the opponent, then degrades it by the tier's error.
static func ai_choose(s: Dictionary, who: int, lv: Array) -> Array:
	var p: Dictionary = s["p"]
	var tgt := 1 - who
	var tx: float = float(s["x"][tgt])
	var ty: float = tank_y(s, tgt)
	var w: float = float(s["wind"]) if int(lv[2]) == 1 else 0.0
	var pmax := float(p["pmax"])
	var best_a := 45.0
	var best_p := pmax * 0.7
	var best_d := 1e9
	for ai in 7:
		var a := 15.0 + 10.0 * float(ai)
		for pi in 5:
			var pw := pmax * (0.35 + 0.1625 * float(pi))
			var d := _score(s, who, a, pw, w, tx, ty)
			if d < best_d:
				best_d = d
				best_a = a
				best_p = pw
	var ca := best_a
	var cp := best_p
	for ai in 5:
		for pi in 5:
			var a := ca + 2.0 * float(ai - 2)
			var pw := minf(pmax, maxf(pmax * 0.2, cp + pmax * 0.025 * float(pi - 2)))
			var d := _score(s, who, a, pw, w, tx, ty)
			if d < best_d:
				best_d = d
				best_a = a
				best_p = pw
	var e1 := float(K.rnd(s, 1001) + K.rnd(s, 1001) - 1000) / 1000.0
	var e2 := float(K.rnd(s, 1001) + K.rnd(s, 1001) - 1000) / 1000.0
	return [clampf(best_a + float(lv[0]) * e1, 3.0, 87.0), clampf(best_p * (1.0 + float(lv[1]) * e2), pmax * 0.15, pmax)]


static func _score(s: Dictionary, who: int, a: float, pw: float, w: float, tx: float, ty: float) -> float:
	var r := sim_shot(s, who, a, pw, w)
	if r["out"]:
		return 1e8
	if r["tank"] == 1 - who:
		return 0.0
	var dx: float = float(r["x"]) - tx
	var dy: float = float(r["y"]) - ty
	var d := sqrt(dx * dx + dy * dy)
	var sx: float = float(r["x"]) - float(s["x"][who])           # do not blow yourself up
	var sy: float = float(r["y"]) - tank_y(s, who)
	if sqrt(sx * sx + sy * sy) < float(s["p"]["blast_r"]) * 0.9:
		d += 200.0
	return d


static func rival_params(p: Dictionary) -> Array:
	return [float(p["ai_err"]), float(p["ai_pow"]), int(p["ai_wind"])]


static func play(seed_in: int, p: Dictionary, lv: int, rival = null) -> Dictionary:
	var s := new_match(seed_in, p)
	var rv: Array = rival if rival != null else rival_params(p)
	while s["over"] == 0:
		var who: int = s["turn"]
		var a := ai_choose(s, who, LEVELS[lv] if who == 0 else rv)
		fire(s, who, a[0], a[1])
	return s


static func play_symmetric(seed_in: int, p: Dictionary) -> Dictionary:
	var s := new_match(seed_in, p)
	while s["over"] == 0:
		var who: int = s["turn"]
		var a := ai_choose(s, who, LEVELS[2])
		fire(s, who, a[0], a[1])
	return s


static func digest(s: Dictionary) -> String:
	var tsum := 0
	for c in COLS:
		tsum += int(float(s["ter"][c]) * 10.0)
	var parts := [s["t"], int(float(s["hp"][0]) * 1000.0), int(float(s["hp"][1]) * 1000.0), s["over"], s["winner"], s["rng"], tsum, int(float(s["x"][0])), int(float(s["x"][1]))]
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))
