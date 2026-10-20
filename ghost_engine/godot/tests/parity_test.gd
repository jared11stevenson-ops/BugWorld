# Living Twin regression: the GDScript kernel must reproduce the Python kernel's golden traces exactly.
# Run: godot --headless --path godot --script res://tests/parity_test.gd
extends SceneTree

const K = preload("res://ghost/kernel.gd")
const TL = preload("res://ghost/timeline.gd")
const RS = preload("res://generated/rulesets.gd")
const G = preload("res://generated/golden.gd")

var checks := 0
var fails := 0


func ok(cond: bool, msg: String) -> void:
	checks += 1
	if not cond:
		fails += 1
		print("FAIL: ", msg)


func _init() -> void:
	var g: Dictionary = G.GOLDEN
	var t0 := Time.get_ticks_msec()
	# RNG
	var st := {"rng": K.seed_state(g["rng"]["seed"])}
	for v in g["rng"]["vals"]:
		ok(K.rnd(st, 1000) == v, "rng value")
	# combat payoff matrices and lab duels
	for name in g["payoff"]:
		var c: Dictionary = RS.get_rules(name)["combat"]
		var a := {"hp": 100, "maxhp": 100, "atk": 20, "def": 5, "potions": c["start_potions"], "last": -1, "streak": 0}
		for x in 4:
			for y in 4:
				ok(K.payoff(c, a, a.duplicate(), x, y) == g["payoff"][name][x][y], "payoff %s %d,%d" % [name, x, y])
		for d in g["duels"][name]:
			var r := K.duel(c, d[0], d[1], d[2])
			ok(r[0] == d[3] and r[1] == d[4] and r[2] == d[5], "duel %s %s -> %s expected %s" % [name, str(d.slice(0, 3)), str(r), str(d.slice(3))])
	# world digests at checkpoints
	for w in g["worlds"]:
		var s := K.new_world(w["seed"], RS.get_rules(w["rules"]))
		for cp in w["checkpoints"]:
			K.run(s, cp[0] - s["tick"])
			ok(K.digest_hex(s) == cp[1], "world %s seed %d tick %d digest %s != %s" % [w["rules"], w["seed"], cp[0], K.digest_hex(s), cp[1]])
		ok(s["events"].size() == w["events"], "event count %s/%d" % [w["rules"], w["seed"]])
		ok(s["ev_hash"] == w["ev_hash"], "event hash %s/%d" % [w["rules"], w["seed"]])
		ok(K.conservation_error(s) == 0, "gold conserved %s/%d" % [w["rules"], w["seed"]])
	# timelines: rewind/replay, branching, interventions
	var t: Dictionary = g["timeline"]
	var rules := RS.get_rules(t["rules"])
	var tl := TL.new(K.new_world(5, rules))
	tl.step(200)
	ok(K.digest_hex(tl.s) == t["d200"], "timeline d200")
	tl.step(100)
	ok(K.digest_hex(tl.s) == t["d300"], "timeline d300")
	tl.rewind(120)
	ok(tl.tick() == 120, "rewind tick")
	tl.step(80)
	ok(K.digest_hex(tl.s) == t["replay200"] and t["replay200"] == t["d200"], "rewind+replay reproduces tick 200")
	var main_tl := TL.new(K.new_world(9, rules))
	main_tl.step(100)
	var same = main_tl.fork()
	var alt = main_tl.fork()
	alt.intervene("kill", [1])
	alt.intervene("set_rule", [90], "world.aggro_pct")
	main_tl.step(150)
	same.step(150)
	alt.step(150)
	ok(K.digest_hex(main_tl.s) == t["main250"], "main250")
	ok(K.digest_hex(same.s) == t["same250"] and t["same250"] == t["main250"], "un-intervened fork equals mainline")
	ok(K.digest_hex(alt.s) == t["alt250"] and t["alt250"] != t["main250"], "alternate reality matches python and diverged")
	var ms := Time.get_ticks_msec() - t0
	print("PARITY_RESULT ", JSON.stringify({"checks": checks, "fails": fails, "ms": ms, "godot": Engine.get_version_info()["string"]}))
	quit(1 if fails > 0 else 0)
