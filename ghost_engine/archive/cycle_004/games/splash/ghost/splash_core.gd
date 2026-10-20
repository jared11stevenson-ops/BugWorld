# Splash core: deterministic top-down water-balloon fight (60 ticks/s). Arcing balloons land after a flight time and splash everyone nearby
# (friendly fire is on). Only + - * / sqrt and integer hashing are used.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const W := 960.0
const H := 600.0
const AR := 16.0
const LEVELS := {0: [0.0, 90.0, 0.4, 0.0], 1: [0.5, 40.0, 0.65, 0.5], 2: [0.0, 10.0, 0.9, 0.95]}     # [lead, aim error px, aggression, dodge]


static func defaults() -> Dictionary:
	return {"slick": 0, "wind": 0.0, "splash_dmg": 45.0, "splash_r": 62.0, "throw_cd": 30, "refill_ticks": 40, "max_ammo": 3, "team_size": 3, "max_ticks": 2400,
		"range": 320.0, "speed": 3.4, "en_lead": 0.5, "en_err": 40.0, "en_aggr": 0.65, "en_dodge": 0.5, "ally_level": 1}


static func new_match(seed_in: int, p: Dictionary) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "p": p, "t": 0, "agents": [], "balloons": [], "obst": [], "over": 0, "winner": -1, "hits": [0, 0], "friendly": [0, 0], "events": []}
	var n: int = int(p["team_size"])
	for i in 5:
		s["obst"].append([200.0 + float(K.rnd(s, 560)), 90.0 + float(K.rnd(s, 420)), 26.0 + float(K.rnd(s, 18))])
	for team in 2:
		for i in n:
			var yy := H * float(i + 1) / float(n + 1) + float(K.rnd(s, 30)) - 15.0
			s["agents"].append({"x": 110.0 if team == 0 else W - 110.0, "y": yy, "vx": 0.0, "vy": 0.0, "wet": 0.0, "ammo": 1, "cd": 0, "team": team, "alive": 1, "refill": 0})
	return s


static func station(team: int) -> Vector2:
	return Vector2(70.0 if team == 0 else W - 70.0, H / 2.0)


static func _tri(t: int) -> float:
	var ph := t % 240
	return (float(ph) if ph < 120 else float(240 - ph)) / 60.0 - 1.0


static func flight(d: float) -> int:
	return 14 + int(d / 22.0)


