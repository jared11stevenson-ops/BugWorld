# godot --headless --path . --script res://ghost/tune_splash.gd -- in.json out.json
extends SceneTree

const S = preload("res://ghost/splash_core.gd")


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var sets = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var n := 32
	var out := []
	for item in sets:
		var p: Dictionary = S.defaults()
		for k in item["p"]:
			p[k] = item["p"][k]
		for k in ["slick", "throw_cd", "refill_ticks", "max_ammo", "team_size", "max_ticks", "ally_level"]:
			p[k] = int(p[k])
		var base: int = int(item.get("seed_base", 1000))
		var w := [0, 0, 0]
		var ticks := 0
		for lv in 3:
			for i in n:
				var s := S.play(base + i, p, lv)
				w[lv] += 1 if s["winner"] == 0 else 0
				if lv == 1:
					ticks += s["t"]
		var sym := 0
		var ns := 30
		for i in ns:
			sym += 1 if S.play_symmetric(base + 500 + i, p)["winner"] == 0 else 0
		out.append({"skilled": float(w[2]) / n, "average": float(w[1]) / n, "novice": float(w[0]) / n, "skilled_stage1": float(w[2]) / n,
			"side_bias": absf(float(sym) / ns - 0.5), "ticks": float(ticks) / n, "skilled_score": 0.0})
	var f := FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	quit(0)
