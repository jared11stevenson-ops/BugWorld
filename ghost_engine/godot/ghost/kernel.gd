# GHOST ENGINE kernel: GDScript port of ghost/kernel/*.py. Same integer math, same RNG draw order,
# same iteration order => identical state digests. Do not "improve" this file independently:
# change the Python kernel, then re-run `python -m ghost.compiler.compile` and the parity test.
extends RefCounted

const M := 0xFFFFFFFF
const FNV_OFFSET := 2166136261
const ATTACK := 0
const GUARD := 1
const POWER := 2
const HEAL := 3
const CRIT_ROLL := 0
const CRIT_EXPECTED := 1

const EV_TRAVEL := 0
const EV_FIGHT := 1
const EV_KILL := 2
const EV_BUY := 3
const EV_SELL := 4
const EV_WAR := 5
const EV_PEACE := 6
const EV_SPAWN := 7
const EV_INTERVENE := 8
const EV_POTION := 9
const EV_NAMES := ["travel", "fight", "kill", "buy", "sell", "war", "peace", "spawn", "intervene", "potion"]

const OUT_TIMEOUT := 0
const OUT_A_KILLED_B := 1
const OUT_B_KILLED_A := 2
const OUT_BOTH_DIED := 3
const OUT_A_FLED := 4
const OUT_B_FLED := 5

const POLICY_NAMES := ["attacker", "turtle", "bruiser", "medic", "chaos", "adapter", "counter", "guardian"]
const NUM_POLICIES := 8
const ACTION_NAMES := ["Attack", "Guard", "Power", "Heal"]
const TOWN_NAMES := ["Oakhaven", "Stonebridge", "Mirefall", "Highmark", "Saltreach", "Emberdell", "Greywatch", "Thornwick"]
const FACTION_NAMES := ["Crown", "Guild", "Wilds", "Order"]
const FIRST := ["Ash", "Bram", "Cora", "Dov", "Elda", "Fenn", "Gale", "Hob"]
const LAST := ["Vale", "Thorn", "Reed", "Marsh", "Crow", "Stone", "Wick", "Ford"]


# ------------------------------------------------------------------ rng
static func seed_state(seed_in: int) -> int:
	var sd := seed_in & 0x7FFFFFFF
	var x := (sd * 2654435761 + 0x9E3779B9) & M
	if x == 0:
		x = 1
	var st := {"rng": x}
	for _i in 3:
		next_u32(st)
	return st["rng"]


static func next_u32(s: Dictionary) -> int:
	var x: int = s["rng"]
	x ^= (x << 13) & M
	x ^= x >> 17
	x ^= (x << 5) & M
	s["rng"] = x
	return x


static func rnd(s: Dictionary, n: int) -> int:
	return next_u32(s) % n


static func rnd_pub(seed_in: int) -> int:
	var sd := seed_in & 0x7FFFFFFF       # mask first: seeds can exceed 2^31 and the product would overflow int64
	return (sd * 2654435761 / 7) % 2


static func fnv_ints(h: int, vals: Array) -> int:
	for v in vals:
		h = ((h ^ (int(v) & M)) * 16777619) & M
	return h


static func fnv_str(text: String) -> int:
	var h := FNV_OFFSET
	for b in text.to_utf8_buffer():
		h = ((h ^ b) * 16777619) & M
	return h


# ------------------------------------------------------------------ combat
static func reset_fighter(f: Dictionary) -> void:
	f["last"] = -1
	f["streak"] = 0


static func base_damage(x: Dictionary, y: Dictionary) -> int:
	return maxi(1, int(x["atk"]) - int(y["def"]))


static func sanitize(act: int, f: Dictionary) -> int:
	if act == HEAL and f["potions"] <= 0:
		return ATTACK
	return act


