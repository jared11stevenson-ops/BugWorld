# Headless difficulty tuner for Cordon. godot --headless --path . --script res://ghost/tune_contain.gd -- in.json out.json
extends SceneTree

const A = preload("res://ghost/contain_core.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var sets = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var n := 40
	var out := []
	for item in sets:
		var p: Dictionary = A.defaults()
		for k in item["p"]:
			p[k] = int(item["p"][k]) if k != "law" else item["p"][k]
		var base: int = int(item.get("seed_base", 1000))
		var easy: Dictionary = p.duplicate()
		easy["beta"] = int(p["beta"]) * 70 / 100
		var sk := 0
		var nov := 0
		var ez := 0
		var av := 0
		for i in n:
			sk += A.play(base + i, p, 1)["won"]
			nov += A.play(base + i, p, 0)["won"]
			ez += A.play(base + i, easy, 1)["won"]
			av += A.play(base + i, p, 2)["won"]
		out.append({"average": float(av) / n, "skilled": float(sk) / n, "novice": float(nov) / n, "skilled_stage1": float(ez) / n, "skilled_score": 0.0})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	quit(0)
