# Cordon core: deterministic integer epidemic on a town network (SIR-like). Pure logic; bots and the Python twin use the same rules.
extends RefCounted

const K = preload("res://ghost/kernel.gd")


static func defaults() -> Dictionary:
	return {"nodes": 12, "days": 30, "beta": 45, "flow": 6, "mort": 8, "rec": 12, "ap": 3, "meds": 8, "treat": 150, "q_days": 4,
		"seeds": 2, "win_pct": 55, "purge_cap": 15, "purge_ap": 2, "leak": 25, "jump": 4}


static func new_game(seed_in: int, p: Dictionary) -> Dictionary:
	var s := {"rng": K.seed_state(seed_in), "p": p, "day": 0, "ap": int(p["ap"]), "meds": int(p["meds"]), "purged": 0, "over": 0, "won": 0, "why": "",
		"h1": [], "h2": [], "x": [], "y": [], "pop": [], "S": [], "I": [], "R": [], "D": [], "Q": [], "B": [], "edges": [], "log": []}
	var n: int = p["nodes"]
	var total := 0
	for i in n:
		s["x"].append(K.rnd(s, 1000))
		s["y"].append(K.rnd(s, 1000))
		var pop := 300 + K.rnd(s, 900)
		s["pop"].append(pop)
		s["S"].append(pop)
		s["I"].append(0)
		s["R"].append(0)
		s["D"].append(0)
		s["Q"].append(0)
		s["B"].append(0)
		total += pop
	s["total"] = total
	for i in n:
		var best := []
		for j in n:
			if j != i:
				best.append([_d2(s, i, j), j])
		best.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
		for k in 2:
			var j: int = best[k][1]
			_add_edge(s, mini(i, j), maxi(i, j))
	while true:        # connect components
		var comp := _components(s)
		var ncomp := 0
		for c in comp:
			ncomp = maxi(ncomp, c + 1)
		if ncomp <= 1:
			break
		var bd := 1 << 60
		var bi := 0
		var bj := 0
		for i in n:
			for j in range(i + 1, n):
				if comp[i] != comp[j]:
					var d := _d2(s, i, j)
					if d < bd:
						bd = d
						bi = i
						bj = j
		_add_edge(s, bi, bj)
	var placed := 0
	while placed < int(p["seeds"]):
		var i := K.rnd(s, n)
		if s["I"][i] == 0:
			s["I"][i] = 20
			s["S"][i] -= 20
			placed += 1
	s["h1"] = s["I"].duplicate()
	s["h2"] = s["I"].duplicate()
	return s


# Fog of war: the player only knows each town's sick count from two days ago.
static func reported(s: Dictionary, i: int) -> int:
	return s["h2"][i]


static func _d2(s: Dictionary, i: int, j: int) -> int:
	var dx: int = s["x"][i] - s["x"][j]
	var dy: int = s["y"][i] - s["y"][j]
	return dx * dx + dy * dy


static func _add_edge(s: Dictionary, a: int, b: int) -> void:
	for e in s["edges"]:
		if e[0] == a and e[1] == b:
			return
	s["edges"].append([a, b])


static func _components(s: Dictionary) -> Array:
	var n: int = s["pop"].size()
	var comp := []
	for i in n:
		comp.append(-1)
	var c := 0
	for i in n:
		if comp[i] != -1:
			continue
		var stack := [i]
		comp[i] = c
		while stack.size() > 0:
			var u: int = stack.pop_back()
			for e in s["edges"]:
				var v := -1
				if e[0] == u:
					v = e[1]
				elif e[1] == u:
					v = e[0]
				if v >= 0 and comp[v] == -1:
					comp[v] = c
					stack.append(v)
		c += 1
	return comp


static func totals(s: Dictionary) -> Array:
	var alive := 0
	var inf := 0
	for i in s["pop"].size():
		alive += s["S"][i] + s["I"][i] + s["R"][i]
		inf += s["I"][i]
	return [alive, inf]


# ---------------------------------------------------------------- actions (return true if applied)
static func quarantine(s: Dictionary, i: int) -> bool:
	if s["over"] != 0 or s["ap"] < 1 or s["B"][i] != 0:
		return false
	s["ap"] -= 1
	s["Q"][i] = int(s["p"]["q_days"])
	return true


static func treat(s: Dictionary, i: int) -> bool:
	if s["over"] != 0 or s["ap"] < 1 or s["meds"] < 1 or s["B"][i] != 0 or s["I"][i] == 0:
		return false
	var m := mini(s["I"][i], int(s["p"]["treat"]))
	s["I"][i] -= m
	s["R"][i] += m
	s["meds"] -= 1
	s["ap"] -= 1
	return true


static func purge(s: Dictionary, i: int) -> bool:
	if s["over"] != 0 or s["ap"] < int(s["p"]["purge_ap"]) or s["B"][i] != 0:
		return false
	var killed: int = s["S"][i] + s["I"][i]
	s["ap"] -= int(s["p"]["purge_ap"])
	s["D"][i] += killed
	s["purged"] += killed
	s["S"][i] = 0
	s["I"][i] = 0
	s["B"][i] = 1
	if s["purged"] * 100 > s["total"] * int(s["p"]["purge_cap"]):
		s["over"] = 1
		s["why"] = "conscience"
	return true