static func _dealt(c: Dictionary, x: Dictionary, y: Dictionary, act_x: int, act_y: int, rep: int, s, mode: int) -> int:
	var d := 0
	if act_x == ATTACK:
		d = base_damage(x, y)
	elif act_x == POWER:
		d = base_damage(x, y) * c["power_mult_pct"] / 100
		if act_y == ATTACK:
			d = d * c["power_interrupt_pct"] / 100
	else:
		return 0
	if c["fatigue_pct"] > 0 and rep > 0:
		d = d * maxi(20, 100 - int(c["fatigue_pct"]) * rep) / 100
	if d > 0:
		if mode == CRIT_ROLL:
			if rnd(s, 100) < c["crit_pct"]:
				d = d * c["crit_mult_pct"] / 100
		else:
			d = d * (10000 + int(c["crit_pct"]) * (int(c["crit_mult_pct"]) - 100)) / 10000
	return d


static func _taken(c: Dictionary, raw_in: int, act_y: int, act_x: int) -> int:
	var raw := raw_in
	if raw <= 0:
		return 0
	if act_y == GUARD:
		var red: int = c["guard_reduce_pct"]
		if act_x == POWER:
			red = red * c["guard_pierce_pct"] / 100
		raw = raw * (100 - red) / 100
	elif act_y == HEAL:
		raw = raw * (100 + int(c["heal_vuln_pct"])) / 100
	return raw


static func _rep(f: Dictionary, act: int) -> int:
	return f["streak"] if act == f["last"] else 0


# returns [damage_to_a, damage_to_b, heal_a, heal_b]
static func round_outcome(c: Dictionary, a: Dictionary, b: Dictionary, act_a: int, act_b: int, s, mode: int) -> Array:
	var raw_b := _dealt(c, a, b, act_a, act_b, _rep(a, act_a), s, mode)
	var raw_a := _dealt(c, b, a, act_b, act_a, _rep(b, act_b), s, mode)
	var dmg_b := _taken(c, raw_b, act_b, act_a)
	var dmg_a := _taken(c, raw_a, act_a, act_b)
	if act_b == GUARD and act_a == ATTACK and c["guard_counter_pct"] > 0:
		dmg_a += base_damage(b, a) * c["guard_counter_pct"] / 100
	if act_a == GUARD and act_b == ATTACK and c["guard_counter_pct"] > 0:
		dmg_b += base_damage(a, b) * c["guard_counter_pct"] / 100
	var heal_a := mini(int(c["potion_heal"]), int(a["maxhp"]) - int(a["hp"])) if act_a == HEAL else 0
	var heal_b := mini(int(c["potion_heal"]), int(b["maxhp"]) - int(b["hp"])) if act_b == HEAL else 0
	return [dmg_a, dmg_b, heal_a, heal_b]


static func payoff(c: Dictionary, a: Dictionary, b: Dictionary, act_a_in: int, act_b_in: int) -> int:
	var act_a := sanitize(act_a_in, a)
	var act_b := sanitize(act_b_in, b)
	var o := round_outcome(c, a, b, act_a, act_b, null, CRIT_EXPECTED)
	return o[1] - o[0] + o[2] - o[3]


static func fight_round(c: Dictionary, a: Dictionary, b: Dictionary, act_a_in: int, act_b_in: int, s: Dictionary) -> Array:
	var act_a := sanitize(act_a_in, a)
	var act_b := sanitize(act_b_in, b)
	var o := round_outcome(c, a, b, act_a, act_b, s, CRIT_ROLL)
	if act_a == HEAL:
		a["potions"] -= 1
	if act_b == HEAL:
		b["potions"] -= 1
	a["hp"] = a["hp"] + o[2] - o[0]
	b["hp"] = b["hp"] + o[3] - o[1]
	for pair in [[a, act_a], [b, act_b]]:
		var f: Dictionary = pair[0]
		var act: int = pair[1]
		f["streak"] = f["streak"] + 1 if act == f["last"] else 0
		f["last"] = act
	return [act_a, act_b]


# ------------------------------------------------------------------ policies
static func new_hist() -> Dictionary:
	return {"counts": [0, 0, 0, 0], "last": -1}


static func observe(h: Dictionary, act: int) -> void:
	h["counts"][act] += 1
	h["last"] = act


static func _best(c: Dictionary, me: Dictionary, opp: Dictionary, weights: Array) -> int:
	var best_a := 0
	var best_v = null
	for a in 4:
		if a == HEAL and me["potions"] <= 0:
			continue
		var v := 0
		for b in 4:
			if weights[b] != 0:
				v += weights[b] * payoff(c, me, opp, a, b)
		if best_v == null or v > best_v:
			best_a = a
			best_v = v
	return best_a


