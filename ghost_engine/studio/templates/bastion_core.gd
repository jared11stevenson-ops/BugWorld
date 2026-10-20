# Bastion core: deterministic wave-defence (60 ticks/s). Invaders walk a winding path; the player fortifies build slots with towers. Theme-neutral engine:
# the universe supplies armor (armored invaders take damage / armor), gravity (mortar shell flight time) and the fiction. Modules: mortar (area shells),
# chill (slowing towers), armored (heavy invaders). Bots play through the same build API as the player. Float ops: + - * / sqrt.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const W := 960.0
const H := 600.0
const NS := 10
const LEVELS := {0: [0.15, 0.6], 1: [0.55, 0.25], 2: [1.0, 0.0]}     # novice, average, expert: [chance to pick the best slot, chance to waste a build on a random type]
const MAX_TICKS := 14000


static func defaults() -> Dictionary:
	return {"armor": 1.0, "gravity": 0.3, "lives": 8, "money": 100, "waves": 8, "hp0": 45.0, "hp_growth": 1.3, "count0": 6, "count_step": 2, "speed": 1.6,
		"cannon_dmg": 10.0, "mortar_dmg": 9.0, "mortar_r": 46.0, "chill_slow": 0.5, "cost": 40, "bounty": 8, "wave_bonus": 25, "mortar": 0, "chill": 0, "armored": 0}


static func int_keys() -> Array:
	return ["lives", "money", "waves", "count0", "count_step", "cost", "bounty", "wave_bonus", "mortar", "chill", "armored"]


static func new_match(seed_in: int, p: Dictionary) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "p": p, "t": 0, "path": [], "cum": [], "total": 0.0, "slots": [], "tw": [], "lv": [], "cd": [], "enemies": [], "shells": [], "wave": 0,
		"wave_active": 0, "spawn_left": 0, "spawn_cd": 0, "spawn_i": 0, "money": int(p["money"]), "lives": int(p["lives"]), "over": 0, "winner": -1, "kills": 0, "events": [], "beams": [], "cov": {}}
	var pts := [[0.0, 120.0 + float(K.rnd(s, 360))]]
	for i in 4:
		pts.append([170.0 + 170.0 * float(i) + float(K.rnd(s, 40)), 90.0 + float(K.rnd(s, 420))])
	pts.append([W, 120.0 + float(K.rnd(s, 360))])
	s["path"] = pts
	var cum := [0.0]
	for i in range(1, pts.size()):
		var dx: float = pts[i][0] - pts[i - 1][0]
		var dy: float = pts[i][1] - pts[i - 1][1]
		cum.append(cum[i - 1] + sqrt(dx * dx + dy * dy))
	s["cum"] = cum
	s["total"] = cum[cum.size() - 1]
	for i in NS:
		var pos := pos_at(s, s["total"] * (float(i) + 0.5) / float(NS))
		var side := 1.0 if i % 2 == 0 else -1.0
		var off := side * (45.0 + float(K.rnd(s, 170)))
		s["slots"].append([clampf(pos.x + float(K.rnd(s, 50)) - 25.0, 30.0, W - 30.0), clampf(pos.y + off, 30.0, H - 30.0)])
		s["tw"].append(-1)
		s["lv"].append(0)
		s["cd"].append(0)
	return s


static func pos_at(s: Dictionary, d: float) -> Vector2:
	var cum: Array = s["cum"]
	var path: Array = s["path"]
	var dd := clampf(d, 0.0, float(s["total"]))
	for i in range(1, cum.size()):
		if dd <= cum[i]:
			var u: float = (dd - cum[i - 1]) / maxf(0.001, cum[i] - cum[i - 1])
			return Vector2(path[i - 1][0] + (path[i][0] - path[i - 1][0]) * u, path[i - 1][1] + (path[i][1] - path[i - 1][1]) * u)
	return Vector2(path[path.size() - 1][0], path[path.size() - 1][1])


static func tower_range(s: Dictionary, type: int, lvl: int) -> float:
	var base := 115.0 if type == 0 else (150.0 if type == 1 else 100.0)
	return base * (1.0 + 0.1 * float(lvl))


static func tower_cost(s: Dictionary, type: int) -> int:
	var c := float(s["p"]["cost"])
	var built := 0
	for i in NS:
		if int(s["tw"][i]) >= 0:
			built += 1
	return int(c * (1.0 if type == 0 else (1.5 if type == 1 else 0.8)) * (1.0 + 0.2 * float(built)))       # fortifying gets pricier: placement order matters


static func upgrade_cost(s: Dictionary, slot: int) -> int:
	return int(float(s["p"]["cost"]) * (0.9 + 0.5 * float(s["lv"][slot])) * (1.0 if int(s["tw"][slot]) != 1 else 1.5))


