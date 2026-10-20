# godot --headless --path . --script res://ghost/tune_bastion.gd -- in.json out.json
extends SceneTree

const B = preload("res://ghost/bastion_core.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var sets = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var n := 20
	var out := []
	for item in sets:
		var p: Dictionary = B.defaults()
		for k in item["p"]:
			p[k] = item["p"][k]
		for k in B.int_keys():
			p[k] = int(p[k])
		var base: int = int(item.get("seed_base", 1000))
		var w := [0, 0, 0]
		var ticks := 0
		for lv in 3:
			for i in n:
				var s := B.play(base + i, p, lv)
				w[lv] += 1 if s["winner"] == 0 else 0
				if lv == 1:
					ticks += s["t"]
		out.append({"skilled": float(w[2]) / n, "average": float(w[1]) / n, "novice": float(w[0]) / n, "skilled_stage1": float(w[2]) / n, "ticks": float(ticks) / n, "skilled_score": 0.0})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	quit(0)
