# GDScript twin of ghost/foundry/dsl.py + agents.py: runs ANY compiled concept spec (specs are plain data).
# Same integer semantics and RNG draw order as Python; verified by tests/concept_parity.gd.
extends RefCounted

const K = preload("res://ghost/kernel.gd")
const ADAPTER := 8
const CYCLE := 6
const RANDOM := 7
const COUNTER := 9
const MIRROR := 10
const GREEDY := 11


static func sat(x: int) -> int:
	return 1000000 if x > 1000000 else (-1000000 if x < -1000000 else x)


static func tdiv(a: int, b: int) -> int:
	if b == 0:
		return 0
	return a / b   # GDScript int division truncates toward zero, like dsl.tdiv


static func new_match(spec: Dictionary, seed_in: int) -> Dictionary:
	var p0 := {}
	var p1 := {}
	for v in spec["vars"]:
		p0[v[0]] = v[1]
		p1[v[0]] = v[1]
	return {"p": [p0, p1], "round": 0, "rng": K.seed_state(seed_in), "done": 0, "winner": -1, "timeout": 0,
		"acts": [[], []], "last": [-1, -1]}


static func ev(e, m: Dictionary, me: int, acts: Array, mode: int) -> int:
	if typeof(e) == TYPE_INT or typeof(e) == TYPE_FLOAT:
		return int(e)
	var h: String = e[0]
	if h == "v":
		return m["p"][me if e[1] == "me" else 1 - me][e[2]]
	if h == "act":
		return acts[me if e[1] == "me" else 1 - me]
	if h == "round":
		return m["round"]
	if h == "rnd":
		return K.rnd(m, int(e[1])) if mode == 0 else int(e[1]) / 2
	if h == "!":
		return 0 if ev(e[1], m, me, acts, mode) != 0 else 1
	if h == "?":
		return ev(e[2], m, me, acts, mode) if ev(e[1], m, me, acts, mode) != 0 else ev(e[3], m, me, acts, mode)
	var a := ev(e[1], m, me, acts, mode)
	if h == "&&":
		return 1 if (a != 0 and ev(e[2], m, me, acts, mode) != 0) else 0
	if h == "||":
		return 1 if (a != 0 or ev(e[2], m, me, acts, mode) != 0) else 0
	var b := ev(e[2], m, me, acts, mode)
	match h:
		"+": return sat(a + b)
		"-": return sat(a - b)
		"*": return sat(a * b)
		"/": return tdiv(a, b)
		"min": return mini(a, b)
		"max": return maxi(a, b)
		">": return 1 if a > b else 0
		"<": return 1 if a < b else 0
		">=": return 1 if a >= b else 0
		"<=": return 1 if a <= b else 0
		"==": return 1 if a == b else 0
	return 1 if a != b else 0


static func is_legal(spec: Dictionary, m: Dictionary, me: int, a: int) -> bool:
	var c = spec["actions"][a]["cond"]
	return typeof(c) == TYPE_INT and c == 0 or ev(c, m, me, [0, 0], 1) != 0


static func sanitize(spec: Dictionary, m: Dictionary, me: int, a: int) -> int:
	return a if (a >= 0 and a < spec["actions"].size() and is_legal(spec, m, me, a)) else 0


static func _pending(spec: Dictionary, m: Dictionary, acts: Array, mode: int) -> Array:
	var out := []
	for me in 2:
		for f in spec["actions"][acts[me]]["fx"]:
			out.append([f[0], me if f[1] == "me" else 1 - me, f[2], ev(f[3], m, me, acts, mode)])
	for me in 2:
		for f in spec["passive"]:
			out.append([f[0], me if f[1] == "me" else 1 - me, f[2], ev(f[3], m, me, acts, mode)])
	return out


static func _apply(spec: Dictionary, m: Dictionary, pend: Array) -> void:
	for pe in pend:
		m["p"][pe[1]][pe[2]] = sat(m["p"][pe[1]][pe[2]] + pe[3])
	for v in spec["vars"]:
		for who in 2:
			m["p"][who][v[0]] = maxi(int(v[2]), mini(int(v[3]), m["p"][who][v[0]]))


static func value(spec: Dictionary, m: Dictionary, me: int) -> int:
	var t := 0
	for term in spec["value"]:
		t += int(term[1]) * (m["p"][me][term[0]] - m["p"][1 - me][term[0]])
	return t


static func payoff(spec: Dictionary, m: Dictionary, me: int, a: int, b: int) -> int:
	var acts := [0, 0]
	acts[me] = a
	acts[1 - me] = b
	var sim := {"p": [m["p"][0].duplicate(), m["p"][1].duplicate()], "round": m["round"], "rng": 0}
	_apply(spec, sim, _pending(spec, sim, acts, 1))
	return value(spec, sim, me) - value(spec, m, me)


