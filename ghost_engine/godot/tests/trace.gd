# Runs arbitrary (ruleset, seed, ticks) cases given as JSON and writes their digests - used for fuzz parity vs Python.
# Run: godot --headless --path godot --script res://tests/trace.gd -- cases.json out.json
extends SceneTree

const K = preload("res://ghost/kernel.gd")


func _intify(v):
	if v is float:
		return int(v)
	if v is Dictionary:
		for k in v.keys():
			v[k] = _intify(v[k])
		return v
	if v is Array:
		for i in v.size():
			v[i] = _intify(v[i])
		return v
	return v


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var cases = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var out := []
	var t0 := Time.get_ticks_msec()
	var total_ticks := 0
	for c in cases:
		var rules: Dictionary = _intify(c["rules"])
		var s := K.new_world(int(c["seed"]), rules)
		K.run(s, int(c["ticks"]))
		total_ticks += int(c["ticks"])
		out.append({"digest": K.digest_hex(s), "events": s["events"].size()})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify({"results": out, "ms": Time.get_ticks_msec() - t0, "ticks": total_ticks}))
	f.close()
	quit(0)