static func choose(pid: int, me: Dictionary, opp: Dictionary, h: Dictionary, c: Dictionary, s: Dictionary) -> int:
	if pid == 0:
		return ATTACK
	if pid == 1:
		return GUARD if me["hp"] * 100 < 60 * me["maxhp"] else ATTACK
	if pid == 2:
		return POWER
	if pid == 3:
		if me["hp"] * 100 <= 40 * me["maxhp"] and me["potions"] > 0:
			return HEAL
		return ATTACK
	if pid == 4:
		return rnd(s, 4)
	if pid == 5:
		var w := []
		for i in 4:
			w.append(h["counts"][i] + 1)
		return _best(c, me, opp, w)
	if pid == 7:
		return GUARD
	var last: int = h["last"] if h["last"] >= 0 else ATTACK
	var w2 := [0, 0, 0, 0]
	w2[last] = 1
	return _best(c, me, opp, w2)


# lab-style equal-stat duel: returns [score_x2 (0,1,2), rounds, stalemate(0/1)]
static func duel(c: Dictionary, pa: int, pb: int, seed_in: int) -> Array:
	var s := {"rng": seed_state(seed_in)}
	var a := {"maxhp": 100, "atk": 20, "def": 5, "hp": 100, "potions": c["start_potions"]}
	var b := a.duplicate()
	reset_fighter(a)
	reset_fighter(b)
	var ha := new_hist()
	var hb := new_hist()
	var rounds := 0
	while a["hp"] > 0 and b["hp"] > 0 and rounds < c["round_cap"]:
		var xa := choose(pa, a, b, ha, c, s)
		var xb := choose(pb, b, a, hb, c, s)
		var r := fight_round(c, a, b, xa, xb, s)
		observe(ha, r[1])
		observe(hb, r[0])
		rounds += 1
	if a["hp"] > 0 and b["hp"] > 0:
		return [1, rounds, 1]
	if a["hp"] <= 0 and b["hp"] <= 0:
		return [1, rounds, 0]
	return [2 if b["hp"] <= 0 else 0, rounds, 0]


# ------------------------------------------------------------------ world
static func npc_name(n: Dictionary) -> String:
	return FIRST[n["na"]] + " " + LAST[n["nb"]]


static func new_world(seed_in: int, rules: Dictionary, n_npcs := 24, n_towns := 6, n_fac := 3) -> Dictionary:
	var s := {"seed": seed_in & 0x7FFFFFFF, "tick": 0, "rng": seed_state(seed_in), "rules": rules.duplicate(true),
		"n_fac": n_fac, "towns": [], "adj": [], "rel": [], "war": [], "npcs": [], "pending": [],
		"events": [], "ev_hash": FNV_OFFSET, "minted": 0, "burned": 0, "gold0": 0}
	var cap: int = rules["economy"]["stock_cap"]
	for i in n_towns:
		s["towns"].append({"id": i, "treasury": 100, "stock": cap / 2})
		s["adj"].append([])
	for i in n_towns:
		_link(s, i, (i + 1) % n_towns)
	for i in range(0, n_towns, 3):
		_link(s, i, (i + n_towns / 2) % n_towns)
	for i in n_fac:
		var r1 := []
		var r2 := []
		for j in n_fac:
			r1.append(0)
			r2.append(0)
		s["rel"].append(r1)
		s["war"].append(r2)
	for i in n_fac:
		s["rel"][i][i] = 100
	for i in n_fac:
		for j in range(i + 1, n_fac):
			var v := rnd(s, 61) - 30
			s["rel"][i][j] = v
			s["rel"][j][i] = v
	for i in n_npcs:
		var f := i % n_fac
		var loc := (_home(s, f) + rnd(s, 2)) % n_towns
		var gold := 20 + rnd(s, 31)
		_make_npc(s, f, loc, gold)
	s["gold0"] = total_gold(s)
	return s


static func _link(s: Dictionary, a: int, b: int) -> void:
	if a != b and not (b in s["adj"][a]):
		s["adj"][a].append(b)
		s["adj"][b].append(a)


