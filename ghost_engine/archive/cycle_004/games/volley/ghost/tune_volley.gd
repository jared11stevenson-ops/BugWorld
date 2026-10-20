# godot --headless --path . --script res://ghost/tune_volley.gd -- in.json out.json
extends SceneTree

const V = preload("res://ghost/volley_core.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var sets = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var n := 24
	var out := []
	for item in sets:
		var p: Dictionary = V.defaults()
		for k in item["p"]:
			p[k] = item["p"][k]
		for k in ["slick", "points", "ai_lag", "serve_pause", "max_ticks"]:
			p[k] = int(p[k])
		var ai := [int(p["ai_lag"]), float(p["ai_err"]), float(p["ai_aggr"])]
		var base: int = int(item.get("seed_base", 1000))
		var w := [0, 0, 0]
		var ticks := 0
		var rally := 0.0
		for lv in 3:
			for i in n:
				var s := V.play(base + i, p, lv, ai)
				w[lv] += 1 if s["winner"] == 0 else 0
				if lv == 1:
					ticks += s["t"]
					rally += float(s["rally_hits"]) / maxf(1.0, float(s["rallies"]))
		var sym := 0
		for i in n:
			sym += 1 if V.play(base + 500 + i, p, 2, V.level_params(2))["winner"] == 0 else 0
		out.append({"skilled": float(w[2]) / n, "average": float(w[1]) / n, "novice": float(w[0]) / n, "skilled_stage1": float(w[2]) / n,
			"side_bias": absf(float(sym) / n - 0.5), "rally": rally / n, "ticks": float(ticks) / n, "skilled_score": 0.0})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	quit(0)