static func end_day(s: Dictionary) -> void:
	if s["over"] != 0:
		return
	var p: Dictionary = s["p"]
	var n: int = s["pop"].size()
	s["h2"] = s["h1"].duplicate()
	s["h1"] = s["I"].duplicate()
	var new := []
	for i in n:
		new.append(0)
	for i in n:
		if s["B"][i] != 0 or s["I"][i] == 0:
			continue
		var beta: int = int(p["beta"]) / 2 if s["Q"][i] > 0 else int(p["beta"])
		new[i] += s["I"][i] * s["S"][i] * beta / (maxi(1, s["pop"][i]) * 100)
	for e in s["edges"]:
		var u: int = e[0]
		var v: int = e[1]
		if s["B"][u] == 0 and s["B"][v] == 0:
			var f: int = int(p["flow"])
			if s["Q"][u] > 0 or s["Q"][v] > 0:
				f = f * int(p["leak"]) / 100          # sealed roads still leak (smugglers, rumours, bad luck)
			new[v] += s["I"][u] * f / 100
			new[u] += s["I"][v] * f / 100
	for i in n:                                      # long-range jumps: a big outbreak sometimes seeds a distant town
		if s["B"][i] == 0 and s["I"][i] >= 30:
			if K.rnd(s, 100) < int(p["jump"]):
				var tgt := K.rnd(s, n)
				if s["B"][tgt] == 0:
					new[tgt] += 3
	for i in n:
		if s["B"][i] != 0:
			continue
		var inf := mini(s["S"][i], new[i])
		s["S"][i] -= inf
		var deaths := 0
		var rec := 0
		if s["I"][i] > 0:
			deaths = (s["I"][i] * int(p["mort"]) + 99) / 100
			rec = (s["I"][i] * int(p["rec"]) + 99) / 100
			if deaths + rec > s["I"][i]:
				rec = maxi(0, s["I"][i] - deaths)
		s["I"][i] = s["I"][i] + inf - deaths - rec
		s["D"][i] += deaths
		s["R"][i] += rec
		if s["Q"][i] > 0:
			s["Q"][i] -= 1
	s["day"] += 1
	s["ap"] = int(p["ap"])
	var t := totals(s)
	if t[0] * 100 < s["total"] * 30:
		s["over"] = 1
		s["why"] = "collapse"
	elif t[1] == 0 and s["day"] >= 3:
		s["over"] = 1
		s["why"] = "extinguished"
	elif s["day"] >= int(p["days"]):
		s["over"] = 1
		s["why"] = "survived"
	if s["over"] != 0 and s["why"] != "collapse" and s["why"] != "conscience":
		s["won"] = 1 if t[0] * 100 >= s["total"] * int(p["win_pct"]) else 0
		if s["won"] == 0:
			s["why"] = "too_many_dead"


static func digest(s: Dictionary) -> String:
	var parts := [s["day"], s["ap"], s["meds"], s["purged"], s["over"], s["won"], s["rng"]]
	for i in s["pop"].size():
		parts.append_array([s["S"][i], s["I"][i], s["R"][i], s["D"][i], s["Q"][i], s["B"][i]])
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))


# ---------------------------------------------------------------- bots
# Skilled: quarantine the highest-export nodes, treat the heaviest outbreaks, purge only a near-lost small node. Novice: acts randomly, rarely.
static func bot_actions(s: Dictionary, skill_in: int) -> Array:
	var acts := []
	var n: int = s["pop"].size()
	var ap: int = s["ap"]
	var skill := skill_in
	if skill_in == 2:       # average human: skips thinking on ~25% of days, otherwise plays like the expert
		skill = 1 if (int(s["day"]) * 2654435761 + 31) % 100 < 75 else -1
	if skill == -1:
		return acts
	if skill == 0:
		var r := K.rnd(s, 5)
		if r == 0:
			acts.append(["q", K.rnd(s, n)])
		elif r == 1 and s["meds"] > 0:
			acts.append(["t", K.rnd(s, n)])
		return acts
	var order := []
	for i in n:
		if s["B"][i] == 0 and reported(s, i) > 0:
			order.append([reported(s, i), i])
	order.sort_custom(func(a, b): return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1]))
	var meds: int = s["meds"]
	for o in order:
		var i: int = o[1]
		if ap <= 0:
			break
		if meds > 0 and o[0] >= 40:
			acts.append(["t", i])
			meds -= 1
			ap -= 1
		elif s["Q"][i] <= 1 and o[0] >= 15:
			acts.append(["q", i])
			ap -= 1
	return acts


static func apply_action(s: Dictionary, a: Array) -> bool:
	match a[0]:
		"q": return quarantine(s, a[1])
		"t": return treat(s, a[1])
		"p": return purge(s, a[1])
	return false


static func play(seed_in: int, p: Dictionary, skill: int) -> Dictionary:
	var s := new_game(seed_in, p)
	while s["over"] == 0:
		for a in bot_actions(s, skill):
			apply_action(s, a)
		end_day(s)
	return s
