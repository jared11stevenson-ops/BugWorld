# Python interpreter vs GDScript interpreter on compiled concepts + fuzzed grammar specs: every match digest must be identical.
extends SceneTree

const C = preload("res://ghost/concept.gd")
const G = preload("res://generated/concept_golden.gd")
const CS = preload("res://generated/concepts.gd")

var checks := 0
var fails := 0


func check_rows(spec: Dictionary, rows: Array, label: String) -> void:
	for r in rows:
		var m := C.play(spec, r[0], r[1], r[2])
		var d := C.match_digest(spec, m)
		checks += 1
		if d != r[3] or m["winner"] != r[4] or m["round"] != r[5]:
			fails += 1
			if fails < 8:
				print("FAIL ", label, " pol ", r[0], "v", r[1], " seed ", r[2], " got ", d, m["winner"], m["round"], " want ", r[3], r[4], r[5])


func _init() -> void:
	var t0 := Time.get_ticks_msec()
	for c in CS.CONCEPTS:
		var sid: String = c["spec"]["id"]
		check_rows(c["spec"], G.GOLDEN[sid], sid)
	for k in G.FUZZ:
		check_rows(G.FUZZ[k]["spec"], G.FUZZ[k]["golden"], k)
	print("CONCEPT_PARITY ", JSON.stringify({"checks": checks, "fails": fails, "ms": Time.get_ticks_msec() - t0}))
	quit(1 if fails > 0 else 0)