static func type_allowed(s: Dictionary, type: int) -> bool:
	return type == 0 or (type == 1 and int(s["p"]["mortar"]) == 1) or (type == 2 and int(s["p"]["chill"]) == 1)


static func build(s: Dictionary, slot: int, type: int) -> bool:
	if slot < 0 or slot >= NS or not type_allowed(s, type):
		return false
	if int(s["tw"][slot]) >= 0:
		if int(s["lv"][slot]) >= 2 or int(s["money"]) < upgrade_cost(s, slot):
			return false
		s["money"] = int(s["money"]) - upgrade_cost(s, slot)
		s["lv"][slot] += 1
		return true
	if int(s["money"]) < tower_cost(s, type):
		return false
	s["money"] = int(s["money"]) - tower_cost(s, type)
	s["tw"][slot] = type
	s["lv"][slot] = 0
	s["cd"][slot] = 10
	return true


static func start_wave(s: Dictionary) -> void:
	if int(s["wave_active"]) == 1 or s["over"] != 0:
		return
	s["wave_active"] = 1
	s["spawn_left"] = int(s["p"]["count0"]) + int(s["p"]["count_step"]) * int(s["wave"])
	s["spawn_cd"] = 0
	s["spawn_i"] = 0


static func coverage(s: Dictionary, slot: int, type: int) -> float:
	var key := slot * 4 + type
	if s["cov"].has(key):
		return s["cov"][key]
	var r := tower_range(s, type, 0)
	var sp: Array = s["slots"][slot]
	var n := 0
	var steps := int(float(s["total"]) / 12.0)
	for i in steps:
		var q := pos_at(s, 12.0 * float(i))
		var dx: float = q.x - sp[0]
		var dy: float = q.y - sp[1]
		if dx * dx + dy * dy < r * r:
			n += 1
	s["cov"][key] = float(n)
	return float(n)


static func _hurt(s: Dictionary, e: Dictionary, dmg: float) -> void:
	var d := dmg
	if int(e["armored"]) == 1:
		d = dmg / float(s["p"]["armor"])
	e["hp"] = float(e["hp"]) - d


static func step(s: Dictionary) -> void:
	if s["over"] != 0:
		return
	var p: Dictionary = s["p"]
	s["events"] = []
	s["beams"] = []
	s["t"] += 1
	if int(s["wave_active"]) == 1 and int(s["spawn_left"]) > 0:
		s["spawn_cd"] -= 1
		if int(s["spawn_cd"]) <= 0:
			var hp: float = float(p["hp0"]) * pow_i(float(p["hp_growth"]), int(s["wave"]))
			var heavy := 1 if (int(p["armored"]) == 1 and int(s["spawn_i"]) % 4 == 3) else 0
			s["enemies"].append({"px": 0.0, "py": float(s["path"][0][1]), "d": 0.0, "hp": hp * (2.2 if heavy == 1 else 1.0), "max": hp * (2.2 if heavy == 1 else 1.0), "slow": 0, "armored": heavy})
			s["spawn_left"] -= 1
			s["spawn_i"] += 1
			s["spawn_cd"] = 22
	var spd := float(p["speed"])
	var alive := []
	for e in s["enemies"]:
		var v := spd
		if int(e["slow"]) > 0:
			v = spd * (1.0 - float(p["chill_slow"]))
			e["slow"] -= 1
		if int(e["armored"]) == 1:
			v *= 0.8
		e["d"] = float(e["d"]) + v
		var ep := pos_at(s, float(e["d"]))
		e["px"] = ep.x
		e["py"] = ep.y
		if float(e["d"]) >= float(s["total"]):
			s["lives"] -= 2 if int(e["armored"]) == 1 else 1
			s["events"].append("leak")
			continue
		alive.append(e)
	s["enemies"] = alive
	for i in NS:
		var type: int = s["tw"][i]
		if type < 0:
			continue
		if int(s["cd"][i]) > 0:
			s["cd"][i] -= 1
			continue
		var lvl: int = s["lv"][i]
		var r := tower_range(s, type, lvl)
		var sp: Array = s["slots"][i]
		var best: Dictionary = {}
		var bd := -1.0
		for e in s["enemies"]:
			if float(e["d"]) > bd:
				var dx: float = float(e["px"]) - sp[0]
				var dy: float = float(e["py"]) - sp[1]
				if dx * dx + dy * dy <= r * r:
					bd = float(e["d"])
					best = e
		if bd < 0.0:
			continue
		var mul := 1.0 + 0.6 * float(lvl)
		if type == 0:
			_hurt(s, best, float(p["cannon_dmg"]) * mul)
			s["cd"][i] = 24
			s["beams"].append([sp[0], sp[1], pos_at(s, bd)])
		elif type == 2:
			_hurt(s, best, 3.0 * mul)
			best["slow"] = 90
			s["cd"][i] = 30
			s["beams"].append([sp[0], sp[1], pos_at(s, bd)])
		else:
			var q0 := pos_at(s, bd)
			var dist := sqrt((q0.x - sp[0]) * (q0.x - sp[0]) + (q0.y - sp[1]) * (q0.y - sp[1]))
			var delay := maxi(8, int(dist / 7.0 * sqrt(0.3 / float(p["gravity"]))))       # heavier gravity, faster shells
			var tgt := pos_at(s, bd + spd * float(delay))
			s["shells"].append([tgt.x, tgt.y, delay, float(p["mortar_dmg"]) * mul])
			s["cd"][i] = 60
	var keep := []
	for sh in s["shells"]:
		sh[2] -= 1
		if sh[2] > 0:
			keep.append(sh)
			continue
		s["events"].append("boom")
		var R := float(p["mortar_r"])
		for e in s["enemies"]:
			var dx: float = float(e["px"]) - sh[0]
			var dy: float = float(e["py"]) - sh[1]
			if dx * dx + dy * dy <= R * R:
				_hurt(s, e, sh[3])
		s["beams"].append([sh[0], sh[1], Vector2(sh[0], sh[1])])
	s["shells"] = keep
	var live := []
	for e in s["enemies"]:
		if float(e["hp"]) <= 0.0:
			s["kills"] += 1
			s["money"] = int(s["money"]) + int(p["bounty"]) * (3 if int(e["armored"]) == 1 else 1)
			s["events"].append("kill")
		else:
			live.append(e)
	s["enemies"] = live
	if int(s["lives"]) <= 0:
		s["over"] = 1
		s["winner"] = 1
		return
	if int(s["wave_active"]) == 1 and int(s["spawn_left"]) == 0 and s["enemies"].is_empty():
		s["wave_active"] = 0
		s["wave"] += 1
		s["money"] = int(s["money"]) + int(p["wave_bonus"])
		s["events"].append("wave")
		if int(s["wave"]) >= int(p["waves"]):
			s["over"] = 1
			s["winner"] = 0
	if s["t"] >= MAX_TICKS and s["over"] == 0:
		s["over"] = 1
		s["winner"] = 1