static func step(s: Dictionary, inputs: Array) -> void:
	if s["over"] != 0:
		return
	s["events"] = []
	var p: Dictionary = s["p"]
	s["t"] += 1
	var slick: bool = int(p["slick"]) != 0
	var fr := 0.95 if slick else 0.82
	var acc: float = float(p["speed"]) * (1.0 - fr) / fr
	for i in s["agents"].size():
		var a: Dictionary = s["agents"][i]
		if a["alive"] == 0:
			continue
		var inp: Array = inputs[i]
		var ax := float(inp[0])
		var ay := float(inp[1])
		var l2 := ax * ax + ay * ay
		if l2 > 1.0:
			var l := sqrt(l2)
			ax /= l
			ay /= l
		a["vx"] = (a["vx"] + ax * acc) * fr
		a["vy"] = (a["vy"] + ay * acc) * fr
		a["x"] += a["vx"]
		a["y"] += a["vy"]
		a["x"] = clampf(a["x"], AR, W - AR)
		a["y"] = clampf(a["y"], AR, H - AR)
		for o in s["obst"]:
			var dx: float = a["x"] - o[0]
			var dy: float = a["y"] - o[1]
			var d2 := dx * dx + dy * dy
			var r: float = o[2] + AR
			if d2 < r * r:
				var d := sqrt(d2)
				if d > 0.001:
					a["x"] = o[0] + dx / d * r
					a["y"] = o[1] + dy / d * r
		if a["cd"] > 0:
			a["cd"] -= 1
		var st := station(a["team"])
		if absf(a["x"] - st.x) < 46.0 and absf(a["y"] - st.y) < 46.0 and a["ammo"] < int(p["max_ammo"]):
			a["refill"] += 1
			if a["refill"] >= int(p["refill_ticks"]):
				a["refill"] = 0
				a["ammo"] += 1
				s["events"].append("refill")
		else:
			a["refill"] = 0
		if inp[2] and a["ammo"] > 0 and a["cd"] == 0:
			var tx := float(inp[3])
			var ty := float(inp[4])
			var dx2: float = tx - a["x"]
			var dy2: float = ty - a["y"]
			var dd := sqrt(dx2 * dx2 + dy2 * dy2)
			var rg: float = float(p["range"])
			if dd > rg:
				tx = a["x"] + dx2 / dd * rg
				ty = a["y"] + dy2 / dd * rg
				dd = rg
			var T := flight(dd)
			tx += float(p["wind"]) * float(T) * _tri(int(s["t"]))
			s["balloons"].append([a["x"], a["y"], clampf(tx, 0.0, W), clampf(ty, 0.0, H), s["t"], T, a["team"], i])
			a["ammo"] -= 1
			a["cd"] = int(p["throw_cd"])
			s["events"].append("throw")
	var keep := []
	for b in s["balloons"]:
		if s["t"] - b[4] >= b[5]:
			_splash(s, b)
		else:
			keep.append(b)
	s["balloons"] = keep
	var tot := [0.0, 0.0]
	var alive := [0, 0]
	for a in s["agents"]:
		tot[a["team"]] += minf(100.0, a["wet"])
		alive[a["team"]] += a["alive"]
	if alive[0] == 0 or alive[1] == 0:
		s["over"] = 1
		s["winner"] = 1 if alive[0] == 0 and alive[1] > 0 else (0 if alive[1] == 0 and alive[0] > 0 else -1)
	elif s["t"] >= int(p["max_ticks"]):
		s["over"] = 1
		s["winner"] = 0 if tot[0] < tot[1] else (1 if tot[1] < tot[0] else -1)


static func _splash(s: Dictionary, b: Array) -> void:
	var p: Dictionary = s["p"]
	var R: float = float(p["splash_r"])
	s["events"].append("splash")
	for a in s["agents"]:
		if a["alive"] == 0:
			continue
		var dx: float = a["x"] - b[2]
		var dy: float = a["y"] - b[3]
		var d := sqrt(dx * dx + dy * dy)
		if d < R:
			a["wet"] += float(p["splash_dmg"]) * (1.0 - 0.5 * d / R)
			s["events"].append("hit")
			if a["team"] != b[6]:
				s["hits"][b[6]] += 1
			else:
				s["friendly"][b[6]] += 1
			if a["wet"] >= 100.0:
				a["alive"] = 0


static func _h(s: Dictionary, i: int, k: int) -> float:
	var x: int = (int(s["t"]) * 2654435761 + i * 40503 + k * 9973) & 0xFFFFFFFF      # integer mixing hash: no correlation between agent indices
	x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
	x = x ^ (x >> 16)
	return float(x % 2000) / 1000.0 - 1.0