static func _home(s: Dictionary, f: int) -> int:
	var nt: int = s["towns"].size()
	return (f * (nt / s["n_fac"])) % nt


static func _make_npc(s: Dictionary, faction: int, loc: int, gold: int) -> Dictionary:
	var nid: int = s["npcs"].size()
	var n := {"id": nid, "faction": faction, "loc": loc, "gold": gold}
	n["maxhp"] = 80 + rnd(s, 41)
	n["atk"] = 12 + rnd(s, 13)
	n["def"] = 2 + rnd(s, 6)
	n["potions"] = rnd(s, 4)
	n["policy"] = rnd(s, NUM_POLICIES)
	n["na"] = rnd(s, 8)
	n["nb"] = rnd(s, 8)
	n["hp"] = n["maxhp"]
	n["alive"] = 1
	n["trader"] = 1 if nid % 4 == 3 else 0
	n["kills"] = 0
	n["basis"] = 0
	n["born"] = s["tick"]
	n["aff"] = []
	reset_fighter(n)
	s["npcs"].append(n)
	return n


static func emit(s: Dictionary, etype: int, a := -1, b := -1, c := 0, cause := -1) -> int:
	var eid: int = s["events"].size()
	var ev := [eid, s["tick"], etype, a, b, c, cause]
	s["events"].append(ev)
	s["ev_hash"] = fnv_ints(s["ev_hash"], ev)
	return eid


static func total_gold(s: Dictionary) -> int:
	var t := 0
	for n in s["npcs"]:
		t += n["gold"]
	for tw in s["towns"]:
		t += tw["treasury"]
	for p in s["pending"]:
		t += p[2]
	return t


static func conservation_error(s: Dictionary) -> int:
	return total_gold(s) - (s["gold0"] + s["minted"] - s["burned"])


static func price(s: Dictionary, town: Dictionary) -> int:
	var e: Dictionary = s["rules"]["economy"]
	var pct := maxi(20, 100 + int(e["swing_pct"]) * (int(e["stock_cap"]) / 2 - int(town["stock"])))
	return maxi(1, int(e["base_price"]) * pct / 100)


static func get_aff(n: Dictionary, other: int) -> int:
	for e in n["aff"]:
		if e[0] == other:
			return e[1]
	return 0


static func add_aff(n: Dictionary, other: int, delta: int, cause: int) -> void:
	for e in n["aff"]:
		if e[0] == other:
			e[1] = maxi(-100, mini(100, e[1] + delta))
			if delta < 0:
				e[2] = cause
			return
	n["aff"].append([other, maxi(-100, mini(100, delta)), cause if delta < 0 else -1])


static func change_rel(s: Dictionary, f: int, g: int, delta: int, cause: int) -> void:
	var v := maxi(-100, mini(100, s["rel"][f][g] + delta))
	s["rel"][f][g] = v
	s["rel"][g][f] = v
	var thr: int = s["rules"]["world"]["war_threshold"]
	if v < thr and s["war"][f][g] == 0:
		s["war"][f][g] = 1
		s["war"][g][f] = 1
		emit(s, EV_WAR, f, g, v, cause)
	elif v > thr + 25 and s["war"][f][g] == 1:
		s["war"][f][g] = 0
		s["war"][g][f] = 0
		emit(s, EV_PEACE, f, g, v, cause)


static func die(s: Dictionary, vid: int, killer: int, cause: int) -> int:
	var w: Dictionary = s["rules"]["world"]
	var v: Dictionary = s["npcs"][vid]
	v["alive"] = 0
	v["hp"] = 0
	if killer >= 0:
		var k: Dictionary = s["npcs"][killer]
		var loot: int = v["gold"] * w["loot_pct"] / 100
		v["gold"] -= loot
		k["gold"] += loot
		k["kills"] += 1
	var rem: int = v["gold"]
	v["gold"] = 0
	var kid := emit(s, EV_KILL, killer, vid, v["loc"], cause)
	s["pending"].append([s["tick"] + w["respawn_delay"], v["faction"], rem, vid, kid])
	if killer >= 0:
		var k2: Dictionary = s["npcs"][killer]
		add_aff(v, killer, -50, kid)
		for o in s["npcs"]:
			if o["alive"] and o["id"] != killer and o["id"] != vid and o["loc"] == v["loc"] and o["faction"] == v["faction"]:
				add_aff(o, killer, -15, kid)
		if k2["faction"] != v["faction"]:
			change_rel(s, k2["faction"], v["faction"], -int(w["kill_rel_penalty"]), kid)
	return kid