static func step(spec: Dictionary, m: Dictionary, a0: int, a1: int) -> Array:
	var acts := [sanitize(spec, m, 0, a0), sanitize(spec, m, 1, a1)]
	_apply(spec, m, _pending(spec, m, acts, 0))
	for i in 2:
		m["acts"][i].append(acts[i])
		m["last"][i] = acts[i]
	m["round"] += 1
	var res := [0, 0]
	var hit := false
	for me in 2:
		for er in spec["end"]:
			if ev(er[0], m, me, acts, 1) != 0:
				res[me] = int(er[1])
				hit = true
				break
	if hit:
		var t: int = res[0] - res[1]
		m["done"] = 1
		m["winner"] = 0 if t > 0 else (1 if t < 0 else -1)
	elif m["round"] >= spec["max_rounds"]:
		m["done"] = 1
		m["timeout"] = 1
		var tb: String = spec["tiebreak"]
		if tb != "" and m["p"][0][tb] != m["p"][1][tb]:
			m["winner"] = 0 if m["p"][0][tb] > m["p"][1][tb] else 1
	return acts


static func match_digest(spec: Dictionary, m: Dictionary) -> String:
	var parts := [m["round"], m["winner"], m["timeout"], m["rng"]]
	for who in 2:
		for v in spec["vars"]:
			parts.append(m["p"][who][v[0]])
		parts.append_array(m["acts"][who])
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return "%08x" % K.fnv_str(",".join(strs))


# ---------------------------------------------------------------- agents
static func new_hist(n: int) -> Dictionary:
	var c := []
	for i in n:
		c.append(0)
	return {"counts": c, "last": -1}


static func observe(h: Dictionary, a: int) -> void:
	h["counts"][a] += 1
	h["last"] = a


static func _best(spec: Dictionary, m: Dictionary, me: int, weights: Array) -> int:
	var best_a := 0
	var best_v = null
	for a in spec["actions"].size():
		if not is_legal(spec, m, me, a):
			continue
		var v := 0
		for b in weights.size():
			if weights[b] != 0:
				v += weights[b] * payoff(spec, m, me, a, b)
		if best_v == null or v > best_v:
			best_a = a
			best_v = v
	return best_a


static func choose(spec: Dictionary, pid: int, m: Dictionary, me: int, h: Dictionary) -> int:
	var n: int = spec["actions"].size()
	if pid >= 100:
		var ta: int = (pid - 100) / 10
		var tb: int = (pid - 100) % 10
		var want := ta if m["round"] % 2 == 0 else tb
		if want < n and is_legal(spec, m, me, want):
			return want
		var wl := []
		for i in n:
			wl.append(1)
		return _best(spec, m, me, wl)
	if pid < 6:
		if pid < n and is_legal(spec, m, me, pid):
			return pid
		var wu := []
		for i in n:
			wu.append(1)
		return _best(spec, m, me, wu)
	if pid == CYCLE:
		return m["round"] % n
	if pid == RANDOM:
		return K.rnd(m, n)
	if pid == ADAPTER:
		var w := []
		for c in h["counts"]:
			w.append(c + 1)
		return _best(spec, m, me, w)
	if pid == COUNTER:
		var w2 := []
		for i in n:
			w2.append(0)
		w2[h["last"] if h["last"] >= 0 else 0] = 1
		return _best(spec, m, me, w2)
	if pid == MIRROR:
		return h["last"] if h["last"] >= 0 else 0
	var w3 := []
	for i in n:
		w3.append(1)
	return _best(spec, m, me, w3)


static func play(spec: Dictionary, p0: int, p1: int, seed_in: int) -> Dictionary:
	var n: int = spec["actions"].size()
	var m := new_match(spec, seed_in)
	var h := [new_hist(n), new_hist(n)]
	while m["done"] == 0:
		var a0 := choose(spec, p0, m, 0, h[0])
		var a1 := choose(spec, p1, m, 1, h[1])
		var s := step(spec, m, a0, a1)
		observe(h[0], s[1])
		observe(h[1], s[0])
	return m


static func text_of_fx(f: Array) -> String:
	return "%s %s %s %s" % ["my" if f[1] == "me" else "their", f[2], f[0], expr_text(f[3])]


static func expr_text(e) -> String:
	if typeof(e) == TYPE_INT or typeof(e) == TYPE_FLOAT:
		return str(int(e))
	var h: String = e[0]
	match h:
		"v": return ("my " if e[1] == "me" else "their ") + e[2]
		"act": return ("my" if e[1] == "me" else "their") + " action"
		"round": return "round"
		"rnd": return "d%d" % int(e[1])
		"!": return "not(%s)" % expr_text(e[1])
		"?": return "(%s ? %s : %s)" % [expr_text(e[1]), expr_text(e[2]), expr_text(e[3])]
		"min", "max": return "%s(%s, %s)" % [h, expr_text(e[1]), expr_text(e[2])]
	return "(%s %s %s)" % [expr_text(e[1]), h, expr_text(e[2])]


static func action_tooltip(spec: Dictionary, i: int) -> String:
	var a: Dictionary = spec["actions"][i]
	var parts := []
	for f in a["fx"]:
		parts.append(text_of_fx(f))
	var s := "; ".join(parts)
	if typeof(a["cond"]) != TYPE_INT:
		s = "Only if %s. %s" % [expr_text(a["cond"]), s]
	return s
