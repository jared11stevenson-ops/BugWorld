# Volley core: deterministic 2D volleyball (60 ticks/s). Only + - * / sqrt and integer hashing are used, so the Python twin matches bit for bit.
# Side 0 = left, side 1 = right. Rally scoring, <=3 touches per side, net, wind, slick ground.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const W := 1000.0
const GROUND := 440.0
const NET_X := 500.0
const NET_HALF := 5.0
const NET_TOP := 300.0
const PR := 38.0
const BR := 16.0
const LEVELS := {0: [22, 100.0, 0.35], 1: [11, 40.0, 0.65], 2: [3, 6.0, 0.95]}     # novice, average, expert: [lag ticks, aim error px, aggression]


static func defaults() -> Dictionary:
	return {"wind": 0.0, "slick": 0, "gravity": 0.42, "jump": 10.5, "restitution": 1.0, "points": 7, "ai_lag": 11, "ai_err": 40.0, "ai_aggr": 0.65, "serve_pause": 40, "max_ticks": 14400, "move_acc": 1.5}


static func new_match(seed_in: int, p: Dictionary) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "p": p, "t": 0, "bx": 250.0, "by": 200.0, "bvx": 0.0, "bvy": 0.0,
		"px": [250.0, 750.0], "py": [GROUND, GROUND], "pvx": [0.0, 0.0], "pvy": [0.0, 0.0], "score": [0, 0], "server": K.rnd_pub(seed_in), "touches": 0, "last_side": -1,
		"pause": int(p["serve_pause"]), "rally": 0, "rallies": 0, "rally_hits": 0, "over": 0, "winner": -1, "hist": [], "events": []}
	_serve(s)
	return s


static func _serve(s: Dictionary) -> void:
	var off := float(K.rnd(s, 60)) - 30.0
	s["bx"] = (250.0 if s["server"] == 0 else 750.0) + off
	s["by"] = 180.0
	s["bvx"] = 0.0
	s["bvy"] = 0.0
	s["px"] = [250.0, 750.0]
	s["py"] = [GROUND, GROUND]
	s["pvx"] = [0.0, 0.0]
	s["pvy"] = [0.0, 0.0]
	s["touches"] = 0
	s["last_side"] = -1
	s["rally"] = 0
	s["pause"] = int(s["p"]["serve_pause"])


static func _point(s: Dictionary, side: int) -> void:
	s["score"][side] += 1
	s["rallies"] += 1
	s["rally_hits"] += s["rally"]
	s["server"] = side
	s["events"].append("point")
	if s["score"][side] >= int(s["p"]["points"]):
		s["over"] = 1
		s["winner"] = side
		return
	_serve(s)


static func _tri(t: int) -> float:
	var ph := t % 240
	return (float(ph) if ph < 120 else float(240 - ph)) / 60.0 - 1.0


static func step(s: Dictionary, in0: Array, in1: Array) -> void:
	if s["over"] != 0:
		return
	s["events"] = []
	var p: Dictionary = s["p"]
	s["t"] += 1
	var g: float = float(p["gravity"])
	var ins := [in0, in1]
	for i in 2:
		var acc: float = float(p["move_acc"]) * (0.25 if int(p["slick"]) != 0 else 1.0)
		var fr := 0.95 if int(p["slick"]) != 0 else 0.8
		s["pvx"][i] = (s["pvx"][i] + float(ins[i][0]) * acc) * fr
		s["px"][i] += s["pvx"][i]
		var lo := PR if i == 0 else NET_X + NET_HALF + PR
		var hi := NET_X - NET_HALF - PR if i == 0 else W - PR
		if s["px"][i] < lo:
			s["px"][i] = lo
			s["pvx"][i] = 0.0
		if s["px"][i] > hi:
			s["px"][i] = hi
			s["pvx"][i] = 0.0
		if ins[i][1] and s["py"][i] >= GROUND:
			s["pvy"][i] = -float(p["jump"])
			s["events"].append("jump")
		s["pvy"][i] += g
		s["py"][i] += s["pvy"][i]
		if s["py"][i] >= GROUND:
			s["py"][i] = GROUND
			s["pvy"][i] = 0.0
	s["hist"].append([s["bx"], s["by"], s["bvx"], s["bvy"]])
	if s["hist"].size() > 40:
		s["hist"].pop_front()
	if s["pause"] > 0:
		s["pause"] -= 1
		return
	s["bvx"] += float(p["wind"]) * _tri(int(s["t"]))
	s["bvy"] += g * 0.8
	for sub in 2:
		s["bx"] += s["bvx"] / 2.0
		s["by"] += s["bvy"] / 2.0
		if s["bx"] < BR:
			s["bx"] = BR
			s["bvx"] = absf(s["bvx"])
		if s["bx"] > W - BR:
			s["bx"] = W - BR
			s["bvx"] = -absf(s["bvx"])
		if s["by"] < BR:
			s["by"] = BR
			s["bvy"] = absf(s["bvy"]) * 0.8
		if absf(s["bx"] - NET_X) < NET_HALF + BR and s["by"] > NET_TOP - BR:
			if s["by"] < NET_TOP and s["bvy"] > 0.0:
				s["by"] = NET_TOP - BR
				s["bvy"] = -absf(s["bvy"]) * 0.7
			else:
				var left: bool = s["bx"] < NET_X
				s["bx"] = NET_X - NET_HALF - BR if left else NET_X + NET_HALF + BR
				s["bvx"] = -absf(s["bvx"]) * 0.7 if left else absf(s["bvx"]) * 0.7
		for i in 2:
			var dx: float = s["bx"] - s["px"][i]
			var dy: float = s["by"] - s["py"][i]
			var r := PR + BR
			var d2 := dx * dx + dy * dy
			if d2 < r * r and dy < 10.0:
				var d := sqrt(d2)
				var nx := 0.0
				var ny := -1.0
				if d > 0.001:
					nx = dx / d
					ny = dy / d
				s["bx"] = s["px"][i] + nx * r
				s["by"] = s["py"][i] + ny * r
				var rvx: float = s["bvx"] - s["pvx"][i]
				var rvy: float = s["bvy"] - s["pvy"][i]
				var vn := rvx * nx + rvy * ny
				if vn < 0.0:
					var e: float = 1.0 + float(p["restitution"])
					s["bvx"] -= e * vn * nx
					s["bvy"] -= e * vn * ny
				s["bvx"] += s["pvx"][i] * 0.3
				s["bvy"] += s["pvy"][i] * 0.3
				var sp := sqrt(s["bvx"] * s["bvx"] + s["bvy"] * s["bvy"])
				if sp > 15.0:
					s["bvx"] *= 15.0 / sp
					s["bvy"] *= 15.0 / sp
				if sp < 5.0 and sp > 0.001:
					s["bvx"] *= 5.0 / sp
					s["bvy"] *= 5.0 / sp
				if s["last_side"] != i:
					s["touches"] = 0
					s["last_side"] = i
				s["touches"] += 1
				s["rally"] += 1
				s["events"].append("hit")
				if s["touches"] > 3:
					_point(s, 1 - i)
					return
		if s["by"] >= GROUND - BR:
			_point(s, 1 if s["bx"] < NET_X else 0)
			return
	if s["t"] >= int(p["max_ticks"]):
		s["over"] = 1
		s["winner"] = 0 if s["score"][0] > s["score"][1] else (1 if s["score"][1] > s["score"][0] else -1)