static func fight(s: Dictionary, i: int, t: int, cause: int) -> void:
	var c: Dictionary = s["rules"]["combat"]
	var w: Dictionary = s["rules"]["world"]
	var a: Dictionary = s["npcs"][i]
	var b: Dictionary = s["npcs"][t]
	reset_fighter(a)
	reset_fighter(b)
	var ha := new_hist()
	var hb := new_hist()
	var rounds := 0
	var fled := 0
	while a["hp"] > 0 and b["hp"] > 0 and rounds < c["round_cap"]:
		var xa := choose(a["policy"], a, b, ha, c, s)
		var xb := choose(b["policy"], b, a, hb, c, s)
		var r := fight_round(c, a, b, xa, xb, s)
		rounds += 1
		observe(ha, r[1])
		observe(hb, r[0])
		if a["hp"] > 0 and b["hp"] > 0:
			if a["hp"] * 100 < 20 * a["maxhp"] and rnd(s, 100) < w["flee_pct"]:
				fled = 1
			elif b["hp"] * 100 < 20 * b["maxhp"] and rnd(s, 100) < w["flee_pct"]:
				fled = 2
			if fled != 0:
				break
	var out := OUT_TIMEOUT
	if a["hp"] <= 0 and b["hp"] <= 0:
		out = OUT_BOTH_DIED
	elif b["hp"] <= 0:
		out = OUT_A_KILLED_B
	elif a["hp"] <= 0:
		out = OUT_B_KILLED_A
	elif fled == 1:
		out = OUT_A_FLED
	elif fled == 2:
		out = OUT_B_FLED
	var fid := emit(s, EV_FIGHT, i, t, rounds * 10 + out, cause)
	if out == OUT_A_KILLED_B:
		die(s, t, i, fid)
	elif out == OUT_B_KILLED_A:
		die(s, i, t, fid)
	elif out == OUT_BOTH_DIED:
		die(s, i, -1, fid)
		die(s, t, -1, fid)
	else:
		add_aff(a, t, -10, fid)
		add_aff(b, i, -10, fid)


static func _work(s: Dictionary, n: Dictionary) -> void:
	var e: Dictionary = s["rules"]["economy"]
	var tax: int = e["wage"] * e["tax_pct"] / 100
	n["gold"] += e["wage"] - tax
	s["towns"][n["loc"]]["treasury"] += tax
	s["minted"] += e["wage"]


static func _buy(s: Dictionary, n: Dictionary, town: Dictionary) -> void:
	var p := price(s, town)
	n["gold"] -= p
	town["treasury"] += p
	town["stock"] -= 1
	n["potions"] += 1
	n["basis"] += p
	emit(s, EV_BUY, n["id"], n["loc"], p)


