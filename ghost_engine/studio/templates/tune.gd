# Headless batch tuner. godot --headless --path . --script res://ghost/tune.gd -- in.json out.json
# in: [{"p": {...params...}}, ...]; out: per-set clear rates of the skilled and novice bots over N seeds.
extends SceneTree

const A = preload("res://ghost/arcade_core.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var sets = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var n := 24
	var out := []
	for item in sets:
		var p: Dictionary = A.defaults()
		for k in item["p"]:
			p[k] = item["p"][k]
		var base: int = int(item.get("seed_base", 1000))
		var sk_full := 0
		var nov_full := 0
		var avg_full := 0
		var sk_s1 := 0
		var sk_score := 0
		for i in n:
			var r := A.play_full(base + i, p, 1)
			var q := A.play_full(base + i, p, 0)
			sk_full += 1 if r["cleared"] == 3 else 0
			sk_s1 += 1 if r["cleared"] >= 1 else 0
			sk_score += r["score"]
			nov_full += 1 if q["cleared"] == 3 else 0
			avg_full += 1 if A.play_full(base + i, p, 2)["cleared"] == 3 else 0
		out.append({"average": float(avg_full) / n, "skilled": float(sk_full) / n, "novice": float(nov_full) / n, "skilled_stage1": float(sk_s1) / n, "skilled_score": float(sk_score) / n})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	quit(0)