# a = [lead, err, aggr, dodge]. Returns [ax, ay, throw, tx, ty].
static func ai_input(s: Dictionary, i: int, a: Array) -> Array:
	var me: Dictionary = s["agents"][i]
	if me["alive"] == 0:
		return [0.0, 0.0, false, 0.0, 0.0]
	var p: Dictionary = s["p"]
	var R: float = float(p["splash_r"])
	var pos := Vector2(me["x"], me["y"])
	var m := Vector2.ZERO
	for b in s["balloons"]:
		var rem: int = int(b[5]) - (int(s["t"]) - int(b[4]))
		if rem <= 26:
			var tp := Vector2(b[2], b[3])
			if pos.distance_to(tp) < R + AR + 12.0 and (_h(s, i, 3) + 1.0) * 50.0 < float(a[3]) * 100.0:
				var away := pos - tp
				m += (away.normalized() if away.length() > 0.5 else Vector2(1, 0)) * 1.0
	var enemy_i := -1
	var bd := 1e18
	for j in s["agents"].size():
		var e: Dictionary = s["agents"][j]
		if e["alive"] != 0 and e["team"] != me["team"]:
			var d2: float = (e["x"] - pos.x) * (e["x"] - pos.x) + (e["y"] - pos.y) * (e["y"] - pos.y)
			if d2 < bd:
				bd = d2
				enemy_i = j
	if enemy_i < 0:
		return [m.x, m.y, false, 0.0, 0.0]
	var e2: Dictionary = s["agents"][enemy_i]
	var ep := Vector2(e2["x"], e2["y"])
	var dist := sqrt(bd)
	if me["ammo"] == 0 or (me["ammo"] < int(p["max_ammo"]) and dist > 290.0):
		var st := station(me["team"])
		m += (st - pos).normalized() * 1.4
	else:
		if dist > 230.0:
			m += (ep - pos).normalized()
		elif dist < 150.0:
			m += (pos - ep).normalized()
		var perp := (ep - pos).normalized().orthogonal()
		m += perp * (0.7 if (int(s["t"]) / 90 + i) % 2 == 0 else -0.7)
	var thr := false
	var tgt := ep
	if me["ammo"] > 0 and me["cd"] == 0 and dist <= float(p["range"]):
		var fl := float(flight(dist))
		tgt = ep + Vector2(e2["vx"], e2["vy"]) * fl * float(a[0]) * 0.25 + Vector2(_h(s, i, 1), _h(s, i, 2)) * float(a[1])
		if (_h(s, i, 4) + 1.0) * 50.0 < float(a[2]) * 100.0:
			thr = true
			if float(a[3]) > 0.9 or float(a[0]) >= 1.0:           # careful throwers do not soak their own team
				for j in s["agents"].size():
					var al: Dictionary = s["agents"][j]
					if al["alive"] != 0 and al["team"] == me["team"] and j != i and Vector2(al["x"], al["y"]).distance_to(tgt) < R * 0.85:
						thr = false
	return [m.x, m.y, thr, tgt.x, tgt.y]


static func team_inputs(s: Dictionary, player_level: int) -> Array:
	var p: Dictionary = s["p"]
	var ally: Array = LEVELS[int(p["ally_level"])]
	var enemy := [float(p["en_lead"]), float(p["en_err"]), float(p["en_aggr"]), float(p["en_dodge"])]
	var n: int = int(p["team_size"])
	var out := []
	for i in s["agents"].size():
		if i == 0:
			out.append(ai_input(s, i, LEVELS[player_level]))
		elif i < n:
			out.append(ai_input(s, i, ally))
		else:
			out.append(ai_input(s, i, enemy))
	return out


static func play(seed_in: int, p: Dictionary, player_level: int) -> Dictionary:
	var s := new_match(seed_in, p)
	while s["over"] == 0:
		step(s, team_inputs(s, player_level))
	return s


static func play_symmetric(seed_in: int, p: Dictionary) -> Dictionary:
	var s := new_match(seed_in, p)
	while s["over"] == 0:
		var inp := []
		for i in s["agents"].size():
			inp.append(ai_input(s, i, LEVELS[2]))
		step(s, inp)
	return s


static func digest(s: Dictionary) -> String:
	var parts := [s["t"], s["over"], s["winner"], s["hits"][0], s["hits"][1], s["friendly"][0], s["friendly"][1], s["rng"], s["balloons"].size()]
	for a in s["agents"]:
		parts.append_array([int(a["x"] * 1000.0), int(a["y"] * 1000.0), int(a["wet"] * 1000.0), a["ammo"], a["alive"], a["cd"]])
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))