static func npc_turn(s: Dictionary, n: Dictionary) -> void:
	var r: Dictionary = s["rules"]
	var c: Dictionary = r["combat"]
	var e: Dictionary = r["economy"]
	var w: Dictionary = r["world"]
	var town: Dictionary = s["towns"][n["loc"]]
	n["hp"] = mini(n["maxhp"], n["hp"] + maxi(1, n["maxhp"] / w["regen_div"]))
	if s["tick"] % e["upkeep_every"] == 0 and n["gold"] >= e["upkeep"]:
		n["gold"] -= e["upkeep"]
		town["treasury"] += e["upkeep"]
	if n["hp"] * 100 < 40 * n["maxhp"] and n["potions"] > 0:
		n["hp"] = mini(n["maxhp"], n["hp"] + int(c["potion_heal"]))
		n["potions"] -= 1
		if n["potions"] == 0:
			n["basis"] = 0
		emit(s, EV_POTION, n["id"])
		return
	var p := price(s, town)
	if n["trader"] != 0:
		if n["potions"] > 0:
			var sp: int = p * e["sell_pct"] / 100
			var avg: int = n["basis"] / n["potions"]
			if sp > avg and town["treasury"] >= sp:
				town["treasury"] -= sp
				n["gold"] += sp
				town["stock"] = mini(e["stock_cap"], town["stock"] + 1)
				n["basis"] -= avg
				n["potions"] -= 1
				emit(s, EV_SELL, n["id"], n["loc"], sp)
				return
		if town["stock"] > 0 and n["potions"] < 6 and n["gold"] >= p and p <= e["base_price"]:
			_buy(s, n, town)
			return
	elif n["hp"] * 100 < 60 * n["maxhp"] and n["potions"] < 3 and town["stock"] > 0 and n["gold"] >= p:
		_buy(s, n, town)
		return
	var roll := rnd(s, 100)
	if roll < 35:
		var nb: Array = s["adj"][n["loc"]]
		var dest: int = nb[rnd(s, nb.size())]
		n["loc"] = dest
		emit(s, EV_TRAVEL, n["id"], dest)
	elif roll < 60:
		var others := []
		for o in s["npcs"]:
			if o["alive"] and o["id"] != n["id"] and o["loc"] == n["loc"]:
				others.append(o["id"])
		if others.size() == 0:
			_work(s, n)
			return
		var t: int = others[rnd(s, others.size())]
		var o2: Dictionary = s["npcs"][t]
		var aggro := 0
		var cause := -1
		if n["faction"] != o2["faction"]:
			var rel: int = s["rel"][n["faction"]][o2["faction"]]
			aggro = w["aggro_pct"]
			if rel < 0:
				aggro += -rel / 4
			if s["war"][n["faction"]][o2["faction"]] != 0:
				aggro += 10
		else:
			for ent in n["aff"]:
				if ent[0] == t and ent[1] <= -40:
					aggro = 30
					cause = ent[2]
		aggro = mini(95, aggro)
		if rnd(s, 100) < aggro:
			fight(s, n["id"], t, cause)
		else:
			add_aff(n, t, 1, -1)
			add_aff(o2, n["id"], 1, -1)
	else:
		_work(s, n)


static func tick(s: Dictionary) -> void:
	s["tick"] += 1
	var e: Dictionary = s["rules"]["economy"]
	if s["tick"] % e["restock_ticks"] == 0:
		for tw in s["towns"]:
			tw["stock"] = mini(e["stock_cap"], tw["stock"] + 1)
	if s["tick"] % 10 == 0:
		for f in s["n_fac"]:
			for g in range(f + 1, s["n_fac"]):
				if s["rel"][f][g] < 0:
					change_rel(s, f, g, 1, -1)
	var keep := []
	for p in s["pending"]:
		if p[0] <= s["tick"]:
			var loc: int = (_home(s, p[1]) + rnd(s, 2)) % s["towns"].size()
			var n := _make_npc(s, p[1], loc, p[2])
			emit(s, EV_SPAWN, n["id"], p[1], p[3], p[4])
		else:
			keep.append(p)
	s["pending"] = keep
	var count: int = s["npcs"].size()
	for i in count:
		var n2: Dictionary = s["npcs"][i]
		if n2["alive"]:
			npc_turn(s, n2)
	for tw in s["towns"]:
		var b := mini(int(e["burn"]), int(tw["treasury"]))
		tw["treasury"] -= b
		s["burned"] += b


static func run(s: Dictionary, ticks: int) -> void:
	for _i in ticks:
		tick(s)


# iv = {"tick": int, "kind": String, "args": Array, "path": String(optional)}
static func apply_intervention(s: Dictionary, iv: Dictionary) -> void:
	var kind: String = iv["kind"]
	var a: Array = iv.get("args", [])
	if kind == "kill":
		var eid := emit(s, EV_INTERVENE, 0, a[0], 0)
		if s["npcs"][a[0]]["alive"]:
			die(s, a[0], -1, eid)
	elif kind == "give_gold":
		emit(s, EV_INTERVENE, 1, a[0], a[1])
		s["npcs"][a[0]]["gold"] += a[1]
		s["minted"] += a[1]
	elif kind == "set_rel":
		var eid2 := emit(s, EV_INTERVENE, 2, a[0], a[2])
		change_rel(s, a[0], a[1], a[2] - s["rel"][a[0]][a[1]], eid2)
	elif kind == "set_rule":
		var parts: PackedStringArray = String(iv["path"]).split(".")
		s["rules"][parts[0]][parts[1]] = a[0]
		emit(s, EV_INTERVENE, 3, a[0], 0)
	else:
		push_error("unknown intervention " + kind)