static func _noise(s: Dictionary, side: int) -> float:
	return float((int(s["t"]) / 8 * 7919 + side * 131 + 17) % 200) / 100.0 - 1.0


# AI/bot controller. a = [lag, err, aggr]. Returns [dir, jump].
static func ai_input(s: Dictionary, side: int, a: Array) -> Array:
	var h: Array = s["hist"]
	if h.size() == 0:
		return [0, false]
	var obs: Array = h[maxi(0, h.size() - 1 - int(a[0]))]
	var g: float = float(s["p"]["gravity"]) * 0.8
	var lo := PR if side == 0 else NET_X + NET_HALF + PR
	var hi := NET_X - NET_HALF - PR if side == 0 else W - PR
	var home := 250.0 if side == 0 else 750.0
	var on_my_side: bool = (obs[0] < NET_X) == (side == 0)
	var target := home
	var yh := GROUND - 70.0
	if on_my_side or (absf(float(obs[0]) - NET_X) < 140.0 and ((obs[2] > 0.0) == (side == 1) or true) and (obs[2] < 0.0) == (side == 1)):
		var disc: float = float(obs[3]) * float(obs[3]) + 2.0 * g * (yh - float(obs[1]))
		var tl := 0.0
		if disc > 0.0:
			tl = (-float(obs[3]) + sqrt(disc)) / g
		if tl < 0.0:
			tl = 0.0
		var xl: float = float(obs[0]) + float(obs[2]) * tl
		if xl < 0.0:
			xl = -xl
		if xl > W:
			xl = 2.0 * W - xl
		var behind := 26.0 + 10.0 * float(s["touches"] if s["last_side"] == side else 0)     # stand behind the ball so contact pushes it toward the net
		target = xl + (-behind if side == 0 else behind) + float(a[1]) * _noise(s, side)
	target = clampf(target, lo, hi)
	var dir := 0
	var dx: float = target - float(s["px"][side])
	if dx > 8.0:
		dir = 1
	elif dx < -8.0:
		dir = -1
	var jump := false
	var bdx: float = float(s["bx"]) - float(s["px"][side])
	var bdy: float = float(s["by"]) - float(s["py"][side])
	if on_my_side and absf(bdx) < 70.0 and bdy < -40.0 and bdy > -190.0 and s["bvy"] > -2.0:
		jump = float((int(s["t"]) * 2654435761 + side * 97) % 100) < float(a[2]) * 100.0
	return [dir, jump]


static func level_params(level: int) -> Array:
	return LEVELS[level]


static func play(seed_in: int, p: Dictionary, left_level: int, right_params: Array) -> Dictionary:
	var s := new_match(seed_in, p)
	while s["over"] == 0:
		step(s, ai_input(s, 0, LEVELS[left_level]), ai_input(s, 1, right_params))
	return s


static func digest(s: Dictionary) -> String:
	var parts := [s["t"], s["score"][0], s["score"][1], s["touches"], s["rally"], s["rallies"], s["rally_hits"], s["over"], s["winner"], s["server"], s["rng"],
		int(s["bx"] * 1000.0), int(s["by"] * 1000.0), int(s["bvx"] * 1000.0), int(s["bvy"] * 1000.0),
		int(s["px"][0] * 1000.0), int(s["px"][1] * 1000.0), int(s["py"][0] * 1000.0), int(s["py"][1] * 1000.0)]
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))