static func pow_i(b: float, n: int) -> float:
	var r := 1.0
	for i in n:
		r *= b
	return r


# Bot: same build API as the player. lv = [probability of choosing the best-covered slot, probability of wasting a build on a random tower type].
static func bot_act(s: Dictionary, lv: Array) -> void:
	for guard in 8:
		var free := []
		var built := 0
		for i in NS:
			if int(s["tw"][i]) < 0:
				free.append(i)
			else:
				built += 1
		var seq := [0, 0, 1, 2, 0, 1, 2, 0]
		var type: int = seq[built % seq.size()]
		if not type_allowed(s, type):
			type = 0
		if float(K.rnd(s, 1001)) / 1000.0 < float(lv[1]):
			type = K.rnd(s, 3)
			if not type_allowed(s, type):
				type = 0
		if free.is_empty():
			var bi := -1
			var bv := -1.0
			for i in NS:
				if int(s["lv"][i]) < 2:
					var v := coverage(s, i, int(s["tw"][i])) - 3.0 * float(s["lv"][i])
					if v > bv:
						bv = v
						bi = i
			if bi < 0 or not build(s, bi, int(s["tw"][bi])):
				return
			continue
		if int(s["money"]) < tower_cost(s, type):
			return
		var slot: int = free[K.rnd(s, free.size())]
		if float(K.rnd(s, 1001)) / 1000.0 < float(lv[0]):
			var bv2 := -1.0
			for i in free:
				var v2 := coverage(s, i, type)
				if v2 > bv2:
					bv2 = v2
					slot = i
		if not build(s, slot, type):
			return


static func play(seed_in: int, p: Dictionary, lv: int) -> Dictionary:
	var s := new_match(seed_in, p)
	while s["over"] == 0:
		if int(s["wave_active"]) == 0:
			bot_act(s, LEVELS[lv])
			start_wave(s)
		elif int(s["t"]) % 40 == 0:
			bot_act(s, LEVELS[lv])
		step(s)
	return s


static func digest(s: Dictionary) -> String:
	var parts := [s["t"], s["wave"], s["lives"], s["money"], s["kills"], s["over"], s["winner"], s["rng"], s["enemies"].size()]
	for i in NS:
		parts.append(int(s["tw"][i]) * 10 + int(s["lv"][i]))
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))