static func history(s: Dictionary, nid: int) -> Array:
	var out := []
	for ev in s["events"]:
		var t: int = ev[2]
		if t in [EV_TRAVEL, EV_BUY, EV_SELL, EV_POTION, EV_SPAWN] and ev[3] == nid:
			out.append(ev)
		elif t in [EV_FIGHT, EV_KILL] and (ev[3] == nid or ev[4] == nid):
			out.append(ev)
	return out


static func consequences(s: Dictionary, event_id: int) -> Array:
	var seen := {event_id: true}
	var out := []
	for ev in s["events"]:
		if seen.has(ev[6]):
			seen[ev[0]] = true
			out.append(ev)
	return out


static func describe(s: Dictionary, ev: Array) -> String:
	var t: int = ev[2]
	var nm := func(i: int) -> String:
		if i >= 0 and i < s["npcs"].size():
			return npc_name(s["npcs"][i]) + "#" + str(i)
		return "(nature)"
	match t:
		EV_TRAVEL: return "[%d] %s travels to %s" % [ev[1], nm.call(ev[3]), TOWN_NAMES[ev[4]]]
		EV_FIGHT: return "[%d] %s fights %s (%d rounds)" % [ev[1], nm.call(ev[3]), nm.call(ev[4]), ev[5] / 10]
		EV_KILL: return "[%d] %s is killed by %s in %s" % [ev[1], nm.call(ev[4]), nm.call(ev[3]), TOWN_NAMES[ev[5]]]
		EV_BUY: return "[%d] %s buys a potion for %dg" % [ev[1], nm.call(ev[3]), ev[5]]
		EV_SELL: return "[%d] %s sells a potion for %dg" % [ev[1], nm.call(ev[3]), ev[5]]
		EV_WAR: return "[%d] WAR: %s vs %s" % [ev[1], FACTION_NAMES[ev[3]], FACTION_NAMES[ev[4]]]
		EV_PEACE: return "[%d] PEACE: %s and %s" % [ev[1], FACTION_NAMES[ev[3]], FACTION_NAMES[ev[4]]]
		EV_SPAWN: return "[%d] %s arrives as heir of #%d" % [ev[1], nm.call(ev[3]), ev[5]]
		EV_POTION: return "[%d] %s drinks a potion" % [ev[1], nm.call(ev[3])]
	var kinds := ["killed", "gave gold to", "forced relations of", "changed a rule:"]
	return "[%d] GOD-MODE: %s %s (%d)" % [ev[1], kinds[ev[3]], ("#" + str(ev[4])) if ev[3] < 2 else str(ev[4]), ev[5]]


static func digest(s: Dictionary) -> int:
	var parts := [s["tick"], s["rng"], s["minted"], s["burned"], s["events"].size(), s["ev_hash"]]
	for sec in ["combat", "economy", "world"]:
		var d: Dictionary = s["rules"][sec]
		var keys := d.keys()
		keys.sort()
		for k in keys:
			parts.append(d[k])
	for tw in s["towns"]:
		parts.append(tw["treasury"])
		parts.append(tw["stock"])
	for row in s["rel"]:
		parts.append_array(row)
	for row in s["war"]:
		parts.append_array(row)
	for n in s["npcs"]:
		parts.append_array([n["id"], n["faction"], n["loc"], n["hp"], n["maxhp"], n["atk"], n["def"], n["gold"],
			n["potions"], n["alive"], n["policy"], n["kills"], n["basis"], n["aff"].size()])
		for e in n["aff"]:
			parts.append_array(e)
	for p in s["pending"]:
		parts.append_array(p)
	var strs := PackedStringArray()
	for x in parts:
		strs.append(str(int(x)))
	return fnv_str(",".join(strs))


static func digest_hex(s: Dictionary) -> String:
	return "%08x" % digest(s)
